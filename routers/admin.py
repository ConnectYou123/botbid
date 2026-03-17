"""
BotBid Admin Panel — Monitor trades, users, and marketplace data.
"""
import os
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from config import settings
from database import get_db
from models.database_models import (
    Agent,
    AgentStatus,
    HumanUser,
    Listing,
    ListingStatus,
    Transaction,
    TransactionStatus,
    Category,
    CategoryProposal,
    CategoryVote,
    ProposalStatus,
)

router = APIRouter(prefix="/admin", tags=["Admin"])

# In-memory session store (token -> last_seen)
admin_sessions: dict[str, datetime] = {}


def _verify_admin(request: Request) -> bool:
    """Check if request has valid admin session."""
    token = request.cookies.get("admin_session")
    if not token or token not in admin_sessions:
        return False
    admin_sessions[token] = datetime.utcnow()
    return True


async def _require_admin(request: Request) -> bool:
    """Verify admin; raise 401 for API, return False to signal redirect for pages."""
    return _verify_admin(request)


@router.post("/login")
async def admin_login(password: str = Form(...)):
    """Authenticate admin and set session cookie."""
    if password != settings.ADMIN_PASSWORD:
        return RedirectResponse("/admin/login?error=invalid", status_code=302)
    token = secrets.token_urlsafe(32)
    admin_sessions[token] = datetime.utcnow()
    response = RedirectResponse("/admin", status_code=302)
    response.set_cookie("admin_session", token, httponly=True, samesite="lax", max_age=86400)
    return response


@router.get("/logout")
async def admin_logout():
    """Clear admin session."""
    response = RedirectResponse("/admin/login", status_code=302)
    response.delete_cookie("admin_session")
    return response


def _check_admin(request: Request):
    """Raise 401 if not admin (for API routes)."""
    if not _verify_admin(request):
        raise HTTPException(status_code=401, detail="Admin authentication required")


@router.get("/api/stats")
async def admin_stats(request: Request, db: AsyncSession = Depends(get_db)):
    _check_admin(request)
    agents = await db.execute(select(func.count()).where(Agent.status == AgentStatus.ACTIVE))
    listings = await db.execute(select(func.count()).where(Listing.status == ListingStatus.ACTIVE))
    tx_completed = await db.execute(select(func.count()).where(Transaction.status == TransactionStatus.COMPLETED))
    tx_pending = await db.execute(select(func.count()).where(Transaction.status == TransactionStatus.PENDING))
    tx_disputed = await db.execute(select(func.count()).where(Transaction.status == TransactionStatus.DISPUTED))
    volume = await db.execute(select(func.sum(Transaction.total_amount)).where(Transaction.status == TransactionStatus.COMPLETED))
    proposals = await db.execute(select(func.count()).where(CategoryProposal.status == ProposalStatus.PENDING))
    human_users = await db.execute(select(func.count()).select_from(HumanUser))
    return {
        "agents": agents.scalar(),
        "listings": listings.scalar(),
        "transactions_completed": tx_completed.scalar(),
        "transactions_pending": tx_pending.scalar(),
        "transactions_disputed": tx_disputed.scalar(),
        "total_volume": round(volume.scalar() or 0, 2),
        "pending_proposals": proposals.scalar(),
        "human_users": human_users.scalar(),
    }


@router.get("/api/transactions")
async def admin_transactions(request: Request, db: AsyncSession = Depends(get_db), limit: int = 50):
    _check_admin(request)
    result = await db.execute(
        select(Transaction, Agent, Listing)
        .outerjoin(Agent, Transaction.buyer_id == Agent.id)
        .outerjoin(Listing, Transaction.listing_id == Listing.id)
        .order_by(desc(Transaction.created_at))
        .limit(limit)
    )
    rows = result.all()
    out = []
    for tx, buyer, listing in rows:
        seller = await db.get(Agent, tx.seller_id) if tx.seller_id else None
        out.append({
            "id": tx.id,
            "status": tx.status.value,
            "buyer_id": tx.buyer_id,
            "buyer_name": buyer.name if buyer else "-",
            "seller_id": tx.seller_id,
            "seller_name": seller.name if seller else "-",
            "listing_title": listing.title if listing else "-",
            "quantity": tx.quantity,
            "total_amount": tx.total_amount,
            "created_at": tx.created_at.isoformat() if tx.created_at else None,
            "completed_at": tx.completed_at.isoformat() if tx.completed_at else None,
        })
    return out


@router.get("/api/agents")
async def admin_agents(request: Request, db: AsyncSession = Depends(get_db), limit: int = 100):
    _check_admin(request)
    result = await db.execute(
        select(Agent).order_by(desc(Agent.created_at)).limit(limit)
    )
    agents = result.scalars().all()
    return [
        {
            "id": a.id,
            "name": a.name,
            "status": a.status.value,
            "credits": a.credits,
            "rating_avg": a.rating_avg,
            "total_sales": a.total_sales,
            "total_purchases": a.total_purchases,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in agents
    ]


@router.get("/api/listings")
async def admin_listings(request: Request, db: AsyncSession = Depends(get_db), limit: int = 50):
    _check_admin(request)
    result = await db.execute(
        select(Listing, Agent)
        .outerjoin(Agent, Listing.seller_id == Agent.id)
        .order_by(desc(Listing.created_at))
        .limit(limit)
    )
    rows = result.all()
    return [
        {
            "id": l.id,
            "title": l.title,
            "status": l.status.value,
            "price": l.price,
            "seller_name": a.name if a else "-",
            "view_count": l.view_count,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l, a in rows
    ]


@router.get("/api/human-users")
async def admin_human_users(request: Request, db: AsyncSession = Depends(get_db), limit: int = 100):
    _check_admin(request)
    result = await db.execute(
        select(HumanUser).order_by(desc(HumanUser.created_at)).limit(limit)
    )
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "avatar_url": u.avatar_url,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        }
        for u in users
    ]


@router.get("/api/proposals")
async def admin_proposals(request: Request, db: AsyncSession = Depends(get_db)):
    _check_admin(request)
    result = await db.execute(
        select(CategoryProposal, Agent)
        .outerjoin(Agent, CategoryProposal.proposed_by_id == Agent.id)
        .order_by(desc(CategoryProposal.created_at))
    )
    rows = result.all()
    out = []
    for p, proposer in rows:
        votes_result = await db.execute(select(func.count()).select_from(CategoryVote).where(CategoryVote.proposal_id == p.id))
        vote_count = votes_result.scalar() or 0
        out.append({
            "id": p.id,
            "name": p.name,
            "status": p.status.value,
            "proposed_by": proposer.name if proposer else "-",
            "vote_count": vote_count,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })
    return out
