# baseline_moderation_service.py
# Baseline content moderation service:
# - Keyword blacklist
# - Manual review queue
# - Block interception on blacklist hit



from enum import Enum
from typing import Dict, List, Optional
import uuid
import time

# App is created by create_app() below. Creation can be skipped by setting SKIP_APP_CREATION=1



class ContentStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"


# Pydantic models are created inside `create_app()` to avoid importing pydantic at module import time.
# Internal runtime uses plain dicts/objects for inputs/outputs to make testing simple and avoid pydantic
# compatibility issues on some Python environments.


def _extract_submit(req: Any) -> Tuple[str, str]:
    # accept dict-like or object with attributes
    if isinstance(req, dict):
        return req.get("user_id"), req.get("text")
    # pydantic model or namespace
    return getattr(req, "user_id", None), getattr(req, "text", None)


def _extract_review(req: Any) -> Tuple[str, str, Optional[str]]:
    if isinstance(req, dict):
        return req.get("reviewer_id"), req.get("decision"), req.get("note")
    return getattr(req, "reviewer_id", None), getattr(req, "decision", None), getattr(req, "note", None)


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


def health():
    return {"ok": True}


def list_blacklist():
    return {"keywords": BLACKLIST}


def add_blacklist_keyword(keyword: str):
    from fastapi import HTTPException
    keyword = keyword.strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="keyword cannot be empty")
    if keyword in BLACKLIST:
        return {"added": False, "keywords": BLACKLIST}
    BLACKLIST.append(keyword)
    return {"added": True, "keywords": BLACKLIST}


def remove_blacklist_keyword(keyword: str):
    from fastapi import HTTPException
    keyword = keyword.strip()
    if keyword in BLACKLIST:
        BLACKLIST.remove(keyword)
        return {"removed": True, "keywords": BLACKLIST}
    return {"removed": False, "keywords": BLACKLIST}


import os
from policy.engine import get_engine


# Execution order: policies are evaluated first (if enabled). If no policy matches, blacklist is checked.
POLICY_EXECUTION_ORDER = "policy_first"



def submit_content(req: Any):
    content_id = str(uuid.uuid4())
    ts = _now()

    user_id, text = _extract_submit(req)

    # Policies may be enabled/disabled via env var POLICIES_ENABLED (default: enabled if file exists)
    policies_enabled = os.getenv("POLICIES_ENABLED", "1").lower() in ("1", "true", "yes")
    if policies_enabled:
        engine = get_engine()
        decision = engine.decide(text, user_id)
        if decision is not None:
            action_str, reason = decision
            try:
                action = ContentStatus(action_str)
            except Exception:
                # invalid action from policy, ignore policy decision
                action = None

            if action is not None:
                item = {
                    "content_id": content_id,
                    "user_id": user_id,
                    "text": text,
                    "status": action,
                    "created_at": ts,
                    "updated_at": ts,
                    "reason": f"Policy decision: {reason}",
                }
                CONTENTS[content_id] = item
                # If decision requires manual review, add to queue
                if action == ContentStatus.PENDING_REVIEW:
                    REVIEW_QUEUE.append(content_id)
                return {"content_id": content_id, "status": item["status"], "reason": item["reason"]}

    # Policies didn't apply or are disabled -> fallback to baseline blacklist behavior
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
        return {"content_id": content_id, "status": item["status"], "reason": item["reason"]}

    # Not blocked -> require manual review in baseline
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

    return {"content_id": content_id, "status": item["status"], "reason": item["reason"]}


def get_content(content_id: str):
    # internal logic: raise KeyError if not found
    item = CONTENTS.get(content_id)
    if item is None:
        raise KeyError("content not found")
    return item


def get_review_queue(limit: int = 20):
    # internal logic: raise ValueError for invalid args
    if limit <= 0:
        raise ValueError("limit must be > 0")
    ids = REVIEW_QUEUE[:limit]
    items = [CONTENTS[i] for i in ids if i in CONTENTS]
    return {"count": len(items), "items": items}


def review_content(content_id: str, req: Any):
    from fastapi import HTTPException
    # accept dict-like or object
    reviewer_id, decision, note = _extract_review(req)

    item = CONTENTS.get(content_id)
    if item is None:
        raise HTTPException(status_code=404, detail="content not found")

    if item["status"] != ContentStatus.PENDING_REVIEW:
        raise HTTPException(
            status_code=409,
            detail=f"content status is {item['status']}, cannot review",
        )

    if decision not in (ContentStatus.APPROVED, ContentStatus.REJECTED):
        raise HTTPException(status_code=400, detail="decision must be APPROVED or REJECTED")

    item["status"] = decision
    item["updated_at"] = _now()
    item["reviewer_id"] = reviewer_id
    item["review_note"] = note

    # Remove from queue if present
    try:
        REVIEW_QUEUE.remove(content_id)
    except ValueError:
        pass

    CONTENTS[content_id] = item
    return {"content_id": content_id, "status": item["status"], "reviewer_id": item.get("reviewer_id")}



def create_app() -> "FastAPI":
    from fastapi import FastAPI

    app = FastAPI(title="Baseline Content Moderation Service", version="0.1.0")

    # register routes
    app.add_api_route("/health", health, methods=["GET"])
    app.add_api_route("/blacklist", list_blacklist, methods=["GET"]) 
    app.add_api_route("/blacklist", add_blacklist_keyword, methods=["POST"]) 
    app.add_api_route("/blacklist", remove_blacklist_keyword, methods=["DELETE"]) 

    # Create local pydantic models to use for FastAPI endpoints (avoid importing pydantic at module import time)
    from pydantic import BaseModel, Field

    class SubmitContentRequest(BaseModel):
        user_id: str = Field(...)
        text: str = Field(..., max_length=5000)

    class SubmitContentResponse(BaseModel):
        content_id: str
        status: ContentStatus
        reason: Optional[str] = None

    class ReviewDecisionRequest(BaseModel):
        reviewer_id: str = Field(...)
        decision: ContentStatus
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

    async def submit_content_endpoint(req: SubmitContentRequest):
        return submit_content(req)

    async def get_content_endpoint(content_id: str):
        from fastapi import HTTPException
        try:
            item = get_content(content_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="content not found")
        # item might be dict or ContentItem
        if isinstance(item, dict):
            return ContentItem(**item)
        return item

    async def get_review_queue_endpoint(limit: int = 20):
        from fastapi import HTTPException
        try:
            return get_review_queue(limit)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def review_content_endpoint(content_id: str, req: ReviewDecisionRequest):
        from fastapi import HTTPException
        try:
            return review_content(content_id, req)
        except KeyError:
            raise HTTPException(status_code=404, detail="content not found")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    app.add_api_route("/content/submit", submit_content_endpoint, methods=["POST"], response_model=SubmitContentResponse)
    app.add_api_route("/content/{content_id}", get_content_endpoint, methods=["GET"], response_model=ContentItem)
    app.add_api_route("/review/queue", get_review_queue_endpoint, methods=["GET"]) 
    app.add_api_route("/review/{content_id}", review_content_endpoint, methods=["POST"]) 

    # if desired, we can print policy load info
    try:
        e = get_engine()
        # no-op to force initial load
    except Exception:
        pass

    return app


# By default create app at module import, but tests can skip by setting SKIP_APP_CREATION=1
if os.getenv("SKIP_APP_CREATION", "0") != "1":
    app = create_app()
