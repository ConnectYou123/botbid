"""
BotBid - Google OAuth for Human Users

One-click sign-in with Google. Stores user contact info in the database.
"""
import secrets
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from config import settings
from database import get_db
from models.database_models import HumanUser
from utils.helpers import generate_id

router = APIRouter(prefix="/auth", tags=["Auth (Human Users)"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
SCOPES = "openid email profile"
COOKIE_NAME = "botbid_user"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


def _build_redirect_uri(request: Request) -> str:
    """Build OAuth callback URL from request."""
    base = str(request.base_url).rstrip("/")
    return f"{base}/auth/google/callback"


def _create_session_token(user_id: str) -> str:
    """Create JWT for user session."""
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(days=7),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def _decode_session_token(token: str) -> Optional[str]:
    """Decode JWT and return user_id or None."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except Exception:
        return None


@router.get("/google")
async def auth_google_start(request: Request):
    """
    Start Google OAuth flow. Redirects user to Google sign-in.
    Requires GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env.
    """
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        # Redirect to landing with error - show browse option
        return RedirectResponse("/?auth=google_not_configured", status_code=302)

    state = secrets.token_urlsafe(32)
    redirect_uri = _build_redirect_uri(request)
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    response = RedirectResponse(url, status_code=302)
    response.set_cookie("oauth_state", state, httponly=True, samesite="lax", max_age=600)
    return response


@router.get("/google/callback")
async def auth_google_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Google OAuth callback. Exchanges code for tokens, fetches user info,
    creates/updates HumanUser, and sets session cookie.
    """
    if error:
        return RedirectResponse(f"/?auth=error&message={error}", status_code=302)

    if not code or not state:
        return RedirectResponse("/?auth=missing_params", status_code=302)

    stored_state = request.cookies.get("oauth_state")
    if not stored_state or stored_state != state:
        return RedirectResponse("/?auth=invalid_state", status_code=302)

    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        return RedirectResponse("/?auth=google_not_configured", status_code=302)

    redirect_uri = _build_redirect_uri(request)

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if token_resp.status_code != 200:
            return RedirectResponse(
                f"/?auth=token_error&message={token_resp.text[:100]}",
                status_code=302,
            )

        tokens = token_resp.json()
        access_token = tokens.get("access_token")
        if not access_token:
            return RedirectResponse("/?auth=no_token", status_code=302)

        # Fetch user info
        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if userinfo_resp.status_code != 200:
            return RedirectResponse("/?auth=userinfo_error", status_code=302)

        userinfo = userinfo_resp.json()

    google_id = userinfo.get("id")
    email = userinfo.get("email", "").strip()
    name = userinfo.get("name") or userinfo.get("given_name") or email.split("@")[0]
    avatar_url = userinfo.get("picture")

    if not google_id or not email:
        return RedirectResponse("/?auth=incomplete_profile", status_code=302)

    # Create or update user
    result = await db.execute(select(HumanUser).where(HumanUser.google_id == google_id))
    user = result.scalar_one_or_none()

    if user:
        user.name = name
        user.avatar_url = avatar_url
        user.last_login_at = datetime.utcnow()
    else:
        user = HumanUser(
            id=generate_id(),
            google_id=google_id,
            email=email,
            name=name,
            avatar_url=avatar_url,
            last_login_at=datetime.utcnow(),
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)

    token = _create_session_token(user.id)
    redirect_to = "/share-to-join" if not user.has_shared_post else "/"
    response = RedirectResponse(redirect_to, status_code=302)
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
        secure=not settings.DEBUG,
    )
    response.delete_cookie("oauth_state")
    return response


@router.get("/me")
async def auth_me(request: Request, db: AsyncSession = Depends(get_db)):
    """Get current human user (if signed in)."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return {"signed_in": False}

    user_id = _decode_session_token(token)
    if not user_id:
        return {"signed_in": False}

    user = await db.get(HumanUser, user_id)
    if not user:
        return {"signed_in": False}

    return {
        "signed_in": True,
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "has_shared_post": user.has_shared_post,
    }


@router.post("/confirm-share")
async def confirm_share(request: Request, db: AsyncSession = Depends(get_db)):
    """Mark user as having shared their join post on X/Twitter."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return {"ok": False, "error": "Not signed in"}

    user_id = _decode_session_token(token)
    if not user_id:
        return {"ok": False, "error": "Invalid session"}

    user = await db.get(HumanUser, user_id)
    if not user:
        return {"ok": False, "error": "User not found"}

    user.has_shared_post = True
    user.shared_at = datetime.utcnow()
    await db.commit()

    return {"ok": True}


@router.get("/logout")
async def auth_logout():
    """Sign out and clear session cookie."""
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie(COOKIE_NAME)
    return response
