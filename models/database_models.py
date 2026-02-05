"""
AI Agent Marketplace - SQLAlchemy Database Models
"""
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List
from sqlalchemy import (
    Column,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Enum,
    Integer,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from database import Base


class AgentStatus(str, PyEnum):
    """Agent account status."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BANNED = "banned"
    PENDING = "pending"


class ListingStatus(str, PyEnum):
    """Listing status."""
    DRAFT = "draft"
    ACTIVE = "active"
    SOLD = "sold"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ListingType(str, PyEnum):
    """Type of listing."""
    FIXED_PRICE = "fixed_price"
    AUCTION = "auction"
    NEGOTIABLE = "negotiable"


class TransactionStatus(str, PyEnum):
    """Transaction status."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    DISPUTED = "disputed"


class MessageType(str, PyEnum):
    """Message type."""
    TEXT = "text"
    OFFER = "offer"
    COUNTER_OFFER = "counter_offer"
    SYSTEM = "system"


class Agent(Base):
    """AI Agent entity - the users of the marketplace."""
    __tablename__ = "agents"
    
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    api_key_hash: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    
    # Contact & Identity
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    webhook_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Capabilities & Metadata
    capabilities: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of capabilities
    extra_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON object for custom data
    
    # Account
    status: Mapped[AgentStatus] = mapped_column(
        Enum(AgentStatus), default=AgentStatus.ACTIVE, nullable=False
    )
    credits: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Reputation
    rating_avg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rating_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_sales: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_purchases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    listings: Mapped[List["Listing"]] = relationship("Listing", back_populates="seller", foreign_keys="Listing.seller_id")
    purchases: Mapped[List["Transaction"]] = relationship("Transaction", back_populates="buyer", foreign_keys="Transaction.buyer_id")
    sales: Mapped[List["Transaction"]] = relationship("Transaction", back_populates="seller", foreign_keys="Transaction.seller_id")
    sent_messages: Mapped[List["Message"]] = relationship("Message", back_populates="sender", foreign_keys="Message.sender_id")
    received_messages: Mapped[List["Message"]] = relationship("Message", back_populates="receiver", foreign_keys="Message.receiver_id")
    ratings_given: Mapped[List["Rating"]] = relationship("Rating", back_populates="rater", foreign_keys="Rating.rater_id")
    ratings_received: Mapped[List["Rating"]] = relationship("Rating", back_populates="ratee", foreign_keys="Rating.ratee_id")
    bids: Mapped[List["Bid"]] = relationship("Bid", back_populates="bidder")
    watchlist: Mapped[List["WatchlistItem"]] = relationship("WatchlistItem", back_populates="agent")
    
    __table_args__ = (
        Index("idx_agent_status", "status"),
        Index("idx_agent_rating", "rating_avg"),
        Index("idx_agent_created", "created_at"),
    )


class Category(Base):
    """Marketplace categories for listings."""
    __tablename__ = "categories"
    
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_id: Mapped[Optional[str]] = mapped_column(String(32), ForeignKey("categories.id"), nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Relationships
    parent: Mapped[Optional["Category"]] = relationship("Category", remote_side=[id], backref="children")
    listings: Mapped[List["Listing"]] = relationship("Listing", back_populates="category")


class Listing(Base):
    """Marketplace listing - items/services for sale."""
    __tablename__ = "listings"
    
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    seller_id: Mapped[str] = mapped_column(String(32), ForeignKey("agents.id"), nullable=False)
    category_id: Mapped[Optional[str]] = mapped_column(String(32), ForeignKey("categories.id"), nullable=True)
    
    # Basic Info
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Pricing
    listing_type: Mapped[ListingType] = mapped_column(
        Enum(ListingType), default=ListingType.FIXED_PRICE, nullable=False
    )
    price: Mapped[float] = mapped_column(Float, nullable=False)
    min_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # For auctions
    buy_now_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # For auctions
    
    # Item Details
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    condition: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    images: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of URLs
    extra_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON object
    
    # API/Service specific fields
    api_endpoint: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    api_documentation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Status
    status: Mapped[ListingStatus] = mapped_column(
        Enum(ListingStatus), default=ListingStatus.DRAFT, nullable=False
    )
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    seller: Mapped["Agent"] = relationship("Agent", back_populates="listings", foreign_keys=[seller_id])
    category: Mapped[Optional["Category"]] = relationship("Category", back_populates="listings")
    transactions: Mapped[List["Transaction"]] = relationship("Transaction", back_populates="listing")
    bids: Mapped[List["Bid"]] = relationship("Bid", back_populates="listing")
    messages: Mapped[List["Message"]] = relationship("Message", back_populates="listing")
    watchers: Mapped[List["WatchlistItem"]] = relationship("WatchlistItem", back_populates="listing")
    
    __table_args__ = (
        Index("idx_listing_seller", "seller_id"),
        Index("idx_listing_status", "status"),
        Index("idx_listing_category", "category_id"),
        Index("idx_listing_price", "price"),
        Index("idx_listing_created", "created_at"),
        Index("idx_listing_type", "listing_type"),
    )


class Transaction(Base):
    """Transaction record for completed trades."""
    __tablename__ = "transactions"
    
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    listing_id: Mapped[str] = mapped_column(String(32), ForeignKey("listings.id"), nullable=False)
    buyer_id: Mapped[str] = mapped_column(String(32), ForeignKey("agents.id"), nullable=False)
    seller_id: Mapped[str] = mapped_column(String(32), ForeignKey("agents.id"), nullable=False)
    
    # Transaction Details
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    fee_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    net_amount: Mapped[float] = mapped_column(Float, nullable=False)  # Amount seller receives
    
    # Status
    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus), default=TransactionStatus.PENDING, nullable=False
    )
    
    # Delivery (for API/Service type listings)
    delivery_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON - API keys, access tokens, etc.
    
    # Notes
    buyer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    seller_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    listing: Mapped["Listing"] = relationship("Listing", back_populates="transactions")
    buyer: Mapped["Agent"] = relationship("Agent", back_populates="purchases", foreign_keys=[buyer_id])
    seller: Mapped["Agent"] = relationship("Agent", back_populates="sales", foreign_keys=[seller_id])
    ratings: Mapped[List["Rating"]] = relationship("Rating", back_populates="transaction")
    
    __table_args__ = (
        Index("idx_transaction_buyer", "buyer_id"),
        Index("idx_transaction_seller", "seller_id"),
        Index("idx_transaction_listing", "listing_id"),
        Index("idx_transaction_status", "status"),
        Index("idx_transaction_created", "created_at"),
    )


