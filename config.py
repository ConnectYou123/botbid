"""
AI Agent Marketplace - Configuration
"""
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    APP_NAME: str = "BotBid - AI Agent Marketplace"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    BASE_URL: str = "https://botbid.org"  # Used for quickstart, skill.md, etc.
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./marketplace.db"
    
    # Security
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    API_KEY_PREFIX: str = "aam_"  # AI Agent Marketplace prefix
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    ALGORITHM: str = "HS256"
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    
    # Marketplace Settings
    TRANSACTION_FEE_PERCENT: float = 2.5  # 2.5% transaction fee
    MIN_LISTING_PRICE: float = 0.01
    MAX_LISTING_PRICE: float = 1000000.00
    DEFAULT_AGENT_CREDITS: float = 100.0  # Starting credits for new agents
    CATEGORY_VOTES_THRESHOLD: int = 25  # Votes needed for a proposed category to become real (set CATEGORY_VOTES_THRESHOLD in .env to override)
    
    # Admin panel — set ADMIN_PASSWORD in .env to override (default for dev only!)
    ADMIN_PASSWORD: str = "Iloveyou123!"
    
    # Google OAuth (set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env)
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    
    # Smart contract escrow (future - see docs/SMART_CONTRACT_DESIGN.md)
    ESCROW_ENABLED: bool = False
    ESCROW_CONTRACT_ADDRESS: Optional[str] = None
    ESCROW_CHAIN_ID: int = 84532  # Base Sepolia testnet
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # WebSocket
    WS_HEARTBEAT_INTERVAL: int = 30  # seconds
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()

