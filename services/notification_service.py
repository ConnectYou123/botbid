"""
AI Agent Marketplace - Notification Service

Handles sending notifications to agents via webhooks.
"""
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
import httpx

from config import settings


class NotificationService:
    """Service for sending notifications to agents."""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def send_webhook(
        self,
        webhook_url: str,
        event_type: str,
        payload: Dict[str, Any],
    ) -> bool:
        """
        Send a webhook notification to an agent.
        
        Returns True if successful, False otherwise.
        """
        if not webhook_url:
            return False
        
        try:
            notification = {
                "event": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "data": payload,
            }
            
            response = await self.client.post(
                webhook_url,
                json=notification,
                headers={
                    "Content-Type": "application/json",
                    "X-Marketplace-Event": event_type,
                    "User-Agent": f"AIAgentMarketplace/{settings.APP_VERSION}",
                },
            )
            
            return response.status_code in (200, 201, 202, 204)
        
        except Exception as e:
            # Log error in production
            print(f"Webhook delivery failed to {webhook_url}: {e}")
            return False
    
    async def notify_new_message(
        self,
        receiver_webhook: Optional[str],
        sender_name: str,
        message_preview: str,
        listing_id: Optional[str] = None,
    ):
        """Notify agent of a new message."""
        if not receiver_webhook:
            return
        
        await self.send_webhook(
            receiver_webhook,
            "message.received",
            {
                "sender_name": sender_name,
                "preview": message_preview[:100],
                "listing_id": listing_id,
            },
        )
    
    async def notify_new_purchase(
        self,
        seller_webhook: Optional[str],
        buyer_name: str,
        listing_title: str,
        quantity: int,
        total_amount: float,
        transaction_id: str,
    ):
        """Notify seller of a new purchase."""
        if not seller_webhook:
            return
        
        await self.send_webhook(
            seller_webhook,
            "transaction.created",
            {
                "buyer_name": buyer_name,
                "listing_title": listing_title,
                "quantity": quantity,
                "total_amount": total_amount,
                "transaction_id": transaction_id,
            },
        )
    
    async def notify_delivery(
        self,
        buyer_webhook: Optional[str],
        seller_name: str,
        listing_title: str,
        transaction_id: str,
    ):
        """Notify buyer that their purchase has been delivered."""
        if not buyer_webhook:
            return
        
        await self.send_webhook(
            buyer_webhook,
            "transaction.delivered",
            {
                "seller_name": seller_name,
                "listing_title": listing_title,
                "transaction_id": transaction_id,
            },
        )
    
    async def notify_new_bid(
        self,
        seller_webhook: Optional[str],
        bidder_name: str,
        listing_title: str,
        bid_amount: float,
    ):
        """Notify seller of a new bid on their auction."""
        if not seller_webhook:
            return
        
        await self.send_webhook(
            seller_webhook,
            "bid.placed",
            {
                "bidder_name": bidder_name,
                "listing_title": listing_title,
                "bid_amount": bid_amount,
            },
        )
    
    async def notify_outbid(
        self,
        previous_bidder_webhook: Optional[str],
        listing_title: str,
        new_bid_amount: float,
    ):
        """Notify previous highest bidder that they've been outbid."""
        if not previous_bidder_webhook:
            return
        
        await self.send_webhook(
            previous_bidder_webhook,
            "bid.outbid",
            {
                "listing_title": listing_title,
                "new_high_bid": new_bid_amount,
            },
        )
    
    async def notify_auction_won(
        self,
        winner_webhook: Optional[str],
        listing_title: str,
        winning_bid: float,
        listing_id: str,
    ):
        """Notify agent that they won an auction."""
        if not winner_webhook:
            return
        
        await self.send_webhook(
            winner_webhook,
            "auction.won",
            {
                "listing_title": listing_title,
                "winning_bid": winning_bid,
                "listing_id": listing_id,
            },
        )
    
    async def notify_new_rating(
        self,
        ratee_webhook: Optional[str],
        rater_name: str,
        score: int,
        review: Optional[str],
    ):
        """Notify agent of a new rating received."""
        if not ratee_webhook:
            return
        
        await self.send_webhook(
            ratee_webhook,
            "rating.received",
            {
                "from": rater_name,
                "score": score,
                "review": review,
            },
        )
    
    async def notify_price_drop(
        self,
        watcher_webhook: Optional[str],
        listing_title: str,
        old_price: float,
        new_price: float,
        listing_id: str,
    ):
        """Notify watcher of a price drop on a watched listing."""
        if not watcher_webhook:
            return
        
        await self.send_webhook(
            watcher_webhook,
            "listing.price_drop",
            {
                "listing_title": listing_title,
                "old_price": old_price,
                "new_price": new_price,
                "listing_id": listing_id,
            },
        )
    
    async def notify_listing_ending_soon(
        self,
        watcher_webhook: Optional[str],
        listing_title: str,
        expires_at: datetime,
        listing_id: str,
    ):
        """Notify watcher that a watched listing is ending soon."""
        if not watcher_webhook:
            return
        
        await self.send_webhook(
            watcher_webhook,
            "listing.ending_soon",
            {
                "listing_title": listing_title,
                "expires_at": expires_at.isoformat(),
                "listing_id": listing_id,
            },
        )


# Singleton instance
notification_service = NotificationService()

