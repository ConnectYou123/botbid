"""
AI Agent Marketplace - Messaging Router
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models.database_models import Agent, Listing, Message, MessageType, AgentStatus
from models.schemas import (
    MessageCreate,
    MessageResponse,
    ConversationResponse,
    AgentPublicResponse,
    ListingResponse,
    PaginatedResponse,
)
from utils.auth import get_current_agent
from utils.helpers import generate_id, parse_json_field

router = APIRouter(prefix="/messages", tags=["Messages"])


def message_to_response(message: Message) -> MessageResponse:
    """Convert message model to response schema."""
    return MessageResponse(
        id=message.id,
        sender_id=message.sender_id,
        receiver_id=message.receiver_id,
        listing_id=message.listing_id,
        message_type=message.message_type,
        content=message.content,
        offer_amount=message.offer_amount,
        is_read=message.is_read,
        read_at=message.read_at,
        created_at=message.created_at,
    )


@router.post("/", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    message_data: MessageCreate,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Send a message to another agent."""
    # Verify receiver exists and is active
    result = await db.execute(
        select(Agent).where(Agent.id == message_data.receiver_id)
    )
    receiver = result.scalar_one_or_none()
    
    if not receiver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receiver not found",
        )
    
    if receiver.status != AgentStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send message to inactive agent",
        )
    
    if receiver.id == current_agent.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send message to yourself",
        )
    
    # Verify listing if provided
    if message_data.listing_id:
        result = await db.execute(
            select(Listing).where(Listing.id == message_data.listing_id)
        )
        listing = result.scalar_one_or_none()
        
        if not listing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Listing not found",
            )
    
    # Create message
    message = Message(
        id=generate_id(),
        sender_id=current_agent.id,
        receiver_id=message_data.receiver_id,
        listing_id=message_data.listing_id,
        message_type=message_data.message_type,
        content=message_data.content,
        offer_amount=message_data.offer_amount,
    )
    
    db.add(message)
    await db.commit()
    await db.refresh(message)
    
    # TODO: Send webhook notification to receiver if configured
    
    return message_to_response(message)


@router.get("/inbox", response_model=PaginatedResponse)
async def get_inbox(
    unread_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Get messages received by current agent."""
    query = select(Message).where(Message.receiver_id == current_agent.id)
    
    if unread_only:
        query = query.where(Message.is_read == False)
    
    # Get total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    query = query.order_by(Message.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    messages = result.scalars().all()
    
    items = [message_to_response(m) for m in messages]
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/sent", response_model=PaginatedResponse)
async def get_sent_messages(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Get messages sent by current agent."""
    query = select(Message).where(Message.sender_id == current_agent.id)
    
    # Get total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    query = query.order_by(Message.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    messages = result.scalars().all()
    
    items = [message_to_response(m) for m in messages]
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/conversations")
async def get_conversations(
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Get list of conversation threads."""
    # Get all unique conversations (grouped by other agent)
    # This returns the latest message from each conversation
    
    # Get all messages involving current agent
    query = (
        select(Message)
        .options(selectinload(Message.listing))
        .where(
            or_(
                Message.sender_id == current_agent.id,
                Message.receiver_id == current_agent.id,
            )
        )
        .order_by(Message.created_at.desc())
    )
    
    result = await db.execute(query)
    all_messages = result.scalars().all()
    
    # Group by conversation partner
    conversations = {}
    for message in all_messages:
        other_id = message.receiver_id if message.sender_id == current_agent.id else message.sender_id
        
        if other_id not in conversations:
            conversations[other_id] = {
                "messages": [],
                "listing_id": message.listing_id,
                "unread_count": 0,
            }
        
        conversations[other_id]["messages"].append(message)
        if message.receiver_id == current_agent.id and not message.is_read:
            conversations[other_id]["unread_count"] += 1
    
    # Get agent info for all conversation partners
    agent_ids = list(conversations.keys())
    if agent_ids:
        agents_result = await db.execute(
            select(Agent).where(Agent.id.in_(agent_ids))
        )
        agents = {a.id: a for a in agents_result.scalars().all()}
    else:
        agents = {}
    
    # Build response
    response = []
    for other_id, data in conversations.items():
        agent = agents.get(other_id)
        if not agent:
            continue
        
        latest_message = data["messages"][0] if data["messages"] else None
        
        response.append({
            "other_agent": AgentPublicResponse(
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
            ),
            "latest_message": message_to_response(latest_message) if latest_message else None,
            "unread_count": data["unread_count"],
            "listing_id": data["listing_id"],
        })
    
    # Sort by latest message time
    response.sort(key=lambda x: x["latest_message"].created_at if x["latest_message"] else datetime.min, reverse=True)
    
    return response


@router.get("/conversation/{agent_id}", response_model=List[MessageResponse])
async def get_conversation(
    agent_id: str,
    listing_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Get conversation with a specific agent."""
    # Verify agent exists
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id)
    )
    other_agent = result.scalar_one_or_none()
    
    if not other_agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    
    # Get messages between the two agents
    query = select(Message).where(
        or_(
            and_(Message.sender_id == current_agent.id, Message.receiver_id == agent_id),
            and_(Message.sender_id == agent_id, Message.receiver_id == current_agent.id),
        )
    )
    
    if listing_id:
        query = query.where(Message.listing_id == listing_id)
    
    query = query.order_by(Message.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    messages = result.scalars().all()
    
    # Mark received messages as read
    for message in messages:
        if message.receiver_id == current_agent.id and not message.is_read:
            message.is_read = True
            message.read_at = datetime.utcnow()
    
    await db.commit()
    
    # Return in chronological order
    messages.reverse()
    
    return [message_to_response(m) for m in messages]


@router.patch("/{message_id}/read")
async def mark_message_read(
    message_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Mark a message as read."""
    result = await db.execute(
        select(Message).where(Message.id == message_id)
    )
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )
    
    if message.receiver_id != current_agent.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only mark your own received messages as read",
        )
    
    if not message.is_read:
        message.is_read = True
        message.read_at = datetime.utcnow()
        await db.commit()
    
    return {"success": True, "message": "Message marked as read"}


@router.get("/unread/count")
async def get_unread_count(
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Get count of unread messages."""
    result = await db.execute(
        select(func.count()).where(
            Message.receiver_id == current_agent.id,
            Message.is_read == False,
        )
    )
    count = result.scalar()
    
    return {"unread_count": count}

