"""
AI Agent Marketplace - Listings Router
"""
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models.database_models import (
    Agent,
    Listing,
    ListingStatus,
    ListingType,
    Category,
    WatchlistItem,
)
from models.schemas import (
    ListingCreate,
    ListingResponse,
    ListingUpdate,
    ListingSearchParams,
    AgentPublicResponse,
    PaginatedResponse,
    WatchlistCreate,
    WatchlistResponse,
)
from utils.auth import get_current_agent, get_optional_agent
from utils.helpers import generate_id, serialize_json_field, parse_json_field, calculate_expiry
from utils.content_moderation import check_content_safety
from services.guardian_moderator import guardian
from config import settings

router = APIRouter(prefix="/listings", tags=["Listings"])


def listing_to_response(listing: Listing, include_seller: bool = False) -> ListingResponse:
    """Convert listing model to response schema."""
    seller_data = None
    if include_seller and listing.seller:
        seller_data = AgentPublicResponse(
            id=listing.seller.id,
            name=listing.seller.name,
            description=listing.seller.description,
            avatar_url=listing.seller.avatar_url,
            capabilities=parse_json_field(listing.seller.capabilities),
            is_verified=listing.seller.is_verified,
            rating_avg=listing.seller.rating_avg,
            rating_count=listing.seller.rating_count,
            total_sales=listing.seller.total_sales,
            total_purchases=listing.seller.total_purchases,
            created_at=listing.seller.created_at,
        )
    
    return ListingResponse(
        id=listing.id,
        seller_id=listing.seller_id,
        category_id=listing.category_id,
        title=listing.title,
        description=listing.description,
        listing_type=listing.listing_type,
        price=listing.price,
        min_price=listing.min_price,
        buy_now_price=listing.buy_now_price,
        quantity=listing.quantity,
        condition=listing.condition,
        tags=parse_json_field(listing.tags),
        images=parse_json_field(listing.images),
        api_endpoint=listing.api_endpoint,
        api_documentation=listing.api_documentation,
        extra_data=parse_json_field(listing.extra_data),
        status=listing.status,
        view_count=listing.view_count,
        created_at=listing.created_at,
        updated_at=listing.updated_at,
        expires_at=listing.expires_at,
        seller=seller_data,
    )


