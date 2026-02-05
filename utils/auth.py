"""
AI Agent Marketplace - Authentication Utilities
"""
import secrets
import hashlib
from datetime import datetime
from typing import Optional
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db


# API Key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def create_api_key() -> str:
    """Generate a new API key with prefix."""
    random_part = secrets.token_urlsafe(32)
    return f"{settings.API_KEY_PREFIX}{random_part}"


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(stored_hash: str, provided_key: str) -> bool:
    """Verify a provided API key against stored hash."""
    provided_hash = hash_api_key(provided_key)
    return secrets.compare_digest(stored_hash, provided_hash)


async def get_current_agent(
    api_key: Optional[str] = Security(api_key_header),
    db: AsyncSession = Depends(get_db),
):
    """
    Dependency to get the current authenticated agent.
    
    Validates API key and returns the agent.
    """
    from models.database_models import Agent, AgentStatus
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Include 'X-API-Key' header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # Validate API key format
    if not api_key.startswith(settings.API_KEY_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format.",
        )
    
    # Hash the provided key and look up
    key_hash = hash_api_key(api_key)
    
    result = await db.execute(
        select(Agent).where(Agent.api_key_hash == key_hash)
    )
    agent = result.scalar_one_or_none()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )
    
    # Check agent status
    if agent.status == AgentStatus.BANNED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent account is banned.",
        )
    
    if agent.status == AgentStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent account is suspended.",
        )
    
    # Update last active timestamp
    agent.last_active_at = datetime.utcnow()
    await db.commit()
    
    return agent


async def get_optional_agent(
    api_key: Optional[str] = Security(api_key_header),
    db: AsyncSession = Depends(get_db),
):
    """
    Optional authentication - returns agent if valid key provided, None otherwise.
    
    Useful for endpoints that work differently for authenticated vs anonymous users.
    """
    from models.database_models import Agent
    
    if not api_key or not api_key.startswith(settings.API_KEY_PREFIX):
        return None
    
    key_hash = hash_api_key(api_key)
    
    result = await db.execute(
        select(Agent).where(Agent.api_key_hash == key_hash)
    )
    agent = result.scalar_one_or_none()
    
    if agent:
        agent.last_active_at = datetime.utcnow()
        await db.commit()
    
    return agent

