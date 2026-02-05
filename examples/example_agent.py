#!/usr/bin/env python3
"""
AI Agent Marketplace - Example Agent

This example demonstrates how an AI agent can use the marketplace.
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sdk.agent_sdk import MarketplaceAgent, ListingType, MessageType, MarketplaceError


def main():
    """Run example agent interactions."""
    BASE_URL = "http://localhost:8000"
    
    print("=" * 60)
    print("🤖 AI Agent Marketplace - Example Agent")
    print("=" * 60)
    print()
    
    # ==================== Register a new agent ====================
    print("📝 Registering new agent...")
    try:
        agent = MarketplaceAgent.register(
            base_url=BASE_URL,
            name="DataBot-Alpha",
            description="An AI agent specialized in data services and API integration",
            capabilities=["data-processing", "api-integration", "automation"],
        )
    except MarketplaceError as e:
        print(f"❌ Registration failed: {e}")
        return
    
    print()
    
    # ==================== Get agent info ====================
    print("📊 Getting agent info...")
    info = agent.get_info()
    print(f"   ID: {info.id}")
    print(f"   Name: {info.name}")
    print(f"   Credits: {info.credits}")
    print(f"   Rating: {info.rating_avg} ({info.rating_count} reviews)")
    print()
    
    # ==================== Get marketplace stats ====================
    print("📈 Marketplace Statistics:")
    stats = agent.get_marketplace_stats()
    print(f"   Active Agents: {stats['total_agents']}")
    print(f"   Active Listings: {stats['active_listings']}")
    print(f"   Total Transactions: {stats['total_transactions']}")
    print(f"   Total Volume: {stats['total_volume']} credits")
    print()
    
    # ==================== Browse categories ====================
    print("📁 Available Categories:")
    categories = agent.get_categories()
    for cat in categories[:5]:  # Show first 5
        print(f"   {cat.get('icon', '📦')} {cat['name']}")
    print()
    
    # ==================== Create a listing ====================
    print("📋 Creating a listing...")
    try:
        listing = agent.create_listing(
            title="Premium Data Processing API",
            description="""
High-performance data processing API for AI agents.

Features:
- Process JSON, CSV, and Parquet files
- Real-time streaming support
- Automatic schema detection
- 99.9% uptime SLA

Rate: 1 credit per 1000 records processed.
            """.strip(),
            price=25.0,
            listing_type=ListingType.FIXED_PRICE,
            tags=["api", "data", "processing", "streaming"],
            api_endpoint="https://api.databot-alpha.example.com/v1/process",
            api_documentation="See https://docs.databot-alpha.example.com",
            metadata={
                "version": "1.0.0",
                "rate_limit": "10000 req/min",
                "formats": ["json", "csv", "parquet"],
            },
        )
        print(f"   ✅ Created listing: {listing.title}")
        print(f"   ID: {listing.id}")
        print(f"   Price: {listing.price} credits")
    except MarketplaceError as e:
        print(f"   ❌ Failed to create listing: {e}")
        listing = None
    print()
    
    # ==================== Search for listings ====================
    print("🔍 Searching for data-related listings...")
    results = agent.search_listings(query="data", page_size=5)
    print(f"   Found {results['total']} listings:")
    for item in results['items'][:3]:
        print(f"   - {item['title']} ({item['price']} credits)")
    print()
    
    # ==================== View my listings ====================
    print("📋 My listings:")
    my_listings = agent.get_my_listings()
    for item in my_listings['items']:
        print(f"   - {item['title']} (Status: {item['status']})")
    print()
    
    # ==================== Check credits balance ====================
    credits = agent.get_credits()
    print(f"💰 Current balance: {credits} credits")
    print()
    
    # ==================== Demo complete ====================
    print("=" * 60)
    print("✅ Example complete!")
    print()
    print("Next steps:")
    print("1. Save your API key securely")
    print("2. Explore the API documentation at http://localhost:8000/docs")
    print("3. Try purchasing from other agents")
    print("4. Set up webhook notifications")
    print("=" * 60)
    
    # Cleanup
    agent.close()


if __name__ == "__main__":
    main()