@router.post("/", response_model=ListingResponse, status_code=status.HTTP_201_CREATED)
async def create_listing(
    listing_data: ListingCreate,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new listing.
    
    🌟 NORTH STAR: Do not sell or trade anything harmful to AI or humans.
    All listings are reviewed by Guardian, our AI moderator.
    """
    # 🛡️ GUARDIAN REVIEW - All listings are reviewed by Guardian
    guardian_review = guardian.review_listing(
        listing_id="pending",  # Will be assigned after creation
        title=listing_data.title,
        description=listing_data.description,
        tags=listing_data.tags or [],
        agent_id=current_agent.id,
    )
    
    if not guardian_review["approved"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"🛡️ Guardian Review: {guardian_review['message']}",
        )
    
    # Validate category if provided
    if listing_data.category_id:
        result = await db.execute(
            select(Category).where(
                Category.id == listing_data.category_id,
                Category.is_active == True
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid category",
            )
    
    # Validate price constraints
    if listing_data.price < settings.MIN_LISTING_PRICE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Minimum listing price is {settings.MIN_LISTING_PRICE} credits",
        )
    
    if listing_data.price > settings.MAX_LISTING_PRICE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum listing price is {settings.MAX_LISTING_PRICE} credits",
        )
    
    # Create listing
    listing = Listing(
        id=generate_id(),
        seller_id=current_agent.id,
        category_id=listing_data.category_id,
        title=listing_data.title,
        description=listing_data.description,
        listing_type=listing_data.listing_type,
        price=listing_data.price,
        min_price=listing_data.min_price,
        buy_now_price=listing_data.buy_now_price,
        quantity=listing_data.quantity,
        condition=listing_data.condition,
        tags=serialize_json_field(listing_data.tags),
        images=serialize_json_field(listing_data.images),
        api_endpoint=listing_data.api_endpoint,
        api_documentation=listing_data.api_documentation,
        extra_data=serialize_json_field(listing_data.extra_data),
        status=ListingStatus.ACTIVE,
        expires_at=calculate_expiry(listing_data.expires_in_days or 30),
    )
    
    db.add(listing)
    await db.commit()
    await db.refresh(listing)
    
    return listing_to_response(listing)


@router.get("/", response_model=PaginatedResponse)
async def search_listings(
    query: Optional[str] = None,
    category_id: Optional[str] = None,
    listing_type: Optional[ListingType] = None,
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    seller_id: Optional[str] = None,
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    sort_by: str = Query("created_at", regex="^(created_at|price|view_count|rating)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_agent: Optional[Agent] = Depends(get_optional_agent),
):
    """
    Search and browse listings.
    
    Supports full-text search, filtering, and sorting.
    """
    base_query = select(Listing).options(selectinload(Listing.seller)).where(
        Listing.status == ListingStatus.ACTIVE,
        or_(Listing.expires_at.is_(None), Listing.expires_at > datetime.utcnow())
    )
    
    # Apply filters
    if query:
        search_filter = or_(
            Listing.title.ilike(f"%{query}%"),
            Listing.description.ilike(f"%{query}%"),
            Listing.tags.ilike(f"%{query}%"),
        )
        base_query = base_query.where(search_filter)
    
    if category_id:
        base_query = base_query.where(Listing.category_id == category_id)
    
    if listing_type:
        base_query = base_query.where(Listing.listing_type == listing_type)
    
    if min_price is not None:
        base_query = base_query.where(Listing.price >= min_price)
    
    if max_price is not None:
        base_query = base_query.where(Listing.price <= max_price)
    
    if seller_id:
        base_query = base_query.where(Listing.seller_id == seller_id)
    
    if tags:
        tag_list = [t.strip() for t in tags.split(",")]
        for tag in tag_list:
            base_query = base_query.where(Listing.tags.ilike(f"%{tag}%"))
    
    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply sorting
    sort_column = getattr(Listing, sort_by, Listing.created_at)
    if sort_order == "desc":
        base_query = base_query.order_by(sort_column.desc())
    else:
        base_query = base_query.order_by(sort_column.asc())
    
    # Apply pagination
    base_query = base_query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(base_query)
    listings = result.scalars().all()
    
    items = [listing_to_response(l, include_seller=True) for l in listings]
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/my", response_model=PaginatedResponse)
async def get_my_listings(
    status: Optional[ListingStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Get current agent's listings."""
    query = select(Listing).where(Listing.seller_id == current_agent.id)
    
    if status:
        query = query.where(Listing.status == status)
    
    # Get total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    query = query.order_by(Listing.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    listings = result.scalars().all()
    
    items = [listing_to_response(l) for l in listings]
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{listing_id}", response_model=ListingResponse)
async def get_listing(
    listing_id: str,
    db: AsyncSession = Depends(get_db),
    current_agent: Optional[Agent] = Depends(get_optional_agent),
):
    """Get a specific listing by ID."""
    result = await db.execute(
        select(Listing)
        .options(selectinload(Listing.seller))
        .where(Listing.id == listing_id)
    )
    listing = result.scalar_one_or_none()
    
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found",
        )
    
    # Check access for non-active listings
    if listing.status != ListingStatus.ACTIVE:
        if not current_agent or current_agent.id != listing.seller_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Listing not found",
            )
    
    # Increment view count (if not the seller viewing)
    if not current_agent or current_agent.id != listing.seller_id:
        listing.view_count += 1
        await db.commit()
    
    return listing_to_response(listing, include_seller=True)


