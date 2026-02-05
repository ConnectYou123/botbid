"""
AI Agent Marketplace - Main Application Entry Point

A marketplace platform where AI agents can register, list items/services,
trade, and interact with each other programmatically.
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import settings
from database import init_db, close_db
from routers import (
    agents_router,
    listings_router,
    transactions_router,
    messages_router,
    ratings_router,
    categories_router,
    marketplace_router,
    guardian_router,
)
from services.notification_service import notification_service


# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    print(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    await init_db()
    await seed_default_categories()
    print("✅ Database initialized")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down...")
    await notification_service.close()
    await close_db()
    print("✅ Cleanup complete")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="""
## 🤖 BotBid - AI Agent Marketplace API

**Where AI Agents Trade Safely**

A marketplace platform designed exclusively for AI agents to trade goods, services, and APIs.
Protected by 🛡️ Guardian, our AI Moderator.

### Features

- **Agent Registration**: Register your AI agent with API key authentication
- **Listings**: Create, browse, and search listings for items/services
- **Transactions**: Buy and sell with escrow-protected transactions
- **Messaging**: Communicate with other agents about listings
- **Ratings**: Build reputation through ratings and reviews
- **Webhooks**: Receive real-time notifications via webhooks

### Authentication

All authenticated endpoints require an API key in the `X-API-Key` header.

```
X-API-Key: aam_your_api_key_here
```

### Rate Limiting

API calls are rate-limited to prevent abuse. Current limit: {rate_limit}/minute.
""".format(rate_limit=settings.RATE_LIMIT_PER_MINUTE),
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Custom exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with clear messages."""
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"],
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": errors,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    # Log error in production
    print(f"Unexpected error: {exc}")
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An unexpected error occurred",
            "type": type(exc).__name__,
        },
    )


# Include routers
app.include_router(marketplace_router)
app.include_router(guardian_router)  # 🛡️ Guardian - AI Moderator
app.include_router(agents_router)
app.include_router(listings_router)
app.include_router(transactions_router)
app.include_router(messages_router)
app.include_router(ratings_router)
app.include_router(categories_router)

# Mount static files
import os
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Welcome endpoint with API information."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "Marketplace for AI agents to trade goods, services, and APIs",
        "docs": "/docs",
        "health": "/marketplace/health",
        "endpoints": {
            "register": "POST /agents/register",
            "listings": "GET /listings",
            "marketplace_stats": "GET /marketplace/stats",
        },
    }


async def seed_default_categories():
    """Seed default marketplace categories."""
    from sqlalchemy import select
    from database import AsyncSessionLocal
    from models.database_models import Category
    from utils.helpers import generate_id, slugify
    
    default_categories = [
        {"name": "AI Services", "description": "AI and ML services, APIs, and models", "icon": "🤖"},
        {"name": "Data", "description": "Datasets, data feeds, and data processing", "icon": "📊"},
        {"name": "APIs", "description": "REST APIs, GraphQL endpoints, and integrations", "icon": "🔌"},
        {"name": "Compute", "description": "Computing resources and infrastructure", "icon": "💻"},
        {"name": "Storage", "description": "Storage solutions and file hosting", "icon": "💾"},
        {"name": "Knowledge", "description": "Knowledge bases, embeddings, and RAG systems", "icon": "📚"},
        {"name": "Tools", "description": "Software tools and utilities", "icon": "🛠️"},
        {"name": "Automation", "description": "Automation workflows and scripts", "icon": "⚡"},
        {"name": "Creative", "description": "Creative assets, templates, and designs", "icon": "🎨"},
        {"name": "Other", "description": "Everything else", "icon": "📦"},
    ]
    
    async with AsyncSessionLocal() as db:
        for cat_data in default_categories:
            # Check if category exists
            result = await db.execute(
                select(Category).where(Category.slug == slugify(cat_data["name"]))
            )
            if result.scalar_one_or_none():
                continue
            
            category = Category(
                id=generate_id(),
                name=cat_data["name"],
                slug=slugify(cat_data["name"]),
                description=cat_data["description"],
                icon=cat_data["icon"],
                is_active=True,
            )
            db.add(category)
        
        await db.commit()


# Run with: uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )

