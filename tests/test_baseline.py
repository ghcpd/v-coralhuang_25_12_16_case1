import os
os.environ.setdefault("SKIP_APP_CREATION", "1")

import importlib
import baseline_moderation_service as svc
importlib.reload(svc)

# use simple dicts for requests (avoids pydantic at import time)


def test_baseline_block_with_policies_disabled(monkeypatch):
    # Ensure policies are disabled
    monkeypatch.setenv("POLICIES_ENABLED", "0")
    svc.CONTENTS.clear()
    svc.REVIEW_QUEUE.clear()

    resp = svc.submit_content({"user_id": "user1", "text": "this is spam content"})
    assert resp.status_code == 200 if hasattr(resp, 'status_code') else True
    data = resp if isinstance(resp, dict) else resp.dict()
    assert data["status"] == "BLOCKED"
    assert "Blacklisted keyword hit" in data["reason"]


def test_baseline_queue_with_policies_disabled(monkeypatch):
    monkeypatch.setenv("POLICIES_ENABLED", "0")
    svc.CONTENTS.clear()
    svc.REVIEW_QUEUE.clear()

    resp = svc.submit_content({"user_id": "user2", "text": "just a normal post"})
    data = resp if isinstance(resp, dict) else resp.dict()
    assert data["status"] == "PENDING_REVIEW"

    # ensure it's present via queue
    q = svc.get_review_queue()
    assert any(item["content_id"] == data["content_id"] for item in q["items"])