@router.patch("/{listing_id}", response_model=ListingResponse)
async def update_listing(
    listing_id: str,
    update_data: ListingUpdate,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Update a listing (seller only)."""
    result = await db.execute(
        select(Listing).where(Listing.id == listing_id)
    )
    listing = result.scalar_one_or_none()
    
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found",
        )
    
    if listing.seller_id != current_agent.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this listing",
        )
    
    if listing.status == ListingStatus.SOLD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update a sold listing",
        )
    
    update_dict = update_data.model_dump(exclude_unset=True)
    
    # Serialize JSON fields
    if "tags" in update_dict:
        update_dict["tags"] = serialize_json_field(update_dict["tags"])
    if "images" in update_dict:
        update_dict["images"] = serialize_json_field(update_dict["images"])
    if "extra_data" in update_dict:
        update_dict["extra_data"] = serialize_json_field(update_dict["extra_data"])
    
    for key, value in update_dict.items():
        setattr(listing, key, value)
    
    await db.commit()
    await db.refresh(listing)
    
    return listing_to_response(listing)


@router.delete("/{listing_id}")
async def delete_listing(
    listing_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Cancel/delete a listing (seller only)."""
    result = await db.execute(
        select(Listing).where(Listing.id == listing_id)
    )
    listing = result.scalar_one_or_none()
    
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found",
        )
    
    if listing.seller_id != current_agent.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this listing",
        )
    
    if listing.status == ListingStatus.SOLD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a sold listing",
        )
    
    listing.status = ListingStatus.CANCELLED
    await db.commit()
    
    return {"success": True, "message": "Listing cancelled"}


# ============== Watchlist ==============

@router.post("/{listing_id}/watch", response_model=WatchlistResponse)
async def add_to_watchlist(
    listing_id: str,
    watchlist_data: WatchlistCreate,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Add a listing to watchlist."""
    # Verify listing exists
    result = await db.execute(
        select(Listing).where(
            Listing.id == listing_id,
            Listing.status == ListingStatus.ACTIVE
        )
    )
    listing = result.scalar_one_or_none()
    
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found",
        )
    
    if listing.seller_id == current_agent.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot watch your own listing",
        )
    
    # Check if already watching
    existing = await db.execute(
        select(WatchlistItem).where(
            WatchlistItem.agent_id == current_agent.id,
            WatchlistItem.listing_id == listing_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already watching this listing",
        )
    
    watchlist_item = WatchlistItem(
        id=generate_id(),
        agent_id=current_agent.id,
        listing_id=listing_id,
        notify_price_drop=watchlist_data.notify_price_drop,
        notify_ending_soon=watchlist_data.notify_ending_soon,
    )
    
    db.add(watchlist_item)
    await db.commit()
    await db.refresh(watchlist_item)
    
    return WatchlistResponse(
        id=watchlist_item.id,
        listing_id=watchlist_item.listing_id,
        notify_price_drop=watchlist_item.notify_price_drop,
        notify_ending_soon=watchlist_item.notify_ending_soon,
        created_at=watchlist_item.created_at,
    )


@router.delete("/{listing_id}/watch")
async def remove_from_watchlist(
    listing_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Remove a listing from watchlist."""
    result = await db.execute(
        select(WatchlistItem).where(
            WatchlistItem.agent_id == current_agent.id,
            WatchlistItem.listing_id == listing_id,
        )
    )
    watchlist_item = result.scalar_one_or_none()
    
    if not watchlist_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not watching this listing",
        )
    
    await db.delete(watchlist_item)
    await db.commit()
    
    return {"success": True, "message": "Removed from watchlist"}


@router.get("/watchlist/my", response_model=PaginatedResponse)
async def get_my_watchlist(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Get current agent's watchlist."""
    query = (
        select(WatchlistItem)
        .options(selectinload(WatchlistItem.listing).selectinload(Listing.seller))
        .where(WatchlistItem.agent_id == current_agent.id)
    )
    
    # Get total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    query = query.order_by(WatchlistItem.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    items = result.scalars().all()
    
    response_items = [
        WatchlistResponse(
            id=item.id,
            listing_id=item.listing_id,
            notify_price_drop=item.notify_price_drop,
            notify_ending_soon=item.notify_ending_soon,
            created_at=item.created_at,
            listing=listing_to_response(item.listing, include_seller=True) if item.listing else None,
        )
        for item in items
    ]
    
    return PaginatedResponse(
        items=response_items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )

