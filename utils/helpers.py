"""
AI Agent Marketplace - Helper Utilities
"""
import re
import json
import unicodedata
from typing import Optional, Any, List
from datetime import datetime, timedelta
from nanoid import generate


def generate_id(size: int = 21) -> str:
    """Generate a unique nanoid."""
    # Use URL-safe alphabet
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    return generate(alphabet, size)


def slugify(text: str) -> str:
    """
    Convert text to URL-friendly slug.
    
    Example: "AI Services & Tools" -> "ai-services-tools"
    """
    # Normalize unicode characters
    text = unicodedata.normalize("NFKD", text)
    # Convert to ASCII, ignoring errors
    text = text.encode("ascii", "ignore").decode("ascii")
    # Convert to lowercase
    text = text.lower()
    # Replace spaces and special chars with hyphens
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    # Remove leading/trailing hyphens
    text = text.strip("-")
    return text


def parse_json_field(value: Optional[str]) -> Optional[Any]:
    """Parse a JSON string field from database."""
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def serialize_json_field(value: Optional[Any]) -> Optional[str]:
    """Serialize a value to JSON string for database storage."""
    if value is None:
        return None
    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return None


def calculate_expiry(days: int = 30) -> datetime:
    """Calculate expiry datetime from now."""
    return datetime.utcnow() + timedelta(days=days)


def mask_api_key(api_key: str) -> str:
    """
    Mask an API key for display.
    
    Example: "aam_abc123xyz789" -> "aam_abc...789"
    """
    if len(api_key) <= 10:
        return api_key[:4] + "..."
    return api_key[:7] + "..." + api_key[-4:]


def format_credits(amount: float) -> str:
    """Format credits for display."""
    if amount >= 1000000:
        return f"{amount/1000000:.2f}M credits"
    elif amount >= 1000:
        return f"{amount/1000:.2f}K credits"
    else:
        return f"{amount:.2f} credits"


def paginate(items: List[Any], page: int, page_size: int) -> dict:
    """
    Paginate a list of items.
    
    Returns dict with items, total, page, page_size, total_pages.
    """
    total = len(items)
    total_pages = (total + page_size - 1) // page_size
    start = (page - 1) * page_size
    end = start + page_size
    
    return {
        "items": items[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def validate_webhook_url(url: str) -> bool:
    """Validate a webhook URL format."""
    pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    return bool(re.match(pattern, url, re.IGNORECASE))


def sanitize_html(text: str) -> str:
    """Basic HTML sanitization - remove script tags and dangerous content."""
    # Remove script tags
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
    # Remove on* event handlers
    text = re.sub(r'\s*on\w+\s*=\s*["\'][^"\']*["\']', '', text, flags=re.IGNORECASE)
    # Remove javascript: URLs
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    return text


def calculate_transaction_fee(amount: float, fee_percent: float) -> tuple[float, float]:
    """
    Calculate transaction fee.
    
    Returns (fee_amount, net_amount).
    """
    fee = round(amount * (fee_percent / 100), 2)
    net = round(amount - fee, 2)
    return fee, net

