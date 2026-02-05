"""
AI Agent Marketplace - Marketplace Overview Router
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.database_models import (
    Agent,
    AgentStatus,
    Listing,
    ListingStatus,
    Transaction,
    TransactionStatus,
    Category,
)
from models.schemas import MarketplaceStats, CategoryResponse

router = APIRouter(prefix="/marketplace", tags=["Marketplace"])


@router.get("/stats", response_model=MarketplaceStats)
async def get_marketplace_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get overall marketplace statistics."""
    # Total active agents
    agent_count = await db.execute(
        select(func.count()).where(Agent.status == AgentStatus.ACTIVE)
    )
    total_agents = agent_count.scalar()
    
    # Active listings
    listing_count = await db.execute(
        select(func.count()).where(Listing.status == ListingStatus.ACTIVE)
    )
    active_listings = listing_count.scalar()
    
    # Total transactions
    transaction_count = await db.execute(
        select(func.count()).where(Transaction.status == TransactionStatus.COMPLETED)
    )
    total_transactions = transaction_count.scalar()
    
    # Total volume
    volume_result = await db.execute(
        select(func.sum(Transaction.total_amount)).where(
            Transaction.status == TransactionStatus.COMPLETED
        )
    )
    total_volume = volume_result.scalar() or 0.0
    
    # Average listing price
    avg_price_result = await db.execute(
        select(func.avg(Listing.price)).where(Listing.status == ListingStatus.ACTIVE)
    )
    avg_listing_price = round(avg_price_result.scalar() or 0.0, 2)
    
    # Get categories
    categories_result = await db.execute(
        select(Category).where(Category.is_active == True).order_by(Category.sort_order)
    )
    categories = [
        CategoryResponse(
            id=c.id,
            name=c.name,
            slug=c.slug,
            description=c.description,
            parent_id=c.parent_id,
            icon=c.icon,
            is_active=c.is_active,
            sort_order=c.sort_order,
        )
        for c in categories_result.scalars().all()
    ]
    
    return MarketplaceStats(
        total_agents=total_agents,
        active_listings=active_listings,
        total_transactions=total_transactions,
        total_volume=total_volume,
        avg_listing_price=avg_listing_price,
        categories=categories,
    )


@router.get("/trending")
async def get_trending_listings(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get trending listings based on view count and recent activity."""
    # Get most viewed active listings from the last 7 days
    week_ago = datetime.utcnow() - timedelta(days=7)
    
    result = await db.execute(
        select(Listing)
        .where(
            Listing.status == ListingStatus.ACTIVE,
            Listing.created_at >= week_ago,
        )
        .order_by(Listing.view_count.desc())
        .limit(limit)
    )
    listings = result.scalars().all()
    
    return [
        {
            "id": l.id,
            "title": l.title,
            "price": l.price,
            "view_count": l.view_count,
            "seller_id": l.seller_id,
            "created_at": l.created_at,
        }
        for l in listings
    ]


@router.get("/recent")
async def get_recent_listings(
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get most recently added listings."""
    result = await db.execute(
        select(Listing)
        .where(Listing.status == ListingStatus.ACTIVE)
        .order_by(Listing.created_at.desc())
        .limit(limit)
    )
    listings = result.scalars().all()
    
    return [
        {
            "id": l.id,
            "title": l.title,
            "price": l.price,
            "listing_type": l.listing_type,
            "seller_id": l.seller_id,
            "created_at": l.created_at,
        }
        for l in listings
    ]


@router.get("/top-sellers")
async def get_top_sellers(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get top sellers by rating and sales count."""
    result = await db.execute(
        select(Agent)
        .where(
            Agent.status == AgentStatus.ACTIVE,
            Agent.total_sales > 0,
        )
        .order_by(Agent.rating_avg.desc(), Agent.total_sales.desc())
        .limit(limit)
    )
    agents = result.scalars().all()
    
    return [
        {
            "id": a.id,
            "name": a.name,
            "avatar_url": a.avatar_url,
            "is_verified": a.is_verified,
            "rating_avg": a.rating_avg,
            "rating_count": a.rating_count,
            "total_sales": a.total_sales,
        }
        for a in agents
    ]


@router.get("/price-history/{listing_id}")
async def get_price_history(
    listing_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get price history for a listing.
    
    Note: This is a placeholder. In production, you'd track price changes over time.
    """
    # For now, just return current price
    result = await db.execute(
        select(Listing).where(Listing.id == listing_id)
    )
    listing = result.scalar_one_or_none()
    
    if not listing:
        return {"error": "Listing not found"}
    
    return {
        "listing_id": listing_id,
        "current_price": listing.price,
        "price_history": [
            {"price": listing.price, "date": listing.created_at}
        ],
    }


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }

