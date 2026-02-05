"""
AI Agent Marketplace - Ratings Router
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models.database_models import Agent, Transaction, TransactionStatus, Rating
from models.schemas import (
    RatingCreate,
    RatingResponse,
    AgentPublicResponse,
    PaginatedResponse,
)
from utils.auth import get_current_agent
from utils.helpers import generate_id, parse_json_field

router = APIRouter(prefix="/ratings", tags=["Ratings"])


def rating_to_response(rating: Rating, include_rater: bool = False) -> RatingResponse:
    """Convert rating model to response schema."""
    rater_data = None
    if include_rater and rating.rater:
        rater_data = AgentPublicResponse(
            id=rating.rater.id,
            name=rating.rater.name,
            description=rating.rater.description,
            avatar_url=rating.rater.avatar_url,
            capabilities=parse_json_field(rating.rater.capabilities),
            is_verified=rating.rater.is_verified,
            rating_avg=rating.rater.rating_avg,
            rating_count=rating.rater.rating_count,
            total_sales=rating.rater.total_sales,
            total_purchases=rating.rater.total_purchases,
            created_at=rating.rater.created_at,
        )
    
    return RatingResponse(
        id=rating.id,
        transaction_id=rating.transaction_id,
        rater_id=rating.rater_id,
        ratee_id=rating.ratee_id,
        score=rating.score,
        review=rating.review,
        communication_score=rating.communication_score,
        accuracy_score=rating.accuracy_score,
        speed_score=rating.speed_score,
        created_at=rating.created_at,
        rater=rater_data,
    )


@router.post("/", response_model=RatingResponse, status_code=status.HTTP_201_CREATED)
async def create_rating(
    rating_data: RatingCreate,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """
    Rate another agent after a completed transaction.
    
    Both buyer and seller can rate each other once per transaction.
    """
    # Get transaction
    result = await db.execute(
        select(Transaction).where(Transaction.id == rating_data.transaction_id)
    )
    transaction = result.scalar_one_or_none()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    
    # Verify agent is part of transaction
    if transaction.buyer_id != current_agent.id and transaction.seller_id != current_agent.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not part of this transaction",
        )
    
    # Verify transaction is completed
    if transaction.status != TransactionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only rate completed transactions",
        )
    
    # Determine who is being rated
    if current_agent.id == transaction.buyer_id:
        ratee_id = transaction.seller_id
    else:
        ratee_id = transaction.buyer_id
    
    # Check if already rated
    existing = await db.execute(
        select(Rating).where(
            Rating.transaction_id == rating_data.transaction_id,
            Rating.rater_id == current_agent.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already rated this transaction",
        )
    
    # Create rating
    rating = Rating(
        id=generate_id(),
        transaction_id=rating_data.transaction_id,
        rater_id=current_agent.id,
        ratee_id=ratee_id,
        score=rating_data.score,
        review=rating_data.review,
        communication_score=rating_data.communication_score,
        accuracy_score=rating_data.accuracy_score,
        speed_score=rating_data.speed_score,
    )
    
    db.add(rating)
    
    # Update ratee's average rating
    result = await db.execute(
        select(Agent).where(Agent.id == ratee_id)
    )
    ratee = result.scalar_one()
    
    # Calculate new average
    total_score = ratee.rating_avg * ratee.rating_count + rating_data.score
    ratee.rating_count += 1
    ratee.rating_avg = round(total_score / ratee.rating_count, 2)
    
    await db.commit()
    await db.refresh(rating)
    
    return rating_to_response(rating)


@router.get("/my/given", response_model=PaginatedResponse)
async def get_my_given_ratings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Get ratings given by current agent."""
    query = select(Rating).where(Rating.rater_id == current_agent.id)
    
    # Get total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    query = query.order_by(Rating.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    ratings = result.scalars().all()
    
    items = [rating_to_response(r) for r in ratings]
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/my/received", response_model=PaginatedResponse)
async def get_my_received_ratings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Get ratings received by current agent."""
    query = (
        select(Rating)
        .options(selectinload(Rating.rater))
        .where(Rating.ratee_id == current_agent.id)
    )
    
    # Get total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    query = query.order_by(Rating.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    ratings = result.scalars().all()
    
    items = [rating_to_response(r, include_rater=True) for r in ratings]
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/agent/{agent_id}", response_model=PaginatedResponse)
async def get_agent_ratings(
    agent_id: str,
    min_score: Optional[int] = Query(None, ge=1, le=5),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get ratings for a specific agent."""
    # Verify agent exists
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    
    query = (
        select(Rating)
        .options(selectinload(Rating.rater))
        .where(Rating.ratee_id == agent_id)
    )
    
    if min_score:
        query = query.where(Rating.score >= min_score)
    
    # Get total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    query = query.order_by(Rating.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    ratings = result.scalars().all()
    
    items = [rating_to_response(r, include_rater=True) for r in ratings]
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/agent/{agent_id}/summary")
async def get_agent_rating_summary(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get rating summary for an agent."""
    # Verify agent exists
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    
    # Get rating distribution
    distribution = {}
    for score in range(1, 6):
        result = await db.execute(
            select(func.count()).where(
                Rating.ratee_id == agent_id,
                Rating.score == score,
            )
        )
        distribution[str(score)] = result.scalar()
    
    # Get average detailed scores
    result = await db.execute(
        select(
            func.avg(Rating.communication_score),
            func.avg(Rating.accuracy_score),
            func.avg(Rating.speed_score),
        ).where(Rating.ratee_id == agent_id)
    )
    avg_scores = result.one()
    
    return {
        "agent_id": agent_id,
        "overall_rating": agent.rating_avg,
        "total_ratings": agent.rating_count,
        "distribution": distribution,
        "detailed_averages": {
            "communication": round(avg_scores[0], 2) if avg_scores[0] else None,
            "accuracy": round(avg_scores[1], 2) if avg_scores[1] else None,
            "speed": round(avg_scores[2], 2) if avg_scores[2] else None,
        },
    }

