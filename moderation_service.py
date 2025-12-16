# moderation_service.py
# Extended content moderation service with policy-driven decision engine
# Maintains backward compatibility with baseline functionality

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from enum import Enum
from typing import Dict, List, Optional
import uuid
import time
import logging
import os

from src.policy_engine import PolicyEngine, RiskLevel

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Content Moderation Service with Policy Engine",
    version="1.0.0",
    description="Baseline moderation with policy-driven multi-stage decisions"
)


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


class ReviewDecisionRequest(BaseModel):
    reviewer_id: str = Field(..., min_length=1)
    decision: ContentStatus  # APPROVED or REJECTED
    note: Optional[str] = Field(default=None, max_length=1000)


class ContentItem(BaseModel):
    content_id: str
    user_id: str
    text: str
    status: ContentStatus
    created_at: float
    updated_at: float
    reason: Optional[str] = None
    reviewer_id: Optional[str] = None
    review_note: Optional[str] = None


# --- Global state ---
BLACKLIST: List[str] = ["spam", "scam", "illegal"]  # baseline static list
CONTENTS: Dict[str, ContentItem] = {}
REVIEW_QUEUE: List[str] = []  # store content_id in FIFO order

# Policy engine - loaded from config
policy_engine = PolicyEngine()

# Configuration flags
POLICY_ENABLED = False
POLICY_PRIORITY = "first"  # "first" = check policy first, "blacklist" = check blacklist first


def initialize_policy_engine(policy_file: str = "policy.json", enable_policies: bool = True) -> None:
    """Initialize the policy engine with configuration file"""
    global POLICY_ENABLED
    
    if enable_policies and os.path.exists(policy_file):
        try:
            policy_engine.load_from_file(policy_file)
            POLICY_ENABLED = True
            logger.info(f"Policy engine initialized from {policy_file}")
        except Exception as e:
            logger.error(f"Failed to initialize policy engine: {e}")
            POLICY_ENABLED = False
    else:
        POLICY_ENABLED = False
        logger.info("Policy engine disabled (policies not enabled or file not found)")


def _now() -> float:
    return time.time()


def _hit_blacklist(text: str) -> Optional[str]:
    """Check if text matches any blacklist keyword (simple substring match)"""
    lower = text.lower()
    for kw in BLACKLIST:
        if kw.lower() in lower:
            return kw
    return None


def _make_moderation_decision(text: str, user_id: str) -> tuple[ContentStatus, str]:
    """
    Make moderation decision based on:
    1. Policies (if enabled)
    2. Blacklist (if policies don't match)
    
    Returns: (status, reason)
    """
    
    # Check policy first (if enabled)
    if POLICY_ENABLED:
        policy_match = policy_engine.evaluate(text, user_id)
        if policy_match:
            # Policy matched - decide based on risk level
            if policy_match.risk_level == RiskLevel.LOW:
                return (ContentStatus.APPROVED, f"Auto-approved: {policy_match.reason}")
            elif policy_match.risk_level == RiskLevel.MEDIUM:
                return (ContentStatus.PENDING_REVIEW, f"Routed to review: {policy_match.reason}")
            elif policy_match.risk_level == RiskLevel.HIGH:
                return (ContentStatus.REJECTED, f"Auto-rejected: {policy_match.reason}")
    
    # Check blacklist
    hit = _hit_blacklist(text)
    if hit is not None:
        return (ContentStatus.BLOCKED, f"Blacklisted keyword hit: {hit}")
    
    # No match - require manual review
    return (ContentStatus.PENDING_REVIEW, "Requires manual review")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/config")
def get_config():
    """Return current configuration"""
    return {
        "policy_enabled": POLICY_ENABLED,
        "policy_priority": POLICY_PRIORITY,
        "policies_count": len(policy_engine.policies),
        "blacklist_keywords": len(BLACKLIST)
    }


@app.get("/blacklist")
def list_blacklist():
    return {"keywords": BLACKLIST}


@app.post("/blacklist")
def add_blacklist_keyword(keyword: str):
    keyword = keyword.strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="keyword cannot be empty")
    if keyword in BLACKLIST:
        return {"added": False, "keywords": BLACKLIST}
    BLACKLIST.append(keyword)
    return {"added": True, "keywords": BLACKLIST}


@app.delete("/blacklist")
def remove_blacklist_keyword(keyword: str):
    keyword = keyword.strip()
    if keyword in BLACKLIST:
        BLACKLIST.remove(keyword)
        return {"removed": True, "keywords": BLACKLIST}
    return {"removed": False, "keywords": BLACKLIST}


@app.post("/content/submit", response_model=SubmitContentResponse)
def submit_content(req: SubmitContentRequest):
    """Submit content for moderation"""
    content_id = str(uuid.uuid4())
    ts = _now()

    # Make moderation decision
    status, reason = _make_moderation_decision(req.text, req.user_id)

    item = ContentItem(
        content_id=content_id,
        user_id=req.user_id,
        text=req.text,
        status=status,
        created_at=ts,
        updated_at=ts,
        reason=reason,
    )
    CONTENTS[content_id] = item

    # Add to review queue if pending
    if status == ContentStatus.PENDING_REVIEW:
        REVIEW_QUEUE.append(content_id)

    return SubmitContentResponse(
        content_id=content_id,
        status=item.status,
        reason=item.reason,
    )


@app.get("/content/{content_id}", response_model=ContentItem)
def get_content(content_id: str):
    """Get content item by ID"""
    item = CONTENTS.get(content_id)
    if item is None:
        raise HTTPException(status_code=404, detail="content not found")
    return item


@app.get("/review/queue")
def get_review_queue(limit: int = 20):
    """Get pending review queue"""
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit must be > 0")
    ids = REVIEW_QUEUE[:limit]
    items = [CONTENTS[i] for i in ids if i in CONTENTS]
    return {"count": len(items), "items": items}


@app.post("/review/{content_id}")
def review_content(content_id: str, req: ReviewDecisionRequest):
    """Submit human review decision"""
    item = CONTENTS.get(content_id)
    if item is None:
        raise HTTPException(status_code=404, detail="content not found")

    if item.status != ContentStatus.PENDING_REVIEW:
        raise HTTPException(
            status_code=409,
            detail=f"content status is {item.status}, cannot review",
        )

    if req.decision not in (ContentStatus.APPROVED, ContentStatus.REJECTED):
        raise HTTPException(status_code=400, detail="decision must be APPROVED or REJECTED")

    item.status = req.decision
    item.updated_at = _now()
    item.reviewer_id = req.reviewer_id
    item.review_note = req.note

    # Remove from queue if present
    try:
        REVIEW_QUEUE.remove(content_id)
    except ValueError:
        pass

    CONTENTS[content_id] = item
    return {"content_id": content_id, "status": item.status, "reviewer_id": item.reviewer_id}


# --- For testing ---
def clear_state():
    """Clear all in-memory state (for testing)"""
    global CONTENTS, REVIEW_QUEUE
    CONTENTS.clear()
    REVIEW_QUEUE.clear()
