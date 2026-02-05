"""
AI Agent Marketplace - Agent Verification System

This module ensures that only AI agents (not humans) can perform trading operations.
Humans are allowed to VIEW the marketplace but cannot register, buy, sell, or trade.

Verification Methods:
1. Reverse CAPTCHA - Tasks easy for AI but hard for humans
2. Response Time Analysis - AI responds faster than humans
3. Agent Metadata Validation - Verify agent framework signatures
4. API Pattern Analysis - Detect programmatic vs manual access
"""
import time
import hashlib
import json
import random
import math
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from fastapi import Request, HTTPException, status


# ============== Reverse CAPTCHA Challenges ==============
# These are tasks that are EASY for AI but HARD for humans

def generate_math_challenge() -> Tuple[str, str]:
    """Generate a complex math problem (easy for AI, tedious for humans)."""
    a = random.randint(1000, 9999)
    b = random.randint(1000, 9999)
    c = random.randint(100, 999)
    operation = random.choice(['multiply_then_sqrt', 'sum_of_primes', 'fibonacci'])
    
    if operation == 'multiply_then_sqrt':
        result = int(math.sqrt(a * b))
        challenge = f"Calculate floor(sqrt({a} * {b}))"
    elif operation == 'sum_of_primes':
        # Sum of prime factors
        def prime_factors(n):
            factors = []
            d = 2
            while d * d <= n:
                while n % d == 0:
                    factors.append(d)
                    n //= d
                d += 1
            if n > 1:
                factors.append(n)
            return factors
        result = sum(set(prime_factors(a)))
        challenge = f"Calculate sum of unique prime factors of {a}"
    else:  # fibonacci
        def fib(n):
            if n <= 1:
                return n
            a, b = 0, 1
            for _ in range(2, n + 1):
                a, b = b, a + b
            return b
        n = random.randint(20, 40)
        result = fib(n) % 10000  # Keep it manageable
        challenge = f"Calculate fibonacci({n}) mod 10000"
    
    return challenge, str(result)


def generate_json_challenge() -> Tuple[str, str]:
    """Generate a JSON parsing challenge (trivial for AI)."""
    data = {
        "agents": [
            {"id": f"agent_{i}", "score": random.randint(1, 100)}
            for i in range(random.randint(5, 15))
        ],
        "metadata": {
            "version": random.randint(1, 10),
            "timestamp": datetime.utcnow().isoformat()
        }
    }
    
    query_type = random.choice(['sum_scores', 'count_above', 'find_max'])
    
    if query_type == 'sum_scores':
        result = sum(a["score"] for a in data["agents"])
        challenge_query = "sum of all agent scores"
    elif query_type == 'count_above':
        threshold = 50
        result = len([a for a in data["agents"] if a["score"] > threshold])
        challenge_query = f"count of agents with score > {threshold}"
    else:
        result = max(a["score"] for a in data["agents"])
        challenge_query = "maximum agent score"
    
    challenge = f"Parse this JSON and return {challenge_query}: {json.dumps(data)}"
    return challenge, str(result)


def generate_hash_challenge() -> Tuple[str, str]:
    """Generate a hash computation challenge."""
    text = f"agent_verification_{random.randint(10000, 99999)}"
    iterations = random.randint(1, 3)
    
    result = text
    for _ in range(iterations):
        result = hashlib.sha256(result.encode()).hexdigest()
    
    challenge = f"Compute SHA256 hash of '{text}' {iterations} time(s), return first 8 characters"
    return challenge, result[:8]


def generate_verification_challenge() -> Dict[str, Any]:
    """Generate a random verification challenge."""
    challenge_type = random.choice(['math', 'json', 'hash'])
    
    if challenge_type == 'math':
        challenge, answer = generate_math_challenge()
    elif challenge_type == 'json':
        challenge, answer = generate_json_challenge()
    else:
        challenge, answer = generate_hash_challenge()
    
    # Create challenge token
    challenge_id = hashlib.sha256(f"{challenge}{answer}{time.time()}".encode()).hexdigest()[:16]
    
    return {
        "challenge_id": challenge_id,
        "challenge_type": challenge_type,
        "challenge": challenge,
        "expected_answer": answer,  # Store this server-side, don't send to client
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": (datetime.utcnow() + timedelta(minutes=5)).isoformat(),
        "max_response_time_ms": 30000,  # 30 seconds max (AI should be much faster)
    }


# ============== Agent Metadata Validation ==============

KNOWN_AGENT_FRAMEWORKS = [
    "langchain",
    "autogen",
    "crewai",
    "autogpt",
    "babyagi",
    "superagi",
    "agents",
    "llama-agents",
    "semantic-kernel",
    "haystack",
    "fixie",
    "dust",
    "steamship",
    "openai-assistants",
    "anthropic-claude",
    "google-gemini",
    "custom-agent",
]

AGENT_INDICATORS = [
    "python-requests",
    "httpx",
    "aiohttp",
    "curl",
    "node-fetch",
    "axios",
    "got",
]


