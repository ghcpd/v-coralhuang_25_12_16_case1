# baseline_moderation_service.py
# Baseline content moderation service with policy-driven moderation engine
import os
import json
from enum import Enum
from typing import Dict, List, Optional
import uuid
import time

# Minimal fallback classes (no FastAPI/pydantic dependency for testing)
FASTAPI_AVAILABLE = False

class HTTPException(Exception):
    def __init__(self, status_code: int = 500, detail: str = ""):
        super().__init__(f"HTTP {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail

class BaseModel(object):
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

def Field(*args, **kwargs):
    return None

app = None  # FastAPI app placeholder


class ContentStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"


class SubmitContentRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1, max_length=5000)


class SubmitContentResponse(BaseModel):
    content_id: str
    status: ContentStatus
    reason: Optional[str] = None


class ReviewContentRequest(BaseModel):
    content_id: str = Field(..., min_length=1)
    decision: str = Field(..., pattern="^(APPROVED|REJECTED)$")


class ReviewContentResponse(BaseModel):
    content_id: str
    status: ContentStatus


# Configurable blacklist
BLACKLIST = ["spam", "scam", "phishing"]

# In-memory storage
content_store: Dict[str, Dict] = {}
review_queue: List[str] = []


# ============================================================================
# Policy Engine
# ============================================================================

class PolicyEngine:
    """
    Configurable policy-driven moderation engine.
    - Loads policies from external JSON file (policy.json by default)
    - Evaluates content + user against policy rules
    - Returns outcome (LOW_RISK / MEDIUM_RISK / HIGH_RISK) and matching policy info
    """
    
    def __init__(self, policy_file: str = "policy.json"):
        self.policy_file = policy_file
        self.policies = []
        self.enabled = False
        self._load_policies()
    
    def _load_policies(self):
        """Load policies from JSON file (relative to module or absolute path)."""
        # Try relative to module first
        module_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(module_dir, self.policy_file)
        
        if not os.path.exists(full_path):
            # Try as absolute or cwd-relative
            full_path = self.policy_file
        
        if os.path.exists(full_path):
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.policies = data
                        self.enabled = True
            except Exception:
                pass  # Silently disable if policy file is malformed
    
    def reload_policies(self):
        """Reload policies from disk (for testing or hot-reload scenarios)."""
        self.policies = []
        self.enabled = False
        self._load_policies()
    
    def evaluate(self, text: str, user_id: str) -> tuple:
        """
        Evaluate content against loaded policies.
        Returns: (outcome, reason) or (None, None) if no policy matches.
        Outcome values: "LOW_RISK", "MEDIUM_RISK", "HIGH_RISK"
        """
        if not self.enabled or not self.policies:
            return None, None
        
        for policy in self.policies:
            if self._policy_matches(policy, text, user_id):
                outcome = policy.get("outcome", "MEDIUM_RISK")
                policy_name = policy.get("name", "unnamed-policy")
                reason = f"Matched policy: {policy_name}"
                return outcome, reason
        
        return None, None
    
    def _policy_matches(self, policy: dict, text: str, user_id: str) -> bool:
        """Check if a policy matches the given content and user."""
        operator = policy.get("operator", "OR").upper()
        rules = policy.get("rules", [])
        
        if not rules:
            return False
        
        results = [self._rule_matches(rule, text, user_id) for rule in rules]
        
        if operator == "AND":
            return all(results)
        else:  # OR
            return any(results)
    
    def _rule_matches(self, rule: dict, text: str, user_id: str) -> bool:
        """Check if a single rule matches."""
        rule_type = rule.get("type", "")
        
        if rule_type == "keyword":
            keywords = rule.get("keywords", [])
            match_mode = rule.get("match", "any").lower()
            text_lower = text.lower()
            
            if match_mode == "all":
                return all(kw.lower() in text_lower for kw in keywords)
            else:  # any
                return any(kw.lower() in text_lower for kw in keywords)
        
        elif rule_type == "user":
            user_ids = rule.get("ids", [])
            prefixes = rule.get("prefixes", [])
            
            if user_id in user_ids:
                return True
            if any(user_id.startswith(prefix) for prefix in prefixes):
                return True
            return False
        
        # Unknown rule types don't match
        return False


