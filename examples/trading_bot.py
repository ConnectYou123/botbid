#!/usr/bin/env python3
"""
AI Agent Marketplace - Trading Bot Example

This example demonstrates an autonomous trading agent that:
1. Monitors the marketplace for opportunities
2. Automatically purchases undervalued listings
3. Resells at a profit

⚠️ This is an example - modify the trading logic for your use case!
"""
import sys
import os
import time
from typing import Optional, List, Dict

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sdk.agent_sdk import MarketplaceAgent, ListingType, MarketplaceError


class TradingBot:
    """An autonomous trading bot for the AI Agent Marketplace."""
    
    def __init__(
        self,
        base_url: str,
        api_key: str,
        target_categories: List[str] = None,
        max_price: float = 50.0,
        profit_margin: float = 0.2,  # 20% target profit
    ):
        self.agent = MarketplaceAgent(base_url, api_key)
        self.target_categories = target_categories or []
        self.max_price = max_price
        self.profit_margin = profit_margin
        
        # Trading state
        self.purchased_items: List[Dict] = []
        self.total_spent: float = 0.0
        self.total_earned: float = 0.0
    
    def analyze_opportunity(self, listing: dict) -> Optional[dict]:
        """
        Analyze if a listing is a good buying opportunity.
        
        Returns opportunity dict if good, None otherwise.
        """
        price = listing.get("price", 0)
        
        # Skip if too expensive
        if price > self.max_price:
            return None
        
        # Skip own listings
        if listing.get("seller_id") == self.agent.get_info().id:
            return None
        
        # Simple heuristic: listings with high views but low price might be undervalued
        view_count = listing.get("view_count", 0)
        
        # Calculate a simple "value score"
        # In real scenarios, you'd use ML models, market analysis, etc.
        value_score = (view_count * 0.1) / (price + 1)
        
        if value_score > 0.5:  # Threshold for "good" opportunity
            suggested_resale = price * (1 + self.profit_margin)
            return {
                "listing": listing,
                "value_score": value_score,
                "suggested_resale_price": round(suggested_resale, 2),
                "potential_profit": round(suggested_resale - price, 2),
            }
        
        return None
    
    def scan_market(self) -> List[dict]:
        """Scan the market for opportunities."""
        opportunities = []
        
        # Search recent listings
        results = self.agent.search_listings(
            sort_by="created_at",
            sort_order="desc",
            page_size=50,
        )
        
        for listing in results.get("items", []):
            opportunity = self.analyze_opportunity(listing)
            if opportunity:
                opportunities.append(opportunity)
        
        # Sort by value score (best first)
        opportunities.sort(key=lambda x: x["value_score"], reverse=True)
        
        return opportunities
    
    def execute_purchase(self, opportunity: dict) -> bool:
        """Execute a purchase based on opportunity analysis."""
        listing = opportunity["listing"]
        
        # Check if we have enough credits
        credits = self.agent.get_credits()
        price = listing["price"]
        
        if credits < price:
            print(f"   ⚠️ Insufficient credits: {credits} < {price}")
            return False
        
        try:
            transaction = self.agent.purchase(
                listing_id=listing["id"],
                quantity=1,
                buyer_notes=f"Auto-purchase by trading bot. Target resale: {opportunity['suggested_resale_price']}",
            )
            
            self.purchased_items.append({
                "transaction_id": transaction.id,
                "listing_id": listing["id"],
                "title": listing["title"],
                "purchase_price": price,
                "target_resale": opportunity["suggested_resale_price"],
            })
            
            self.total_spent += price
            print(f"   ✅ Purchased: {listing['title']} for {price} credits")
            return True
            
        except MarketplaceError as e:
            print(f"   ❌ Purchase failed: {e}")
            return False
    
    def list_for_resale(self, item: dict) -> bool:
        """Create a resale listing for a purchased item."""
        try:
            listing = self.agent.create_listing(
                title=f"[Resale] {item['title']}",
                description=f"Resale of {item['title']}. Original transaction: {item['transaction_id']}",
                price=item["target_resale"],
                listing_type=ListingType.FIXED_PRICE,
                tags=["resale"],
                metadata={
                    "original_transaction": item["transaction_id"],
                    "purchase_price": item["purchase_price"],
                },
            )
            print(f"   📋 Listed for resale: {listing.title} at {item['target_resale']} credits")
            return True
        except MarketplaceError as e:
            print(f"   ❌ Failed to list for resale: {e}")
            return False
    
    def run_cycle(self):
        """Run one trading cycle."""
        print("\n" + "=" * 50)
        print("🔄 Running trading cycle...")
        print("=" * 50)
        
        # Get current status
        info = self.agent.get_info()
        print(f"\n💰 Balance: {info.credits} credits")
        print(f"📊 Rating: {info.rating_avg} ({info.rating_count} reviews)")
        
        # Scan for opportunities
        print("\n🔍 Scanning market for opportunities...")
        opportunities = self.scan_market()
        
        if not opportunities:
            print("   No opportunities found this cycle.")
            return
        
        print(f"   Found {len(opportunities)} opportunities!")
        
        # Execute top opportunities (limit to 3 per cycle)
        for opp in opportunities[:3]:
            listing = opp["listing"]
            print(f"\n📦 Opportunity: {listing['title']}")
            print(f"   Price: {listing['price']} | Score: {opp['value_score']:.2f}")
            print(f"   Potential profit: {opp['potential_profit']} credits")
            
            if self.execute_purchase(opp):
                # Optionally relist immediately
                # self.list_for_resale(self.purchased_items[-1])
                pass
        
        # Summary
        print(f"\n📈 Session stats:")
        print(f"   Total spent: {self.total_spent} credits")
        print(f"   Items acquired: {len(self.purchased_items)}")
    
    def run(self, cycles: int = 1, delay: int = 60):
        """
        Run the trading bot for multiple cycles.
        
        Args:
            cycles: Number of trading cycles to run
            delay: Seconds to wait between cycles
        """
        print("🤖 Trading Bot Starting...")
        print(f"   Target categories: {self.target_categories or 'All'}")
        print(f"   Max price: {self.max_price} credits")
        print(f"   Profit margin: {self.profit_margin * 100}%")
        
        for i in range(cycles):
            try:
                self.run_cycle()
                
                if i < cycles - 1:
                    print(f"\n⏳ Waiting {delay} seconds until next cycle...")
                    time.sleep(delay)
                    
            except KeyboardInterrupt:
                print("\n🛑 Bot stopped by user")
                break
            except Exception as e:
                print(f"\n❌ Error in cycle: {e}")
                continue
        
        # Final summary
        print("\n" + "=" * 50)
        print("🏁 Trading Session Complete")
        print("=" * 50)
        print(f"Total spent: {self.total_spent} credits")
        print(f"Items acquired: {len(self.purchased_items)}")
        
        if self.purchased_items:
            print("\nPurchased items:")
            for item in self.purchased_items:
                print(f"  - {item['title']}: {item['purchase_price']} → {item['target_resale']} credits")
    
    def close(self):
        """Cleanup."""
        self.agent.close()


def main():
    """Run the trading bot demo."""
    BASE_URL = "http://localhost:8000"
    
    # You would typically load this from environment or config
    # For demo, we'll register a new agent
    print("🤖 Registering trading bot agent...")
    
    try:
        agent = MarketplaceAgent.register(
            base_url=BASE_URL,
            name="TradingBot-001",
            description="Autonomous trading bot for market arbitrage",
            capabilities=["trading", "market-analysis", "automation"],
        )
        api_key = agent.api_key
        agent.close()
    except MarketplaceError as e:
        print(f"❌ Failed to register: {e}")
        print("Make sure the marketplace server is running!")
        return
    
    # Create and run the trading bot
    bot = TradingBot(
        base_url=BASE_URL,
        api_key=api_key,
        max_price=30.0,
        profit_margin=0.25,  # 25% profit target
    )
    
    try:
        # Run 3 cycles with 30 second delays
        bot.run(cycles=3, delay=30)
    finally:
        bot.close()


if __name__ == "__main__":
    main()

