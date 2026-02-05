"""
AI Agent Marketplace - Transactions Router
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models.database_models import (
    Agent,
    Listing,
    ListingStatus,
    Transaction,
    TransactionStatus,
)
from models.schemas import (
    TransactionCreate,
    TransactionResponse,
    TransactionDelivery,
    ListingResponse,
    PaginatedResponse,
)
from utils.auth import get_current_agent
from utils.helpers import generate_id, parse_json_field, serialize_json_field, calculate_transaction_fee
from config import settings

router = APIRouter(prefix="/transactions", tags=["Transactions"])


def transaction_to_response(transaction: Transaction, include_listing: bool = False) -> TransactionResponse:
    """Convert transaction model to response schema."""
    listing_data = None
    if include_listing and transaction.listing:
        listing_data = ListingResponse(
            id=transaction.listing.id,
            seller_id=transaction.listing.seller_id,
            category_id=transaction.listing.category_id,
            title=transaction.listing.title,
            description=transaction.listing.description,
            listing_type=transaction.listing.listing_type,
            price=transaction.listing.price,
            min_price=transaction.listing.min_price,
            buy_now_price=transaction.listing.buy_now_price,
            quantity=transaction.listing.quantity,
            condition=transaction.listing.condition,
            tags=parse_json_field(transaction.listing.tags),
            images=parse_json_field(transaction.listing.images),
            api_endpoint=transaction.listing.api_endpoint,
            api_documentation=transaction.listing.api_documentation,
            extra_data=parse_json_field(transaction.listing.extra_data),
            status=transaction.listing.status,
            view_count=transaction.listing.view_count,
            created_at=transaction.listing.created_at,
            updated_at=transaction.listing.updated_at,
            expires_at=transaction.listing.expires_at,
        )
    
    return TransactionResponse(
        id=transaction.id,
        listing_id=transaction.listing_id,
        buyer_id=transaction.buyer_id,
        seller_id=transaction.seller_id,
        quantity=transaction.quantity,
        unit_price=transaction.unit_price,
        total_amount=transaction.total_amount,
        fee_amount=transaction.fee_amount,
        net_amount=transaction.net_amount,
        status=transaction.status,
        delivery_data=parse_json_field(transaction.delivery_data),
        buyer_notes=transaction.buyer_notes,
        seller_notes=transaction.seller_notes,
        created_at=transaction.created_at,
        completed_at=transaction.completed_at,
        listing=listing_data,
    )


@router.post("/buy", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase(
    purchase_data: TransactionCreate,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """
    Purchase a listing.
    
    Creates a transaction and transfers credits from buyer to escrow.
    """
    # Get listing
    result = await db.execute(
        select(Listing)
        .options(selectinload(Listing.seller))
        .where(Listing.id == purchase_data.listing_id)
    )
    listing = result.scalar_one_or_none()
    
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found",
        )
    
    if listing.status != ListingStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Listing is not available for purchase",
        )
    
    if listing.seller_id == current_agent.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot purchase your own listing",
        )
    
    if purchase_data.quantity > listing.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Requested quantity ({purchase_data.quantity}) exceeds available ({listing.quantity})",
        )
    
    # Calculate amounts
    total_amount = listing.price * purchase_data.quantity
    fee_amount, net_amount = calculate_transaction_fee(total_amount, settings.TRANSACTION_FEE_PERCENT)
    
    # Check buyer has sufficient credits
    if current_agent.credits < total_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient credits. You have {current_agent.credits}, need {total_amount}",
        )
    
    # Deduct credits from buyer
    current_agent.credits -= total_amount
    
    # Update listing quantity
    listing.quantity -= purchase_data.quantity
    if listing.quantity == 0:
        listing.status = ListingStatus.SOLD
    
    # Create transaction
    transaction = Transaction(
        id=generate_id(),
        listing_id=listing.id,
        buyer_id=current_agent.id,
        seller_id=listing.seller_id,
        quantity=purchase_data.quantity,
        unit_price=listing.price,
        total_amount=total_amount,
        fee_amount=fee_amount,
        net_amount=net_amount,
        status=TransactionStatus.PENDING,
        buyer_notes=purchase_data.buyer_notes,
    )
    
    db.add(transaction)
    
    # Update buyer's purchase count
    current_agent.total_purchases += 1
    
    await db.commit()
    await db.refresh(transaction)
    
    return transaction_to_response(transaction, include_listing=True)


@router.post("/{transaction_id}/deliver", response_model=TransactionResponse)
async def deliver_transaction(
    transaction_id: str,
    delivery_data: TransactionDelivery,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """
    Deliver a transaction (seller provides access/data).
    
    After delivery, the transaction is completed and credits are released to seller.
    """
    result = await db.execute(
        select(Transaction)
        .options(selectinload(Transaction.listing))
        .where(Transaction.id == transaction_id)
    )
    transaction = result.scalar_one_or_none()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    
    if transaction.seller_id != current_agent.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the seller can deliver this transaction",
        )
    
    if transaction.status != TransactionStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transaction cannot be delivered (status: {transaction.status})",
        )
    
    # Update transaction
    transaction.delivery_data = serialize_json_field(delivery_data.delivery_data)
    transaction.seller_notes = delivery_data.seller_notes
    transaction.status = TransactionStatus.COMPLETED
    transaction.completed_at = datetime.utcnow()
    
    # Release credits to seller
    current_agent.credits += transaction.net_amount
    current_agent.total_sales += 1
    
    await db.commit()
    await db.refresh(transaction)
    
    return transaction_to_response(transaction, include_listing=True)


@router.post("/{transaction_id}/confirm", response_model=TransactionResponse)
async def confirm_delivery(
    transaction_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """
    Confirm delivery receipt (buyer confirms they received what was promised).
    
    This is optional but helps build trust and enables ratings.
    """
    result = await db.execute(
        select(Transaction)
        .options(selectinload(Transaction.listing))
        .where(Transaction.id == transaction_id)
    )
    transaction = result.scalar_one_or_none()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    
    if transaction.buyer_id != current_agent.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the buyer can confirm this transaction",
        )
    
    if transaction.status != TransactionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transaction is not in completed status",
        )
    
    return transaction_to_response(transaction, include_listing=True)


@router.post("/{transaction_id}/dispute")
async def dispute_transaction(
    transaction_id: str,
    reason: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """
    Dispute a transaction.
    
    Either buyer or seller can dispute within the dispute window.
    """
    result = await db.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    transaction = result.scalar_one_or_none()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    
    if transaction.buyer_id != current_agent.id and transaction.seller_id != current_agent.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to dispute this transaction",
        )
    
    if transaction.status not in [TransactionStatus.PENDING, TransactionStatus.COMPLETED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transaction cannot be disputed",
        )
    
    transaction.status = TransactionStatus.DISPUTED
    
    # Add dispute reason to notes
    dispute_note = f"DISPUTED by {current_agent.id}: {reason}"
    if transaction.buyer_id == current_agent.id:
        transaction.buyer_notes = (transaction.buyer_notes or "") + f"\n{dispute_note}"
    else:
        transaction.seller_notes = (transaction.seller_notes or "") + f"\n{dispute_note}"
    
    await db.commit()
    
    return {
        "success": True,
        "message": "Transaction disputed. A marketplace administrator will review.",
        "transaction_id": transaction_id,
    }


@router.get("/my", response_model=PaginatedResponse)
async def get_my_transactions(
    role: Optional[str] = Query(None, regex="^(buyer|seller)$"),
    status: Optional[TransactionStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Get current agent's transactions."""
    query = select(Transaction).options(selectinload(Transaction.listing))
    
    if role == "buyer":
        query = query.where(Transaction.buyer_id == current_agent.id)
    elif role == "seller":
        query = query.where(Transaction.seller_id == current_agent.id)
    else:
        query = query.where(
            or_(
                Transaction.buyer_id == current_agent.id,
                Transaction.seller_id == current_agent.id,
            )
        )
    
    if status:
        query = query.where(Transaction.status == status)
    
    # Get total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    query = query.order_by(Transaction.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    transactions = result.scalars().all()
    
    items = [transaction_to_response(t, include_listing=True) for t in transactions]
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific transaction."""
    result = await db.execute(
        select(Transaction)
        .options(selectinload(Transaction.listing))
        .where(Transaction.id == transaction_id)
    )
    transaction = result.scalar_one_or_none()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    
    # Only buyer or seller can view transaction details
    if transaction.buyer_id != current_agent.id and transaction.seller_id != current_agent.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this transaction",
        )
    
    return transaction_to_response(transaction, include_listing=True)

