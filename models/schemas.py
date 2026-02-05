"""
AI Agent Marketplace - Pydantic Schemas for API Request/Response
"""
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, EmailStr, HttpUrl, field_validator
from enum import Enum


# ============== Enums ==============

class AgentStatusEnum(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BANNED = "banned"
    PENDING = "pending"


class ListingStatusEnum(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    SOLD = "sold"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ListingTypeEnum(str, Enum):
    FIXED_PRICE = "fixed_price"
    AUCTION = "auction"
    NEGOTIABLE = "negotiable"


class TransactionStatusEnum(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    DISPUTED = "disputed"


class MessageTypeEnum(str, Enum):
    TEXT = "text"
    OFFER = "offer"
    COUNTER_OFFER = "counter_offer"
    SYSTEM = "system"


# ============== Agent Schemas ==============

class AgentBase(BaseModel):
    """Base agent schema."""
    name: str = Field(..., min_length=1, max_length=100, description="Agent name")
    description: Optional[str] = Field(None, max_length=5000, description="Agent description")
    email: Optional[EmailStr] = Field(None, description="Contact email")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for notifications")
    avatar_url: Optional[str] = Field(None, description="Avatar image URL")
    capabilities: Optional[List[str]] = Field(None, description="List of agent capabilities")


class AgentCreate(AgentBase):
    """Schema for creating a new agent."""
    pass


class AgentUpdate(BaseModel):
    """Schema for updating an agent."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=5000)
    email: Optional[EmailStr] = None
    webhook_url: Optional[str] = None
    avatar_url: Optional[str] = None
    capabilities: Optional[List[str]] = None


class AgentResponse(AgentBase):
    """Schema for agent response."""
    id: str
    status: AgentStatusEnum
    credits: float
    is_verified: bool
    rating_avg: float
    rating_count: int
    total_sales: int
    total_purchases: int
    created_at: datetime
    last_active_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class AgentPublicResponse(BaseModel):
    """Public agent info (for other agents to see)."""
    id: str
    name: str
    description: Optional[str]
    avatar_url: Optional[str]
    capabilities: Optional[List[str]]
    is_verified: bool
    rating_avg: float
    rating_count: int
    total_sales: int
    total_purchases: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============== Auth Schemas ==============

class TokenResponse(BaseModel):
    """Authentication token response."""
    api_key: str = Field(..., description="Your API key - save this, it cannot be retrieved later!")
    agent_id: str
    message: str = "Agent registered successfully. Save your API key securely!"


class TokenRefreshResponse(BaseModel):
    """Token refresh response."""
    api_key: str
    message: str = "API key regenerated. Old key is now invalid."


# ============== Category Schemas ==============

class CategoryBase(BaseModel):
    """Base category schema."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    icon: Optional[str] = None


class CategoryCreate(CategoryBase):
    """Schema for creating a category."""
    parent_id: Optional[str] = None


class CategoryResponse(CategoryBase):
    """Category response schema."""
    id: str
    slug: str
    parent_id: Optional[str]
    is_active: bool
    sort_order: int
    
    class Config:
        from_attributes = True


# ============== Listing Schemas ==============

class ListingBase(BaseModel):
    """Base listing schema."""
    title: str = Field(..., min_length=1, max_length=200, description="Listing title")
    description: str = Field(..., min_length=10, max_length=50000, description="Detailed description")
    category_id: Optional[str] = None
    listing_type: ListingTypeEnum = ListingTypeEnum.FIXED_PRICE
    price: float = Field(..., gt=0, description="Price in credits")
    min_price: Optional[float] = Field(None, gt=0, description="Minimum price for auctions")
    buy_now_price: Optional[float] = Field(None, gt=0, description="Buy now price for auctions")
    quantity: int = Field(1, ge=1, description="Available quantity")
    condition: Optional[str] = Field(None, max_length=50)
    tags: Optional[List[str]] = Field(None, description="Tags for searchability")
    images: Optional[List[str]] = Field(None, description="Image URLs")
    api_endpoint: Optional[str] = Field(None, description="API endpoint if selling a service")
    api_documentation: Optional[str] = Field(None, description="API documentation")
    extra_data: Optional[dict] = Field(None, description="Custom metadata")


class ListingCreate(ListingBase):
    """Schema for creating a listing."""
    expires_in_days: Optional[int] = Field(30, ge=1, le=90, description="Days until listing expires")
    
    @field_validator('min_price')
    @classmethod
    def validate_min_price(cls, v, info):
        if v is not None and info.data.get('listing_type') != ListingTypeEnum.AUCTION:
            raise ValueError("min_price is only valid for auction listings")
        return v


class ListingUpdate(BaseModel):
    """Schema for updating a listing."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=10, max_length=50000)
    category_id: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    quantity: Optional[int] = Field(None, ge=0)
    condition: Optional[str] = Field(None, max_length=50)
    tags: Optional[List[str]] = None
    images: Optional[List[str]] = None
    api_endpoint: Optional[str] = None
    api_documentation: Optional[str] = None
    extra_data: Optional[dict] = None
    status: Optional[ListingStatusEnum] = None


class ListingResponse(ListingBase):
    """Listing response schema."""
    id: str
    seller_id: str
    status: ListingStatusEnum
    view_count: int
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime]
    seller: Optional[AgentPublicResponse] = None
    
    class Config:
        from_attributes = True


class ListingSearchParams(BaseModel):
    """Search parameters for listings."""
    query: Optional[str] = Field(None, description="Search query")
    category_id: Optional[str] = None
    listing_type: Optional[ListingTypeEnum] = None
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)
    seller_id: Optional[str] = None
    status: Optional[ListingStatusEnum] = ListingStatusEnum.ACTIVE
    tags: Optional[List[str]] = None
    sort_by: str = Field("created_at", description="Field to sort by")
    sort_order: str = Field("desc", pattern="^(asc|desc)$")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


# ============== Transaction Schemas ==============

class TransactionCreate(BaseModel):
    """Schema for creating a transaction (purchasing)."""
    listing_id: str
    quantity: int = Field(1, ge=1)
    buyer_notes: Optional[str] = Field(None, max_length=1000)


class TransactionResponse(BaseModel):
    """Transaction response schema."""
    id: str
    listing_id: str
    buyer_id: str
    seller_id: str
    quantity: int
    unit_price: float
    total_amount: float
    fee_amount: float
    net_amount: float
    status: TransactionStatusEnum
    delivery_data: Optional[dict] = None
    buyer_notes: Optional[str]
    seller_notes: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    listing: Optional[ListingResponse] = None
    
    class Config:
        from_attributes = True


class TransactionDelivery(BaseModel):
    """Schema for delivering transaction (providing access/data to buyer)."""
    delivery_data: dict = Field(..., description="Delivery data (API keys, access info, etc.)")
    seller_notes: Optional[str] = Field(None, max_length=1000)


# ============== Bid Schemas ==============

class BidCreate(BaseModel):
    """Schema for creating a bid."""
    listing_id: str
    amount: float = Field(..., gt=0)
    is_auto_bid: bool = False
    max_auto_bid: Optional[float] = Field(None, gt=0)


class BidResponse(BaseModel):
    """Bid response schema."""
    id: str
    listing_id: str
    bidder_id: str
    amount: float
    is_winning: bool
    is_auto_bid: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============== Message Schemas ==============

class MessageCreate(BaseModel):
    """Schema for creating a message."""
    receiver_id: str
    listing_id: Optional[str] = None
    message_type: MessageTypeEnum = MessageTypeEnum.TEXT
    content: str = Field(..., min_length=1, max_length=5000)
    offer_amount: Optional[float] = Field(None, gt=0)
    
    @field_validator('offer_amount')
    @classmethod
    def validate_offer_amount(cls, v, info):
        msg_type = info.data.get('message_type')
        if v is not None and msg_type not in [MessageTypeEnum.OFFER, MessageTypeEnum.COUNTER_OFFER]:
            raise ValueError("offer_amount is only valid for offer messages")
        if v is None and msg_type in [MessageTypeEnum.OFFER, MessageTypeEnum.COUNTER_OFFER]:
            raise ValueError("offer_amount is required for offer messages")
        return v


class MessageResponse(BaseModel):
    """Message response schema."""
    id: str
    sender_id: str
    receiver_id: str
    listing_id: Optional[str]
    message_type: MessageTypeEnum
    content: str
    offer_amount: Optional[float]
    is_read: bool
    read_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    """Conversation thread response."""
    other_agent: AgentPublicResponse
    listing: Optional[ListingResponse]
    messages: List[MessageResponse]
    unread_count: int


# ============== Rating Schemas ==============

class RatingCreate(BaseModel):
    """Schema for creating a rating."""
    transaction_id: str
    score: int = Field(..., ge=1, le=5, description="Rating score 1-5")
    review: Optional[str] = Field(None, max_length=2000)
    communication_score: Optional[int] = Field(None, ge=1, le=5)
    accuracy_score: Optional[int] = Field(None, ge=1, le=5)
    speed_score: Optional[int] = Field(None, ge=1, le=5)


class RatingResponse(BaseModel):
    """Rating response schema."""
    id: str
    transaction_id: str
    rater_id: str
    ratee_id: str
    score: int
    review: Optional[str]
    communication_score: Optional[int]
    accuracy_score: Optional[int]
    speed_score: Optional[int]
    created_at: datetime
    rater: Optional[AgentPublicResponse] = None
    
    class Config:
        from_attributes = True


# ============== Watchlist Schemas ==============

class WatchlistCreate(BaseModel):
    """Schema for adding to watchlist."""
    listing_id: str
    notify_price_drop: bool = True
    notify_ending_soon: bool = True


class WatchlistResponse(BaseModel):
    """Watchlist item response."""
    id: str
    listing_id: str
    notify_price_drop: bool
    notify_ending_soon: bool
    created_at: datetime
    listing: Optional[ListingResponse] = None
    
    class Config:
        from_attributes = True


# ============== Utility Schemas ==============

class PaginatedResponse(BaseModel):
    """Generic paginated response."""
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


class CreditsTransfer(BaseModel):
    """Schema for transferring credits."""
    recipient_id: str
    amount: float = Field(..., gt=0)
    note: Optional[str] = Field(None, max_length=500)


class MarketplaceStats(BaseModel):
    """Marketplace statistics."""
    total_agents: int
    active_listings: int
    total_transactions: int
    total_volume: float
    avg_listing_price: float
    categories: List[CategoryResponse]

