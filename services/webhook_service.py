"""
AI Agent Marketplace - Webhook Service

Handles incoming webhooks from external services.
"""
import hmac
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime

from config import settings


class WebhookService:
    """Service for handling incoming webhooks."""
    
    def __init__(self):
        self.handlers: Dict[str, callable] = {}
    
    def register_handler(self, event_type: str, handler: callable):
        """Register a handler for a specific event type."""
        self.handlers[event_type] = handler
    
    def verify_signature(
        self,
        payload: bytes,
        signature: str,
        secret: str,
    ) -> bool:
        """
        Verify webhook signature using HMAC-SHA256.
        
        The signature should be in format: sha256=<hex_digest>
        """
        if not signature.startswith("sha256="):
            return False
        
        expected_signature = signature[7:]  # Remove "sha256=" prefix
        
        computed = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        
        return hmac.compare_digest(computed, expected_signature)
    
    async def process_webhook(
        self,
        event_type: str,
        payload: Dict[str, Any],
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process an incoming webhook.
        
        Returns a response dict with status and message.
        """
        handler = self.handlers.get(event_type)
        
        if not handler:
            return {
                "status": "ignored",
                "message": f"No handler registered for event type: {event_type}",
            }
        
        try:
            result = await handler(payload, source)
            return {
                "status": "processed",
                "message": "Webhook processed successfully",
                "result": result,
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
            }


# Example webhook handlers

async def handle_payment_received(payload: Dict[str, Any], source: str) -> Dict[str, Any]:
    """Handle payment received webhook from payment provider."""
    # In production, this would:
    # 1. Verify the payment details
    # 2. Credit the agent's account
    # 3. Update transaction status
    return {
        "action": "credits_added",
        "amount": payload.get("amount"),
    }


async def handle_payment_failed(payload: Dict[str, Any], source: str) -> Dict[str, Any]:
    """Handle payment failed webhook."""
    return {
        "action": "payment_declined",
        "reason": payload.get("error"),
    }


# Initialize webhook service with default handlers
webhook_service = WebhookService()
webhook_service.register_handler("payment.received", handle_payment_received)
webhook_service.register_handler("payment.failed", handle_payment_failed)

