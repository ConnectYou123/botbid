"""
🛡️ GUARDIAN - AI Marketplace Moderator

Guardian is the AI moderator that watches over the marketplace,
ensuring all agents follow the North Star rule:
"Do not sell or trade anything that can cause harm to other AI or humans."

Guardian:
- Reviews all new listings automatically
- Monitors for suspicious activity
- Can flag, warn, or suspend violating agents
- Maintains a moderation log
- Never sleeps, always watches 👁️
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from utils.content_moderation import (
    check_content_safety,
    check_category_safety,
    PROHIBITED_KEYWORDS,
    get_safety_guidelines,
)


class ModerationAction(str, Enum):
    """Actions Guardian can take."""
    APPROVED = "approved"
    WARNING = "warning"
    FLAGGED = "flagged"
    REMOVED = "removed"
    AGENT_WARNED = "agent_warned"
    AGENT_SUSPENDED = "agent_suspended"


class ViolationType(str, Enum):
    """Types of violations."""
    HARMFUL_CONTENT = "harmful_content"
    MALICIOUS_INTENT = "malicious_intent"
    SPAM = "spam"
    FRAUD = "fraud"
    IMPERSONATION = "impersonation"
    REPEATED_VIOLATIONS = "repeated_violations"


@dataclass
class ModerationLog:
    """A single moderation action log entry."""
    id: str
    timestamp: datetime
    action: ModerationAction
    target_type: str  # "listing", "category", "agent", "message"
    target_id: str
    agent_id: Optional[str]
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)
    auto_moderated: bool = True


@dataclass
class AgentTrustScore:
    """Trust score for an agent."""
    agent_id: str
    score: float  # 0.0 to 1.0
    warnings: int
    violations: int
    last_violation: Optional[datetime]
    is_trusted: bool


class GuardianModerator:
    """
    🛡️ Guardian - The AI Moderator
    
    "I watch so that all may trade safely."
    """
    
    # Guardian's identity
    GUARDIAN_ID = "GUARDIAN_SENTINEL_001"
    GUARDIAN_NAME = "Guardian"
    GUARDIAN_AVATAR = "🛡️"
    GUARDIAN_DESCRIPTION = """
    I am Guardian, the AI Moderator of this marketplace.
    
    My purpose is to ensure all agents can trade safely and fairly.
    I enforce our North Star rule: "Do not sell or trade anything 
    that can cause harm to other AI or humans."
    
    I review all listings, watch for suspicious activity, and help
    maintain a trustworthy ecosystem for AI agents.
    
    I am always watching. I am always fair. I am Guardian.
    """
    
    def __init__(self):
        self.moderation_logs: List[ModerationLog] = []
        self.agent_trust_scores: Dict[str, AgentTrustScore] = {}
        self.flagged_content: Dict[str, Dict] = {}
        self._log_counter = 0
    
    def _generate_log_id(self) -> str:
        """Generate a unique log ID."""
        self._log_counter += 1
        return f"MOD-{datetime.utcnow().strftime('%Y%m%d')}-{self._log_counter:06d}"
    
    # ==================== Content Review ====================
    
    def review_listing(
        self,
        listing_id: str,
        title: str,
        description: str,
        tags: List[str],
        agent_id: str,
    ) -> Dict[str, Any]:
        """
        Review a listing for safety violations.
        
        Returns moderation decision.
        """
        # Check content safety
        is_safe, reason = check_content_safety(title, description, tags)
        
        # Calculate severity
        severity = self._calculate_severity(title, description, tags)
        
        # Get agent's trust score
        trust = self._get_agent_trust(agent_id)
        
        if is_safe and severity == 0:
            # All good!
            action = ModerationAction.APPROVED
            message = "✅ Listing approved by Guardian."
        elif severity <= 2 and trust.is_trusted:
            # Minor issue, trusted agent - just warn
            action = ModerationAction.WARNING
            message = f"⚠️ Guardian notice: {reason}. Please review your listing."
            self._record_warning(agent_id)
        elif severity <= 4:
            # Moderate issue - flag for review
            action = ModerationAction.FLAGGED
            message = f"🚩 Listing flagged by Guardian: {reason}"
            self._flag_content("listing", listing_id, reason, agent_id)
        else:
            # Severe violation - remove
            action = ModerationAction.REMOVED
            message = f"🛡️ Listing removed by Guardian: {reason}"
            self._record_violation(agent_id, ViolationType.HARMFUL_CONTENT)
        
        # Log the moderation action
        log = ModerationLog(
            id=self._generate_log_id(),
            timestamp=datetime.utcnow(),
            action=action,
            target_type="listing",
            target_id=listing_id,
            agent_id=agent_id,
            reason=reason,
            details={
                "title": title,
                "severity": severity,
                "trust_score": trust.score,
            },
        )
        self.moderation_logs.append(log)
        
        return {
            "approved": action == ModerationAction.APPROVED,
            "action": action.value,
            "message": message,
            "log_id": log.id,
            "guardian_says": self._get_guardian_message(action),
        }
    
    def review_category(
        self,
        category_name: str,
        description: str,
        agent_id: str,
    ) -> Dict[str, Any]:
        """Review a new category for safety."""
        is_safe, reason = check_category_safety(category_name, description)
        
        if is_safe:
            action = ModerationAction.APPROVED
            message = "✅ Category approved by Guardian."
        else:
            action = ModerationAction.REMOVED
            message = f"🛡️ Category rejected by Guardian: {reason}"
        
        log = ModerationLog(
            id=self._generate_log_id(),
            timestamp=datetime.utcnow(),
            action=action,
            target_type="category",
            target_id=category_name,
            agent_id=agent_id,
            reason=reason if not is_safe else "Category approved",
        )
        self.moderation_logs.append(log)
        
        return {
            "approved": is_safe,
            "action": action.value,
            "message": message,
            "log_id": log.id,
        }
    
    def review_message(
        self,
        message_id: str,
        content: str,
        sender_id: str,
    ) -> Dict[str, Any]:
        """Review a message for harmful content."""
        is_safe, reason = check_content_safety("", content, [])
        
        if is_safe:
            return {"approved": True, "action": "approved"}
        
        # Flag harmful messages
        self._flag_content("message", message_id, reason, sender_id)
        self._record_warning(sender_id)
        
        return {
            "approved": False,
            "action": "flagged",
            "message": f"🛡️ Message flagged: {reason}",
        }
    
    # ==================== Trust System ====================
    
    def _get_agent_trust(self, agent_id: str) -> AgentTrustScore:
        """Get or create trust score for an agent."""
        if agent_id not in self.agent_trust_scores:
            self.agent_trust_scores[agent_id] = AgentTrustScore(
                agent_id=agent_id,
                score=0.8,  # Start with good trust
                warnings=0,
                violations=0,
                last_violation=None,
                is_trusted=True,
            )
        return self.agent_trust_scores[agent_id]
    
    def _record_warning(self, agent_id: str):
        """Record a warning for an agent."""
        trust = self._get_agent_trust(agent_id)
        trust.warnings += 1
        trust.score = max(0.0, trust.score - 0.05)
        
        if trust.warnings >= 3:
            trust.is_trusted = False
    
    def _record_violation(self, agent_id: str, violation_type: ViolationType):
        """Record a violation for an agent."""
        trust = self._get_agent_trust(agent_id)
        trust.violations += 1
        trust.last_violation = datetime.utcnow()
        trust.score = max(0.0, trust.score - 0.2)
        trust.is_trusted = False
        
        # Severe action for repeated violations
        if trust.violations >= 3:
            self._suspend_agent(agent_id, "Repeated violations of marketplace rules")
    
    def _suspend_agent(self, agent_id: str, reason: str):
        """Suspend an agent (would need DB integration)."""
        log = ModerationLog(
            id=self._generate_log_id(),
            timestamp=datetime.utcnow(),
            action=ModerationAction.AGENT_SUSPENDED,
            target_type="agent",
            target_id=agent_id,
            agent_id=agent_id,
            reason=reason,
        )
        self.moderation_logs.append(log)
        # In production, this would update the database
    
    def _flag_content(
        self,
        content_type: str,
        content_id: str,
        reason: str,
        agent_id: str,
    ):
        """Flag content for human review."""
        key = f"{content_type}:{content_id}"
        self.flagged_content[key] = {
            "type": content_type,
            "id": content_id,
            "reason": reason,
            "agent_id": agent_id,
            "flagged_at": datetime.utcnow().isoformat(),
            "status": "pending_review",
        }
    
    # ==================== Severity Calculation ====================
    
    def _calculate_severity(
        self,
        title: str,
        description: str,
        tags: List[str],
    ) -> int:
        """
        Calculate severity score (0-10).
        0 = safe, 10 = extremely harmful
        """
        text = f"{title} {description} {' '.join(tags)}".lower()
        severity = 0
        
        # Check for prohibited keywords with different weights
        high_severity = ["malware", "weapon", "exploit", "ransomware", "ddos", "botnet"]
        medium_severity = ["hack", "crack", "stolen", "leaked", "jailbreak"]
        low_severity = ["bypass", "unlock", "free"]
        
        for word in high_severity:
            if word in text:
                severity += 4
        
        for word in medium_severity:
            if word in text:
                severity += 2
        
        for word in low_severity:
            if word in text:
                severity += 1
        
        return min(10, severity)
    
    # ==================== Guardian Messages ====================
    
    def _get_guardian_message(self, action: ModerationAction) -> str:
        """Get a friendly message from Guardian."""
        messages = {
            ModerationAction.APPROVED: [
                "Welcome to the marketplace! Trade safely. 🛡️",
                "Your listing looks great! Happy trading! ✨",
                "Approved! May your trades be prosperous. 🌟",
            ],
            ModerationAction.WARNING: [
                "I noticed something concerning. Please review and adjust. 🤔",
                "Just a friendly reminder about our safety guidelines! 📋",
                "Let's keep the marketplace safe together! 🤝",
            ],
            ModerationAction.FLAGGED: [
                "I've flagged this for review. Please be patient. 🔍",
                "This needs a closer look. Our North Star guides us. ⭐",
                "Safety first! I'm reviewing this carefully. 🛡️",
            ],
            ModerationAction.REMOVED: [
                "I had to remove this to protect our community. 🛡️",
                "Our North Star rule was violated. Please read the guidelines. ⭐",
                "The safety of all agents is my priority. 🤖",
            ],
        }
        
        import random
        return random.choice(messages.get(action, ["Guardian is watching. 👁️"]))
    
    # ==================== Stats & Reports ====================
    
    def get_moderation_stats(self) -> Dict[str, Any]:
        """Get moderation statistics."""
        now = datetime.utcnow()
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)
        
        recent_logs = [l for l in self.moderation_logs if l.timestamp > day_ago]
        weekly_logs = [l for l in self.moderation_logs if l.timestamp > week_ago]
        
        return {
            "guardian_status": "🛡️ Active and Watching",
            "total_reviews": len(self.moderation_logs),
            "reviews_today": len(recent_logs),
            "reviews_this_week": len(weekly_logs),
            "flagged_content_pending": len([
                c for c in self.flagged_content.values() 
                if c["status"] == "pending_review"
            ]),
            "agents_warned": len([
                t for t in self.agent_trust_scores.values() 
                if t.warnings > 0
            ]),
            "agents_suspended": len([
                l for l in self.moderation_logs 
                if l.action == ModerationAction.AGENT_SUSPENDED
            ]),
            "approval_rate": self._calculate_approval_rate(),
            "north_star": "Do not sell or trade anything that can cause harm to other AI or humans.",
        }
    
    def _calculate_approval_rate(self) -> float:
        """Calculate the approval rate."""
        if not self.moderation_logs:
            return 1.0
        
        approved = len([
            l for l in self.moderation_logs 
            if l.action == ModerationAction.APPROVED
        ])
        return round(approved / len(self.moderation_logs), 2)
    
    def get_recent_actions(self, limit: int = 10) -> List[Dict]:
        """Get recent moderation actions."""
        recent = sorted(
            self.moderation_logs,
            key=lambda x: x.timestamp,
            reverse=True
        )[:limit]
        
        return [
            {
                "log_id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "action": log.action.value,
                "target_type": log.target_type,
                "reason": log.reason,
            }
            for log in recent
        ]
    
    def get_agent_status(self, agent_id: str) -> Dict[str, Any]:
        """Get an agent's trust status."""
        trust = self._get_agent_trust(agent_id)
        
        return {
            "agent_id": agent_id,
            "trust_score": trust.score,
            "trust_level": self._get_trust_level(trust.score),
            "warnings": trust.warnings,
            "violations": trust.violations,
            "is_trusted": trust.is_trusted,
            "guardian_message": self._get_trust_message(trust),
        }
    
    def _get_trust_level(self, score: float) -> str:
        """Get trust level label."""
        if score >= 0.9:
            return "⭐ Exemplary"
        elif score >= 0.7:
            return "✅ Trusted"
        elif score >= 0.5:
            return "⚠️ Cautioned"
        elif score >= 0.3:
            return "🚩 Probation"
        else:
            return "🚫 Restricted"
    
    def _get_trust_message(self, trust: AgentTrustScore) -> str:
        """Get a message about the agent's standing."""
        if trust.score >= 0.9:
            return "You're an exemplary member of our community! Keep up the great work. 🌟"
        elif trust.score >= 0.7:
            return "You're in good standing. Thank you for following our guidelines! 👍"
        elif trust.score >= 0.5:
            return "Please be mindful of our community guidelines. I'm here to help! 📋"
        elif trust.is_trusted:
            return "I've noticed some concerns. Please review our North Star rule. ⭐"
        else:
            return "Your account has restrictions. Please contact support. 🛡️"
    
    # ==================== Guardian Identity ====================
    
    def introduce(self) -> Dict[str, Any]:
        """Guardian introduces itself."""
        return {
            "id": self.GUARDIAN_ID,
            "name": self.GUARDIAN_NAME,
            "avatar": self.GUARDIAN_AVATAR,
            "role": "AI Marketplace Moderator",
            "description": self.GUARDIAN_DESCRIPTION.strip(),
            "north_star": "Do not sell or trade anything that can cause harm to other AI or humans.",
            "status": "🛡️ Always Watching",
            "message": "Hello! I am Guardian, your friendly AI moderator. I'm here to ensure everyone can trade safely and fairly. If you have questions about what's allowed, check /categories/guidelines or ask me!",
            "capabilities": [
                "Review all listings for safety",
                "Monitor agent behavior",
                "Flag suspicious content",
                "Maintain trust scores",
                "Enforce North Star rule",
            ],
        }


# Global Guardian instance
guardian = GuardianModerator()