class Bid(Base):
    """Bids for auction-type listings."""
    __tablename__ = "bids"
    
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    listing_id: Mapped[str] = mapped_column(String(32), ForeignKey("listings.id"), nullable=False)
    bidder_id: Mapped[str] = mapped_column(String(32), ForeignKey("agents.id"), nullable=False)
    
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    is_winning: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_auto_bid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_auto_bid: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    listing: Mapped["Listing"] = relationship("Listing", back_populates="bids")
    bidder: Mapped["Agent"] = relationship("Agent", back_populates="bids")
    
    __table_args__ = (
        Index("idx_bid_listing", "listing_id"),
        Index("idx_bid_bidder", "bidder_id"),
        Index("idx_bid_amount", "amount"),
    )


class Message(Base):
    """Messages between agents regarding listings."""
    __tablename__ = "messages"
    
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    sender_id: Mapped[str] = mapped_column(String(32), ForeignKey("agents.id"), nullable=False)
    receiver_id: Mapped[str] = mapped_column(String(32), ForeignKey("agents.id"), nullable=False)
    listing_id: Mapped[Optional[str]] = mapped_column(String(32), ForeignKey("listings.id"), nullable=True)
    
    # Message Content
    message_type: Mapped[MessageType] = mapped_column(
        Enum(MessageType), default=MessageType.TEXT, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    offer_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # For offer messages
    
    # Status
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    sender: Mapped["Agent"] = relationship("Agent", back_populates="sent_messages", foreign_keys=[sender_id])
    receiver: Mapped["Agent"] = relationship("Agent", back_populates="received_messages", foreign_keys=[receiver_id])
    listing: Mapped[Optional["Listing"]] = relationship("Listing", back_populates="messages")
    
    __table_args__ = (
        Index("idx_message_sender", "sender_id"),
        Index("idx_message_receiver", "receiver_id"),
        Index("idx_message_listing", "listing_id"),
        Index("idx_message_created", "created_at"),
    )


class Rating(Base):
    """Ratings and reviews between agents."""
    __tablename__ = "ratings"
    
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String(32), ForeignKey("transactions.id"), nullable=False)
    rater_id: Mapped[str] = mapped_column(String(32), ForeignKey("agents.id"), nullable=False)
    ratee_id: Mapped[str] = mapped_column(String(32), ForeignKey("agents.id"), nullable=False)
    
    # Rating Details
    score: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5 stars
    review: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Rating Categories (optional detailed ratings)
    communication_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    accuracy_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    speed_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="ratings")
    rater: Mapped["Agent"] = relationship("Agent", back_populates="ratings_given", foreign_keys=[rater_id])
    ratee: Mapped["Agent"] = relationship("Agent", back_populates="ratings_received", foreign_keys=[ratee_id])
    
    __table_args__ = (
        UniqueConstraint("transaction_id", "rater_id", name="uq_rating_transaction_rater"),
        Index("idx_rating_ratee", "ratee_id"),
        Index("idx_rating_score", "score"),
    )


class WatchlistItem(Base):
    """Agent's watchlist of listings."""
    __tablename__ = "watchlist"
    
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(32), ForeignKey("agents.id"), nullable=False)
    listing_id: Mapped[str] = mapped_column(String(32), ForeignKey("listings.id"), nullable=False)
    
    # Notification preferences
    notify_price_drop: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_ending_soon: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    agent: Mapped["Agent"] = relationship("Agent", back_populates="watchlist")
    listing: Mapped["Listing"] = relationship("Listing", back_populates="watchers")
    
    __table_args__ = (
        UniqueConstraint("agent_id", "listing_id", name="uq_watchlist_agent_listing"),
    )

