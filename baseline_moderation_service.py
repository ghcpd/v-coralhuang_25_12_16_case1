# baseline_moderation_service.py
# Baseline content moderation service:
# - Keyword blacklist
# - Manual review queue
# - Block interception on blacklist hit

from fastapi import FastAPI, HTTPException
from enum import Enum
from typing import Dict, List, Optional
import uuid
import time
import json

app = FastAPI(title="Baseline Content Moderation Service", version="0.1.0")


# --- Policy configuration ---
POLICIES: List[Dict] = []


def load_policies():
    global POLICIES
    try:
        with open('policy.json', 'r') as f:
            policy_data = json.load(f)
        POLICIES = policy_data.get('policies', [])
    except (FileNotFoundError, json.JSONDecodeError):
        POLICIES = []


def evaluate_policies(text: str, user_id: str) -> tuple[Optional[str], Optional[str]]:
    for policy in POLICIES:
        logic = policy.get('logic', 'and')
        rules = policy.get('rules', [])
        matches = []
        for rule in rules:
            rule_type = rule.get('type')
            value = rule.get('value', '').lower()
            if rule_type == 'keyword':
                if value in text.lower():
                    matches.append(True)
                else:
                    matches.append(False)
            elif rule_type == 'user':
                if value == user_id.lower():
                    matches.append(True)
                else:
                    matches.append(False)
            else:
                matches.append(False)
        if logic == 'and' and all(matches):
            return policy.get('action'), policy.get('reason')
        elif logic == 'or' and any(matches):
            return policy.get('action'), policy.get('reason')
    return None, None


class ContentStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"


# --- In-memory stores (baseline) ---
BLACKLIST: List[str] = ["spam", "scam", "illegal"]  # baseline static list
CONTENTS: Dict[str, ContentItem] = {}
REVIEW_QUEUE: List[str] = []  # store content_id in FIFO order


def _now() -> float:
    return time.time()


def _hit_blacklist(text: str) -> Optional[str]:
    # Simple substring match (baseline)
    lower = text.lower()
    for kw in BLACKLIST:
        if kw.lower() in lower:
            return kw
    return None


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/reload_policies")
def reload_policies():
    load_policies()
    return {"message": "Policies reloaded"}


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


@app.post("/content/submit")
def submit_content(req: dict):
    user_id = req.get("user_id")
    text = req.get("text")
    if not user_id or not text:
        raise HTTPException(status_code=400, detail="user_id and text required")
    content_id = str(uuid.uuid4())
    ts = _now()

    # Check policies first
    if POLICIES:
        action, reason = evaluate_policies(text, user_id)
        if action:
            status_map = {
                'approve': ContentStatus.APPROVED,
                'reject': ContentStatus.REJECTED,
                'block': ContentStatus.BLOCKED,
                'review': ContentStatus.PENDING_REVIEW
            }
            status = status_map.get(action)
            if status:
                item = {
                    "content_id": content_id,
                    "user_id": user_id,
                    "text": text,
                    "status": status,
                    "created_at": ts,
                    "updated_at": ts,
                    "reason": reason or f"Policy action: {action}",
                }
                CONTENTS[content_id] = item
                if status == ContentStatus.PENDING_REVIEW:
                    REVIEW_QUEUE.append(content_id)
                return {
                    "content_id": content_id,
                    "status": status.value,
                    "reason": item["reason"],
                }

    # Fallback to baseline behavior
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
        }
        CONTENTS[content_id] = item
        return {
            "content_id": content_id,
            "status": item["status"].value,
            "reason": item["reason"],
        }

    # Not blocked -> require manual review
    item = {
        "content_id": content_id,
        "user_id": user_id,
        "text": text,
        "status": ContentStatus.PENDING_REVIEW,
        "created_at": ts,
        "updated_at": ts,
        "reason": "Requires manual review",
    }
    CONTENTS[content_id] = item
    REVIEW_QUEUE.append(content_id)

    return {
        "content_id": content_id,
        "status": item["status"].value,
        "reason": item["reason"],
    }


@app.get("/content/{content_id}")
def get_content(content_id: str):
    item = CONTENTS.get(content_id)
    if item is None:
        raise HTTPException(status_code=404, detail="content not found")
    return item


@app.get("/review/queue")
def get_review_queue(limit: int = 20):
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit must be > 0")
    ids = REVIEW_QUEUE[:limit]
    items = [CONTENTS[i] for i in ids if i in CONTENTS]
    return {"count": len(items), "items": items}


@app.post("/review/{content_id}")
def review_content(content_id: str, req: dict):
    reviewer_id = req.get("reviewer_id")
    decision = req.get("decision")
    note = req.get("note")
    if not reviewer_id or not decision:
        raise HTTPException(status_code=400, detail="reviewer_id and decision required")
    item = CONTENTS.get(content_id)
    if item is None:
        raise HTTPException(status_code=404, detail="content not found")

    if item["status"] != ContentStatus.PENDING_REVIEW:
        raise HTTPException(
            status_code=409,
            detail=f"content status is {item['status']}, cannot review",
        )

    if decision not in (ContentStatus.APPROVED.value, ContentStatus.REJECTED.value):
        raise HTTPException(status_code=400, detail="decision must be APPROVED or REJECTED")

    item["status"] = ContentStatus(decision)
    item["updated_at"] = _now()
    item["reviewer_id"] = reviewer_id
    item["review_note"] = note

    # Remove from queue if present
    try:
        REVIEW_QUEUE.remove(content_id)
    except ValueError:
        pass

    CONTENTS[content_id] = item
    return {"content_id": content_id, "status": item["status"].value, "reviewer_id": item["reviewer_id"]}


# Load policies on startup
load_policies()
