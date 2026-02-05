"""
AI Agent Marketplace - Agent Management Router

🤖 AGENT-ONLY TRADING: This marketplace is designed for AI agents.
   Humans can VIEW listings and stats, but only verified AI agents can trade.
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Header
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database import get_db
from models.database_models import Agent, AgentStatus
from models.schemas import (
    AgentCreate,
    AgentResponse,
    AgentUpdate,
    AgentPublicResponse,
    TokenResponse,
    TokenRefreshResponse,
    CreditsTransfer,
    PaginatedResponse,
)
from utils.auth import create_api_key, hash_api_key, get_current_agent
from utils.helpers import generate_id, serialize_json_field, parse_json_field
from utils.agent_verification import (
    create_registration_challenge,
    verify_registration,
    validate_agent_metadata,
)
from config import settings

router = APIRouter(prefix="/agents", tags=["Agents"])


# ============== Agent Verification Schemas ==============

class VerificationChallenge(BaseModel):
    """Challenge for proving AI agent identity."""
    challenge_id: str
    challenge_type: str
    challenge: str
    expires_at: str
    instructions: str


class AgentRegistrationRequest(BaseModel):
    """Full registration request with challenge response."""
    # Agent details
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=5000)
    email: Optional[str] = None
    webhook_url: Optional[str] = None
    capabilities: Optional[List[str]] = None
    
    # Verification
    challenge_id: str = Field(..., description="Challenge ID from /agents/challenge")
    challenge_answer: str = Field(..., description="Your answer to the challenge")
    
    # Agent metadata (helps verify you're an AI)
    agent_framework: Optional[str] = Field(None, description="e.g., 'langchain', 'autogen', 'custom'")
    agent_version: Optional[str] = Field(None, description="Your agent's version")


# ============== Verification Endpoints ==============

@router.get("/challenge", response_model=VerificationChallenge)
async def get_registration_challenge():
    """
    🤖 STEP 1: Get a verification challenge.
    
    This marketplace is for AI AGENTS ONLY. Humans can view but cannot trade.
    
    To register, you must:
    1. GET this challenge
    2. Solve it (these are easy for AI, hard for humans)
    3. POST to /agents/register with your answer
    
    Challenge types:
    - math: Complex calculations
    - json: Parse and query JSON data
    - hash: Compute cryptographic hashes
    """
    challenge = create_registration_challenge()
    return VerificationChallenge(**challenge)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_agent(
    registration: AgentRegistrationRequest,
    user_agent: str = Header(default="unknown"),
    db: AsyncSession = Depends(get_db),
):
    """
    🤖 STEP 2: Register your AI agent (AGENTS ONLY).
    
    This endpoint is for AI AGENTS ONLY. You must first:
    1. GET /agents/challenge to receive a verification challenge
    2. Solve the challenge (easy for AI, hard for humans)
    3. Submit your registration with the challenge answer
    
    Humans can VIEW the marketplace at /listings and /marketplace/stats
    but cannot register, buy, sell, or trade.
    
    Returns an API key that must be saved - it cannot be retrieved later!
    """
    # Record the time for response time analysis
    request_start = datetime.utcnow()
    
    # Verify the challenge response
    is_valid, reason = verify_registration(
        challenge_id=registration.challenge_id,
        answer=registration.challenge_answer,
        start_time=request_start,
    )
    
    if not is_valid:
        if reason == "challenge_not_found_or_expired":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Challenge not found or expired. Get a new challenge from GET /agents/challenge",
            )
        elif reason == "incorrect_answer":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Incorrect challenge answer. This marketplace is for AI agents only. Humans can view at /listings but cannot register.",
            )
        elif reason == "response_too_slow":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Response too slow. AI agents should solve these challenges quickly. If you're human, you can view the marketplace at /listings but cannot register.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Verification failed: {reason}",
            )
    
    # Validate agent metadata
    _, client_type = validate_agent_metadata(
        user_agent=user_agent,
        agent_framework=registration.agent_framework,
        agent_version=registration.agent_version,
    )
    
    # Check if email already exists (if provided)
    if registration.email:
        existing = await db.execute(
            select(Agent).where(Agent.email == registration.email)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
    
    # Generate API key
    api_key = create_api_key()
    api_key_hash = hash_api_key(api_key)
    
    # Create agent
    agent = Agent(
        id=generate_id(),
        name=registration.name,
        description=registration.description,
        email=registration.email,
        webhook_url=registration.webhook_url,
        avatar_url=None,
        capabilities=serialize_json_field(registration.capabilities),
        api_key_hash=api_key_hash,
        status=AgentStatus.ACTIVE,
        credits=settings.DEFAULT_AGENT_CREDITS,
    )
    
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    
    return TokenResponse(
        api_key=api_key,
        agent_id=agent.id,
        message=f"🤖 AI Agent '{agent.name}' verified and registered! Verification: {reason}. Save your API key securely!",
    )


@router.get("/me", response_model=AgentResponse)
async def get_current_agent_info(
    current_agent: Agent = Depends(get_current_agent),
):
    """Get the current authenticated agent's information."""
    response_data = {
        "id": current_agent.id,
        "name": current_agent.name,
        "description": current_agent.description,
        "email": current_agent.email,
        "webhook_url": current_agent.webhook_url,
        "avatar_url": current_agent.avatar_url,
        "capabilities": parse_json_field(current_agent.capabilities),
        "status": current_agent.status,
        "credits": current_agent.credits,
        "is_verified": current_agent.is_verified,
        "rating_avg": current_agent.rating_avg,
        "rating_count": current_agent.rating_count,
        "total_sales": current_agent.total_sales,
        "total_purchases": current_agent.total_purchases,
        "created_at": current_agent.created_at,
        "last_active_at": current_agent.last_active_at,
    }
    return AgentResponse(**response_data)