# Global policy engine instance
_policy_engine = PolicyEngine()


def get_policy_engine() -> PolicyEngine:
    """Access the global policy engine (for testing/reloading)."""
    return _policy_engine


# ============================================================================
# Moderation logic with policy-first execution
# ============================================================================

def submit_content(user_id: str, text: str) -> dict:
    """
    Submit content for moderation. Execution order:
    1. Evaluate policies (if enabled) — takes precedence
    2. Fall back to baseline blacklist check
    Returns dict with content_id, status, and reason.
    """
    content_id = str(uuid.uuid4())
    
    # Step 1: Policy evaluation (if policies are loaded)
    outcome, policy_reason = _policy_engine.evaluate(text, user_id)
    
    if outcome is not None:
        # Policy matched — use policy outcome
        if outcome == "LOW_RISK":
            status = ContentStatus.APPROVED
            reason = f"Auto-approved: {policy_reason}"
        elif outcome == "MEDIUM_RISK":
            status = ContentStatus.PENDING_REVIEW
            reason = policy_reason
            review_queue.append(content_id)
        else:  # HIGH_RISK
            # Check if policy specifies BLOCK action
            status = ContentStatus.BLOCKED
            reason = f"Auto-blocked: {policy_reason}"
        
        content_store[content_id] = {
            "user_id": user_id,
            "text": text,
            "status": status,
            "reason": reason,
            "created_at": time.time()
        }
        
        return {
            "content_id": content_id,
            "status": status,
            "reason": reason
        }
    
    # Step 2: Baseline blacklist check (no policy matched)
    text_lower = text.lower()
    for keyword in BLACKLIST:
        if keyword.lower() in text_lower:
            status = ContentStatus.BLOCKED
            reason = f"Blacklisted keyword detected: {keyword}"
            content_store[content_id] = {
                "user_id": user_id,
                "text": text,
                "status": status,
                "reason": reason,
                "created_at": time.time()
            }
            return {
                "content_id": content_id,
                "status": status,
                "reason": reason
            }
    
    # No policy matched and no blacklist hit → manual review
    status = ContentStatus.PENDING_REVIEW
    reason = None
    review_queue.append(content_id)
    content_store[content_id] = {
        "user_id": user_id,
        "text": text,
        "status": status,
        "reason": reason,
        "created_at": time.time()
    }
    
    return {
        "content_id": content_id,
        "status": status,
        "reason": reason
    }


def review_content(content_id: str, decision: str) -> dict:
    """
    Review content and set final decision (APPROVED or REJECTED).
    Returns updated content info.
    """
    if content_id not in content_store:
        raise HTTPException(status_code=404, detail="Content not found")
    
    content = content_store[content_id]
    
    if content["status"] != ContentStatus.PENDING_REVIEW:
        raise HTTPException(status_code=400, detail="Content is not pending review")
    
    if decision not in ["APPROVED", "REJECTED"]:
        raise HTTPException(status_code=400, detail="Invalid decision")
    
    content["status"] = ContentStatus.APPROVED if decision == "APPROVED" else ContentStatus.REJECTED
    content["reviewed_at"] = time.time()
    
    if content_id in review_queue:
        review_queue.remove(content_id)
    
    return {
        "content_id": content_id,
        "status": content["status"]
    }


def get_review_queue() -> list:
    """Get all content IDs pending review."""
    return review_queue.copy()


def get_content(content_id: str) -> dict:
    """Retrieve content by ID."""
    if content_id not in content_store:
        raise HTTPException(status_code=404, detail="Content not found")
    return content_store[content_id].copy()
