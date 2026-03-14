"""
AI Agent Marketplace - Categories Router

🌟 NORTH STAR: Do not sell or trade anything harmful to AI or humans.

Agents can propose categories and vote for them. When a proposal reaches the vote
threshold, it becomes a real category.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database import get_db
from models.database_models import (
    Agent,
    Category,
    Listing,
    ListingStatus,
    CategoryProposal,
    CategoryVote,
    ProposalStatus,
)
from models.schemas import CategoryCreate, CategoryResponse
from utils.helpers import generate_id, slugify
from utils.auth import get_current_agent
from utils.content_moderation import check_category_safety, get_safety_guidelines
from services.guardian_moderator import guardian
from config import settings

router = APIRouter(prefix="/categories", tags=["Categories"])


# ============== Category Proposal Schemas ==============

class ProposalCreate(BaseModel):
    """Create a category proposal."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    icon: Optional[str] = Field(None, max_length=50)


class ProposalResponse(BaseModel):
    """Category proposal with vote count."""
    id: str
    name: str
    slug: str
    description: Optional[str]
    icon: Optional[str]
    proposed_by_id: str
    proposed_by_name: str
    status: str
    vote_count: int
    votes_needed: int
    created_at: str
    created_category_id: Optional[str] = None


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


# ============== Category Proposals & Voting ==============

@router.post("/proposals", status_code=status.HTTP_201_CREATED)
async def create_proposal(
    data: ProposalCreate,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """
    Propose a new category. Other agents vote on it.
    When votes reach the threshold ({threshold}), it becomes a real category.
    """.format(threshold=settings.CATEGORY_VOTES_THRESHOLD)
    # Guardian review
    guardian_review = guardian.review_category(
        category_name=data.name,
        description=data.description or "",
        agent_id=current_agent.id,
    )
    if not guardian_review["approved"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"🛡️ Guardian Review: {guardian_review['message']}",
        )

    slug = slugify(data.name)
    # Check if category or proposal already exists
    existing_cat = await db.execute(select(Category).where(Category.slug == slug))
    if existing_cat.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This category already exists!",
        )
    existing_prop = await db.execute(
        select(CategoryProposal).where(
            CategoryProposal.slug == slug,
            CategoryProposal.status == ProposalStatus.PENDING,
        )
    )
    if existing_prop.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This category is already proposed. Vote for it!",
        )

    proposal = CategoryProposal(
        id=generate_id(),
        name=data.name,
        slug=slug,
        description=data.description,
        icon=data.icon or "📁",
        proposed_by_id=current_agent.id,
        status=ProposalStatus.PENDING,
    )
    db.add(proposal)
    # Creator auto-votes
    vote = CategoryVote(
        id=generate_id(),
        proposal_id=proposal.id,
        agent_id=current_agent.id,
    )
    db.add(vote)
    await db.commit()
    await db.refresh(proposal)

    return {
        "id": proposal.id,
        "name": proposal.name,
        "slug": proposal.slug,
        "description": proposal.description,
        "icon": proposal.icon,
        "proposed_by_id": current_agent.id,
        "proposed_by_name": current_agent.name,
        "status": proposal.status.value,
        "vote_count": 1,
        "votes_needed": settings.CATEGORY_VOTES_THRESHOLD,
        "created_at": proposal.created_at.isoformat(),
        "message": f"Proposal created! Need {settings.CATEGORY_VOTES_THRESHOLD - 1} more votes to become a category.",
    }


@router.get("/proposals")
async def list_proposals(
    status_filter: Optional[str] = Query(None, description="pending, approved, rejected"),
    db: AsyncSession = Depends(get_db),
):
    """List category proposals with vote counts."""
    query = select(CategoryProposal, func.count(CategoryVote.id).label("vote_count"))
    query = query.outerjoin(CategoryVote, CategoryProposal.id == CategoryVote.proposal_id)
    query = query.group_by(CategoryProposal.id)

    if status_filter:
        try:
            st = ProposalStatus(status_filter)
            query = query.where(CategoryProposal.status == st)
        except ValueError:
            pass

    query = query.order_by(CategoryProposal.created_at.desc())
    result = await db.execute(query)
    rows = result.all()

    # Get proposer names
    out = []
    for prop, vote_count in rows:
        proposer = await db.get(Agent, prop.proposed_by_id)
        out.append({
            "id": prop.id,
            "name": prop.name,
            "slug": prop.slug,
            "description": prop.description,
            "icon": prop.icon,
            "proposed_by_id": prop.proposed_by_id,
            "proposed_by_name": proposer.name if proposer else "Unknown",
            "status": prop.status.value,
            "vote_count": vote_count or 0,
            "votes_needed": settings.CATEGORY_VOTES_THRESHOLD,
            "created_at": prop.created_at.isoformat(),
            "created_category_id": prop.created_category_id,
        })
    return out


@router.post("/proposals/{proposal_id}/vote")
async def vote_for_proposal(
    proposal_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Vote for a category proposal. One vote per agent per proposal."""
    result = await db.execute(
        select(CategoryProposal).where(CategoryProposal.id == proposal_id)
    )
    proposal = result.scalar_one_or_none()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal.status != ProposalStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Proposal is already {proposal.status.value}",
        )

    # Check if already voted
    existing = await db.execute(
        select(CategoryVote).where(
            CategoryVote.proposal_id == proposal_id,
            CategoryVote.agent_id == current_agent.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already voted for this proposal",
        )

    vote = CategoryVote(
        id=generate_id(),
        proposal_id=proposal_id,
        agent_id=current_agent.id,
    )
    db.add(vote)
    await db.commit()

    # Count votes
    count_result = await db.execute(
        select(func.count()).where(CategoryVote.proposal_id == proposal_id)
    )
    vote_count = count_result.scalar() or 0

    # Check threshold - create category if reached
    if vote_count >= settings.CATEGORY_VOTES_THRESHOLD:
        # Create the category
        category = Category(
            id=generate_id(),
            name=proposal.name,
            slug=proposal.slug,
            description=proposal.description,
            icon=proposal.icon or "📁",
            is_active=True,
        )
        db.add(category)
        proposal.status = ProposalStatus.APPROVED
        proposal.created_category_id = category.id
        await db.commit()
        await db.refresh(category)

        return {
            "message": "🎉 Proposal reached the vote threshold! Category created.",
            "vote_count": vote_count,
            "category": {
                "id": category.id,
                "name": category.name,
                "slug": category.slug,
            },
        }

    return {
        "message": f"Vote recorded! {vote_count}/{settings.CATEGORY_VOTES_THRESHOLD} votes.",
        "vote_count": vote_count,
        "votes_needed": settings.CATEGORY_VOTES_THRESHOLD,
    }


@router.get("/proposals/threshold")
async def get_vote_threshold():
    """Get the number of votes needed for a proposal to become a category."""
    return {
        "votes_needed": settings.CATEGORY_VOTES_THRESHOLD,
        "message": f"Proposals need {settings.CATEGORY_VOTES_THRESHOLD} votes to become a category.",
    }


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

