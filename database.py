"""
AI Agent Marketplace - Database Configuration

Supports both SQLite (local dev) and PostgreSQL (production/Render).
Set DATABASE_URL env var to switch:
  - SQLite:     sqlite+aiosqlite:///./marketplace.db
  - PostgreSQL: postgresql+asyncpg://user:pass@host:5432/dbname
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from config import settings


def _make_url(raw: str) -> str:
    """Convert DATABASE_URL to async-compatible format."""
    url = raw.strip()
    # Render provides postgres:// but SQLAlchemy needs postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


db_url = _make_url(settings.DATABASE_URL)
is_postgres = "postgresql" in db_url

engine_kwargs = {
    "echo": settings.DEBUG,
    "future": True,
}
if is_postgres:
    engine_kwargs["poolclass"] = NullPool

engine = create_async_engine(db_url, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


async def get_db() -> AsyncSession:
    """Dependency that provides a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections."""
    await engine.dispose()
