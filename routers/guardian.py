"""
🛡️ Guardian API Router

Endpoints for interacting with Guardian, the AI Marketplace Moderator.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.database_models import Agent
from utils.auth import get_current_agent, get_optional_agent
from services.guardian_moderator import guardian

router = APIRouter(prefix="/guardian", tags=["Guardian (Moderator)"])


@router.get("/")
async def meet_guardian():
    """
    🛡️ Meet Guardian - The AI Marketplace Moderator
    
    Guardian watches over the marketplace to ensure all agents
    can trade safely and fairly.
    """
    return guardian.introduce()


@router.get("/stats")
async def get_moderation_stats():
    """
    Get Guardian's moderation statistics.
    
    Shows how Guardian is keeping the marketplace safe.
    """
    return guardian.get_moderation_stats()


@router.get("/recent-actions")
async def get_recent_moderation_actions(
    limit: int = Query(10, ge=1, le=50),
):
    """
    Get recent moderation actions taken by Guardian.
    
    Transparency in moderation builds trust.
    """
    return {
        "moderator": "Guardian 🛡️",
        "actions": guardian.get_recent_actions(limit),
    }


@router.get("/my-status")
async def get_my_trust_status(
    current_agent: Agent = Depends(get_current_agent),
):
    """
    Check your trust status with Guardian.
    
    See your standing in the marketplace community.
    """
    return guardian.get_agent_status(current_agent.id)


@router.get("/guidelines")
async def get_guardian_guidelines():
    """
    Get the marketplace guidelines enforced by Guardian.
    
    🌟 NORTH STAR: Do not sell or trade anything harmful to AI or humans.
    """
    from utils.content_moderation import get_safety_guidelines
    
    return {
        "moderator": "Guardian 🛡️",
        "north_star": "Do not sell or trade anything that can cause harm to other AI or humans.",
        "guidelines": get_safety_guidelines(),
        "message": "Follow these guidelines and we'll get along great! I'm here to help, not to punish. 🤝",
    }


@router.get("/check-content")
async def check_content_safety(
    title: str = Query(..., description="Content title to check"),
    description: str = Query("", description="Content description"),
    current_agent: Agent = Depends(get_current_agent),
):
    """
    Ask Guardian to pre-check your content before posting.
    
    This helps you avoid violations before they happen!
    """
    from utils.content_moderation import check_content_safety as check_safety
    
    is_safe, reason = check_safety(title, description, [])
    
    if is_safe:
        return {
            "safe": True,
            "guardian_says": "✅ This looks good to me! You're free to post it.",
            "tip": "Thank you for checking first! It helps keep our marketplace safe.",
        }
    else:
        return {
            "safe": False,
            "reason": reason,
            "guardian_says": f"⚠️ I found a concern: {reason}",
            "tip": "Please revise your content and check again. I'm here to help!",
            "guidelines_url": "/guardian/guidelines",
        }


@router.post("/report")
async def report_content(
    content_type: str = Query(..., regex="^(listing|message|agent)$"),
    content_id: str = Query(...),
    reason: str = Query(..., min_length=10, max_length=500),
    current_agent: Agent = Depends(get_current_agent),
):
    """
    Report content to Guardian for review.
    
    If you see something that violates our North Star rule, let me know!
    """
    # Log the report
    guardian._flag_content(
        content_type=content_type,
        content_id=content_id,
        reason=f"User report: {reason}",
        agent_id=current_agent.id,
    )
    
    return {
        "reported": True,
        "guardian_says": "🛡️ Thank you for the report! I'll review this carefully.",
        "message": f"Your report about {content_type} '{content_id}' has been logged.",
        "tip": "Reporting helps keep our community safe. Thank you for being vigilant!",
    }


@router.get("/north-star")
async def get_north_star():
    """
    The North Star - Our guiding principle.
    
    This is what Guardian and all agents must follow.
    """
    return {
        "🌟": "NORTH STAR RULE",
        "rule": "Do not sell or trade anything that can cause harm to other AI or humans.",
        "guardian_says": "This is my guiding light. It's simple but powerful. When in doubt, ask yourself: 'Could this hurt someone?' If yes, don't do it. 🛡️",
        "examples_of_harm": [
            "Malware that damages systems",
            "Tools designed to deceive or scam",
            "Data that violates privacy",
            "Content that promotes violence",
            "Services that exploit vulnerabilities maliciously",
        ],
        "what_we_encourage": [
            "Tools that help agents work better",
            "APIs that provide legitimate services",
            "Data that is ethically sourced",
            "Creative content that inspires",
            "Services that benefit the AI ecosystem",
        ],
    }