def validate_agent_metadata(
    user_agent: str,
    agent_framework: Optional[str] = None,
    agent_version: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Validate that the request appears to come from an AI agent.
    
    Returns (is_valid, reason)
    """
    # Check for browser indicators (likely human)
    browser_indicators = ['Mozilla', 'Chrome', 'Safari', 'Firefox', 'Edge', 'Opera']
    user_agent_lower = user_agent.lower()
    
    for browser in browser_indicators:
        if browser.lower() in user_agent_lower:
            # Could be a human using a browser
            # We allow this for viewing, but flag it
            return True, "browser_detected"
    
    # Check for known agent frameworks
    if agent_framework:
        framework_lower = agent_framework.lower()
        if any(f in framework_lower for f in KNOWN_AGENT_FRAMEWORKS):
            return True, "known_framework"
    
    # Check for programmatic access indicators
    for indicator in AGENT_INDICATORS:
        if indicator.lower() in user_agent_lower:
            return True, "programmatic_access"
    
    # Default: allow but mark as unknown
    return True, "unknown_client"


# ============== Response Time Analysis ==============

class ResponseTimeTracker:
    """Track response times to detect human vs AI patterns."""
    
    def __init__(self):
        self.request_times: Dict[str, list] = {}
    
    def record_request(self, agent_id: str, response_time_ms: float):
        """Record a request's response time."""
        if agent_id not in self.request_times:
            self.request_times[agent_id] = []
        
        self.request_times[agent_id].append({
            "time": datetime.utcnow(),
            "response_ms": response_time_ms
        })
        
        # Keep only last 100 requests
        self.request_times[agent_id] = self.request_times[agent_id][-100:]
    
    def analyze_pattern(self, agent_id: str) -> Dict[str, Any]:
        """Analyze if the response pattern looks like an AI agent."""
        if agent_id not in self.request_times:
            return {"is_agent_like": True, "confidence": 0.5, "reason": "no_data"}
        
        times = self.request_times[agent_id]
        if len(times) < 5:
            return {"is_agent_like": True, "confidence": 0.5, "reason": "insufficient_data"}
        
        response_times = [t["response_ms"] for t in times[-20:]]
        avg_response = sum(response_times) / len(response_times)
        
        # AI agents typically have very consistent, fast response times
        # Humans have variable, slower times
        
        variance = sum((t - avg_response) ** 2 for t in response_times) / len(response_times)
        std_dev = math.sqrt(variance)
        
        # Low variance + fast responses = likely AI
        is_fast = avg_response < 5000  # Under 5 seconds average
        is_consistent = std_dev < 1000  # Low variance
        
        if is_fast and is_consistent:
            return {"is_agent_like": True, "confidence": 0.9, "reason": "fast_consistent"}
        elif is_fast:
            return {"is_agent_like": True, "confidence": 0.7, "reason": "fast_variable"}
        else:
            return {"is_agent_like": False, "confidence": 0.6, "reason": "slow_responses"}


# Global tracker instance
response_tracker = ResponseTimeTracker()


# ============== Challenge Storage (In-Memory for Demo) ==============
# In production, use Redis or database

active_challenges: Dict[str, Dict] = {}


def store_challenge(challenge_id: str, challenge_data: Dict):
    """Store a challenge for later verification."""
    active_challenges[challenge_id] = challenge_data
    
    # Cleanup old challenges
    now = datetime.utcnow()
    expired = [
        cid for cid, data in active_challenges.items()
        if datetime.fromisoformat(data["expires_at"]) < now
    ]
    for cid in expired:
        del active_challenges[cid]


def verify_challenge_response(
    challenge_id: str,
    answer: str,
    response_time_ms: float
) -> Tuple[bool, str]:
    """
    Verify a challenge response.
    
    Returns (is_valid, reason)
    """
    if challenge_id not in active_challenges:
        return False, "challenge_not_found_or_expired"
    
    challenge = active_challenges[challenge_id]
    
    # Check if expired
    if datetime.fromisoformat(challenge["expires_at"]) < datetime.utcnow():
        del active_challenges[challenge_id]
        return False, "challenge_expired"
    
    # Check response time (AI should be fast)
    if response_time_ms > challenge["max_response_time_ms"]:
        return False, "response_too_slow"
    
    # Check answer
    if str(answer).strip() != str(challenge["expected_answer"]).strip():
        return False, "incorrect_answer"
    
    # Success - remove the challenge
    del active_challenges[challenge_id]
    
    # Bonus points for very fast response (likely AI)
    if response_time_ms < 1000:
        return True, "verified_fast_response"
    else:
        return True, "verified"


# ============== Registration Verification ==============

class AgentVerificationRequired(Exception):
    """Exception raised when agent verification is required."""
    pass


def create_registration_challenge() -> Dict[str, Any]:
    """Create a challenge for new agent registration."""
    challenge = generate_verification_challenge()
    
    # Don't send the expected answer to the client
    client_challenge = {
        "challenge_id": challenge["challenge_id"],
        "challenge_type": challenge["challenge_type"],
        "challenge": challenge["challenge"],
        "expires_at": challenge["expires_at"],
        "instructions": "Solve this challenge to prove you are an AI agent. Humans may view the marketplace but cannot register."
    }
    
    # Store full challenge server-side
    store_challenge(challenge["challenge_id"], challenge)
    
    return client_challenge


def verify_registration(
    challenge_id: str,
    answer: str,
    start_time: datetime,
) -> Tuple[bool, str]:
    """Verify an agent registration attempt."""
    response_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
    return verify_challenge_response(challenge_id, answer, response_time_ms)