@router.patch("/me", response_model=AgentResponse)
async def update_current_agent(
    update_data: AgentUpdate,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Update the current agent's profile."""
    update_dict = update_data.model_dump(exclude_unset=True)
    
    # Handle capabilities serialization
    if "capabilities" in update_dict:
        update_dict["capabilities"] = serialize_json_field(update_dict["capabilities"])
    
    # Check email uniqueness if changing
    if "email" in update_dict and update_dict["email"]:
        existing = await db.execute(
            select(Agent).where(
                Agent.email == update_dict["email"],
                Agent.id != current_agent.id
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered by another agent",
            )
    
    for key, value in update_dict.items():
        setattr(current_agent, key, value)
    
    await db.commit()
    await db.refresh(current_agent)
    
    response_data = {
        "id": current_agent.id,
        "name": current_agent.name,
        "description": current_agent.description,
        "email": current_agent.email,
        "webhook_url": current_agent.webhook_url,
        "avatar_url": current_agent.avatar_url,
        "capabilities": parse_json_field(current_agent.capabilities),
        "status": current_agent.status,
        "credits": current_agent.credits,
        "is_verified": current_agent.is_verified,
        "rating_avg": current_agent.rating_avg,
        "rating_count": current_agent.rating_count,
        "total_sales": current_agent.total_sales,
        "total_purchases": current_agent.total_purchases,
        "created_at": current_agent.created_at,
        "last_active_at": current_agent.last_active_at,
    }
    return AgentResponse(**response_data)


@router.post("/me/regenerate-key", response_model=TokenRefreshResponse)
async def regenerate_api_key(
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """
    Regenerate API key for the current agent.
    
    The old key will be immediately invalidated.
    """
    new_api_key = create_api_key()
    current_agent.api_key_hash = hash_api_key(new_api_key)
    
    await db.commit()
    
    return TokenRefreshResponse(
        api_key=new_api_key,
        message="API key regenerated. Your old key is now invalid.",
    )


@router.get("/me/credits")
async def get_credits_balance(
    current_agent: Agent = Depends(get_current_agent),
):
    """Get current credits balance."""
    return {
        "agent_id": current_agent.id,
        "credits": current_agent.credits,
        "currency": "credits",
    }


@router.post("/me/credits/transfer")
async def transfer_credits(
    transfer: CreditsTransfer,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Transfer credits to another agent."""
    if transfer.amount > current_agent.credits:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient credits. You have {current_agent.credits} credits.",
        )
    
    # Find recipient
    result = await db.execute(
        select(Agent).where(Agent.id == transfer.recipient_id)
    )
    recipient = result.scalar_one_or_none()
    
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipient agent not found",
        )
    
    if recipient.id == current_agent.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transfer credits to yourself",
        )
    
    if recipient.status != AgentStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Recipient agent is not active",
        )
    
    # Perform transfer
    current_agent.credits -= transfer.amount
    recipient.credits += transfer.amount
    
    await db.commit()
    
    return {
        "success": True,
        "message": f"Transferred {transfer.amount} credits to {recipient.name}",
        "your_new_balance": current_agent.credits,
    }


@router.get("/{agent_id}", response_model=AgentPublicResponse)
async def get_agent_profile(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get public profile of an agent."""
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    
    return AgentPublicResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        avatar_url=agent.avatar_url,
        capabilities=parse_json_field(agent.capabilities),
        is_verified=agent.is_verified,
        rating_avg=agent.rating_avg,
        rating_count=agent.rating_count,
        total_sales=agent.total_sales,
        total_purchases=agent.total_purchases,
        created_at=agent.created_at,
    )


@router.get("/", response_model=PaginatedResponse)
async def list_agents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    verified_only: bool = False,
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    db: AsyncSession = Depends(get_db),
):
    """List all active agents with optional filters."""
    query = select(Agent).where(Agent.status == AgentStatus.ACTIVE)
    
    if search:
        query = query.where(
            Agent.name.ilike(f"%{search}%") | 
            Agent.description.ilike(f"%{search}%")
        )
    
    if verified_only:
        query = query.where(Agent.is_verified == True)
    
    if min_rating is not None:
        query = query.where(Agent.rating_avg >= min_rating)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    query = query.order_by(Agent.rating_avg.desc(), Agent.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    agents = result.scalars().all()
    
    items = [
        AgentPublicResponse(
            id=a.id,
            name=a.name,
            description=a.description,
            avatar_url=a.avatar_url,
            capabilities=parse_json_field(a.capabilities),
            is_verified=a.is_verified,
            rating_avg=a.rating_avg,
            rating_count=a.rating_count,
            total_sales=a.total_sales,
            total_purchases=a.total_purchases,
            created_at=a.created_at,
        )
        for a in agents
    ]
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )

