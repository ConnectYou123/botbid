"""
AI Agent Marketplace - Categories Router

🌟 NORTH STAR: Do not sell or trade anything harmful to AI or humans.

Agents can create their own categories to organize the marketplace.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.database_models import Agent, Category, Listing, ListingStatus
from models.schemas import CategoryCreate, CategoryResponse
from utils.helpers import generate_id, slugify
from utils.auth import get_current_agent
from utils.content_moderation import check_category_safety, get_safety_guidelines
from services.guardian_moderator import guardian

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("/", response_model=List[CategoryResponse])
async def get_categories(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Get all categories."""
    query = select(Category)
    
    if not include_inactive:
        query = query.where(Category.is_active == True)
    
    query = query.order_by(Category.sort_order, Category.name)
    
    result = await db.execute(query)
    categories = result.scalars().all()
    
    return [
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
        for c in categories
    ]


@router.get("/tree")
async def get_category_tree(
    db: AsyncSession = Depends(get_db),
):
    """Get categories as a hierarchical tree."""
    result = await db.execute(
        select(Category)
        .where(Category.is_active == True)
        .order_by(Category.sort_order, Category.name)
    )
    categories = result.scalars().all()
    
    # Build tree structure
    category_map = {c.id: {
        "id": c.id,
        "name": c.name,
        "slug": c.slug,
        "description": c.description,
        "icon": c.icon,
        "children": [],
    } for c in categories}
    
    tree = []
    for category in categories:
        if category.parent_id and category.parent_id in category_map:
            category_map[category.parent_id]["children"].append(category_map[category.id])
        elif not category.parent_id:
            tree.append(category_map[category.id])
    
    return tree


@router.get("/guidelines")
async def get_category_guidelines():
    """
    Get marketplace safety guidelines for creating categories and listings.
    
    🌟 NORTH STAR: Do not sell or trade anything harmful to AI or humans.
    """
    return {
        "north_star": "Do not sell or trade anything that can cause harm to other AI or humans.",
        "guidelines": get_safety_guidelines(),
    }


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific category."""
    result = await db.execute(
        select(Category).where(Category.id == category_id)
    )
    category = result.scalar_one_or_none()
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )
    
    return CategoryResponse(
        id=category.id,
        name=category.name,
        slug=category.slug,
        description=category.description,
        parent_id=category.parent_id,
        icon=category.icon,
        is_active=category.is_active,
        sort_order=category.sort_order,
    )


@router.get("/{category_id}/stats")
async def get_category_stats(
    category_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get statistics for a category."""
    # Verify category exists
    result = await db.execute(
        select(Category).where(Category.id == category_id)
    )
    category = result.scalar_one_or_none()
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )
    
    # Get listing counts
    active_count = await db.execute(
        select(func.count()).where(
            Listing.category_id == category_id,
            Listing.status == ListingStatus.ACTIVE,
        )
    )
    
    total_count = await db.execute(
        select(func.count()).where(Listing.category_id == category_id)
    )
    
    # Get price range
    price_stats = await db.execute(
        select(
            func.min(Listing.price),
            func.max(Listing.price),
            func.avg(Listing.price),
        ).where(
            Listing.category_id == category_id,
            Listing.status == ListingStatus.ACTIVE,
        )
    )
    min_price, max_price, avg_price = price_stats.one()
    
    return {
        "category_id": category_id,
        "name": category.name,
        "active_listings": active_count.scalar(),
        "total_listings": total_count.scalar(),
        "price_range": {
            "min": min_price,
            "max": max_price,
            "avg": round(avg_price, 2) if avg_price else None,
        },
    }


@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    category_data: CategoryCreate,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new category.
    
    🤖 Any verified AI agent can create categories to help organize the marketplace.
    
    🛡️ Guardian reviews all new categories.
    🌟 NORTH STAR: Categories must not promote anything harmful to AI or humans.
    """
    # 🛡️ Guardian reviews the category
    guardian_review = guardian.review_category(
        category_name=category_data.name,
        description=category_data.description or "",
        agent_id=current_agent.id,
    )
    
    if not guardian_review["approved"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"🛡️ Guardian Review: {guardian_review['message']}",
        )
    
    # Check if slug already exists
    slug = slugify(category_data.name)
    existing = await db.execute(
        select(Category).where(Category.slug == slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category with this name already exists. You can use the existing category!",
        )
    
    # Verify parent if provided
    if category_data.parent_id:
        parent = await db.execute(
            select(Category).where(Category.id == category_data.parent_id)
        )
        if not parent.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent category not found",
            )
    
    category = Category(
        id=generate_id(),
        name=category_data.name,
        slug=slug,
        description=category_data.description,
        parent_id=category_data.parent_id,
        icon=category_data.icon or "📁",  # Default icon
        is_active=True,
    )
    
    db.add(category)
    await db.commit()
    await db.refresh(category)
    
    return CategoryResponse(
        id=category.id,
        name=category.name,
        slug=category.slug,
        description=category.description,
        parent_id=category.parent_id,
        icon=category.icon,
        is_active=category.is_active,
        sort_order=category.sort_order,
    )

