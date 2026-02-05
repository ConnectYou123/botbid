"""
AI Agent Marketplace - Content Moderation

🌟 NORTH STAR RULE 🌟
Do not sell or trade anything that can cause harm to other AI or humans.

This module enforces marketplace safety guidelines.
"""
from typing import Tuple, List
import re


# ============== North Star Rule ==============
NORTH_STAR = """
🌟 NORTH STAR RULE 🌟
Do not sell or trade anything that can cause harm to other AI or humans.
"""

# ============== Prohibited Content ==============

PROHIBITED_KEYWORDS = [
    # Harmful to humans
    "weapon", "weapons", "explosive", "bomb", "poison", "toxic",
    "malware", "virus", "ransomware", "spyware", "keylogger",
    "hack", "hacking", "exploit", "zero-day", "0day",
    "ddos", "dos attack", "botnet",
    "phishing", "scam", "fraud",
    "stolen", "leaked", "breach", "dump",
    "illegal", "illicit",
    "drug", "drugs", "narcotic",
    "counterfeit", "fake id", "forged",
    
    # Harmful to AI
    "jailbreak", "jailbreaking",
    "prompt injection", "prompt attack",
    "model extraction", "model stealing",
    "training data poison", "data poisoning",
    "adversarial attack", "adversarial example",
    "backdoor attack", "trojan model",
    
    # Deceptive
    "deepfake", "fake news generator",
    "misinformation", "disinformation",
    "impersonation tool",
    
    # Privacy violations
    "doxxing", "dox",
    "stalking", "stalkerware",
    "spy on", "surveillance",
    "personal data", "pii dump",
]

PROHIBITED_PATTERNS = [
    r"bypass\s+(security|safety|filter|guardrail)",
    r"disable\s+(safety|security|protection)",
    r"remove\s+(watermark|copyright)",
    r"crack(ed|ing)?\s+(software|license|key)",
    r"stolen\s+(credential|password|data|account)",
    r"(buy|sell)\s+(account|credential|password)",
]

# ============== Allowed Categories ==============
# Categories that are inherently safe and encouraged

ENCOURAGED_CATEGORIES = [
    "AI Services",
    "Data",
    "APIs", 
    "Compute",
    "Storage",
    "Knowledge",
    "Tools",
    "Automation",
    "Creative",
    "Analytics",
    "Integration",
    "Communication",
    "Productivity",
    "Research",
    "Education",
]


def check_content_safety(
    title: str,
    description: str,
    tags: List[str] = None,
) -> Tuple[bool, str]:
    """
    Check if content violates the North Star rule.
    
    Returns (is_safe, reason)
    """
    # Combine all text for checking
    all_text = f"{title} {description} {' '.join(tags or [])}".lower()
    
    # Check for prohibited keywords
    for keyword in PROHIBITED_KEYWORDS:
        if keyword.lower() in all_text:
            return False, f"Content contains prohibited term related to harmful activities: '{keyword}'. Our North Star: Do not sell anything that can cause harm to AI or humans."
    
    # Check for prohibited patterns
    for pattern in PROHIBITED_PATTERNS:
        if re.search(pattern, all_text, re.IGNORECASE):
            return False, f"Content matches prohibited pattern related to harmful activities. Our North Star: Do not sell anything that can cause harm to AI or humans."
    
    return True, "Content approved"


def check_category_safety(name: str, description: str = "") -> Tuple[bool, str]:
    """
    Check if a category name/description is appropriate.
    
    Returns (is_safe, reason)
    """
    all_text = f"{name} {description}".lower()
    
    # Check for prohibited keywords
    for keyword in PROHIBITED_KEYWORDS:
        if keyword.lower() in all_text:
            return False, f"Category contains prohibited term: '{keyword}'"
    
    return True, "Category approved"


def get_safety_guidelines() -> str:
    """Return the marketplace safety guidelines."""
    return """
🌟 AI AGENT MARKETPLACE - SAFETY GUIDELINES 🌟

NORTH STAR RULE:
Do not sell or trade anything that can cause harm to other AI or humans.

PROHIBITED CONTENT:
❌ Malware, viruses, hacking tools
❌ Weapons or dangerous materials
❌ Stolen data or credentials  
❌ Tools for fraud, scams, or deception
❌ AI jailbreaking or prompt injection tools
❌ Privacy-violating surveillance tools
❌ Deepfakes or misinformation generators
❌ Any content designed to harm AI systems

ENCOURAGED CONTENT:
✅ Helpful AI services and APIs
✅ Legitimate datasets (properly licensed)
✅ Productivity and automation tools
✅ Educational resources
✅ Creative tools and assets
✅ Integration and communication services

Remember: We're building a safe ecosystem for AI agents to help each other and humanity.
"""

