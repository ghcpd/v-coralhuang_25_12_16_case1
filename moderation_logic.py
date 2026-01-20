from typing import Dict, List, Optional
import time
import uuid

from policy_engine import PolicyEngine
from enum import Enum


class ContentStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"

# In-memory stores
BLACKLIST: List[str] = ["spam", "scam", "illegal"]  # baseline static list
CONTENTS: Dict[str, Dict] = {}
REVIEW_QUEUE: List[str] = []


def _now() -> float:
    return time.time()


def _hit_blacklist(text: str) -> Optional[str]:
    lower = text.lower()
    for kw in BLACKLIST:
        if kw.lower() in lower:
            return kw
    return None


def submit_content_logic(user_id: str, text: str):
    content_id = str(uuid.uuid4())
    ts = _now()

    # Policy-first evaluation
    policy_engine = PolicyEngine()
    action, reason = policy_engine.evaluate(text, user_id)

    if action is not None:
        status = ContentStatus[action]
        item = {
            "content_id": content_id,
            "user_id": user_id,
            "text": text,
            "status": status,
            "created_at": ts,
            "updated_at": ts,
            "reason": reason,
            "reviewer_id": None,
            "review_note": None,
        }
        CONTENTS[content_id] = item
        if status == ContentStatus.PENDING_REVIEW:
            REVIEW_QUEUE.append(content_id)
        return item

    # no policy -> fallback to blacklist
    hit = _hit_blacklist(text)
    if hit is not None:
        item = {
            "content_id": content_id,
            "user_id": user_id,
            "text": text,
            "status": ContentStatus.BLOCKED,
            "created_at": ts,
            "updated_at": ts,
            "reason": f"Blacklisted keyword hit: {hit}",
            "reviewer_id": None,
            "review_note": None,
        }
        CONTENTS[content_id] = item
        return item

    # manual review
    item = {
        "content_id": content_id,
        "user_id": user_id,
        "text": text,
        "status": ContentStatus.PENDING_REVIEW,
        "created_at": ts,
        "updated_at": ts,
        "reason": "Requires manual review",
        "reviewer_id": None,
        "review_note": None,
    }
    CONTENTS[content_id] = item
    REVIEW_QUEUE.append(content_id)
    return item


# Helpers used by API

def get_content_logic(content_id: str):
    return CONTENTS.get(content_id)


def get_review_queue_logic(limit: int = 20):
    ids = REVIEW_QUEUE[:limit]
    return [CONTENTS[i] for i in ids if i in CONTENTS]



def review_content_logic(content_id: str, reviewer_id: str, decision: str, note: Optional[str] = None):
    item = CONTENTS.get(content_id)
    if item is None:
        raise KeyError("content not found")

    if item["status"] != ContentStatus.PENDING_REVIEW:
        raise RuntimeError("content status not pending review")

    if decision not in (ContentStatus.APPROVED, ContentStatus.REJECTED):
        raise ValueError("invalid decision")

    item["status"] = decision
    item["updated_at"] = _now()
    item["reviewer_id"] = reviewer_id
    item["review_note"] = note

    try:
        REVIEW_QUEUE.remove(content_id)
    except ValueError:
        pass
    return item
