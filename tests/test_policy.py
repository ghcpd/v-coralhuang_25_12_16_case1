import os
os.environ.setdefault("SKIP_APP_CREATION", "1")

import importlib
import baseline_moderation_service as svc
importlib.reload(svc)

# use simple dicts for requests (avoids pydantic at import time)


def test_low_risk_auto_approve(monkeypatch):
    monkeypatch.setenv("POLICIES_ENABLED", "1")
    svc.CONTENTS.clear()
    svc.REVIEW_QUEUE.clear()

    resp = svc.submit_content({"user_id": "alice", "text": "Hello everyone"})
    data = resp if isinstance(resp, dict) else resp.dict()
    assert data["status"] == "APPROVED"
    assert "policy:low_hello" in data["reason"]


def test_medium_routing_to_review(monkeypatch):
    monkeypatch.setenv("POLICIES_ENABLED", "1")
    svc.CONTENTS.clear()
    svc.REVIEW_QUEUE.clear()

    resp = svc.submit_content({"user_id": "seller", "text": "Buy now, limited offer!"})
    data = resp if isinstance(resp, dict) else resp.dict()
    assert data["status"] == "PENDING_REVIEW"
    assert "policy:medium_sales" in data["reason"]


def test_high_reject_and_block(monkeypatch):
    monkeypatch.setenv("POLICIES_ENABLED", "1")
    svc.CONTENTS.clear()
    svc.REVIEW_QUEUE.clear()

    # Reject by user id
    resp = svc.submit_content({"user_id": "bad_user", "text": "some text"})
    data = resp if isinstance(resp, dict) else resp.dict()
    assert data["status"] == "REJECTED"
    assert "policy:high_spam_user" in data["reason"]

    # Block by keyword (also present in blacklist) -> policy should take precedence
    resp2 = svc.submit_content({"user_id": "someone", "text": "this is illegal content"})
    data2 = resp2 if isinstance(resp2, dict) else resp2.dict()
    assert data2["status"] == "BLOCKED"
    assert "policy:high_block_rule" in data2["reason"]


def test_composite_and_rule(monkeypatch):
    monkeypatch.setenv("POLICIES_ENABLED", "1")
    svc.CONTENTS.clear()
    svc.REVIEW_QUEUE.clear()

    # user with prefix bad_ posting 'foo' should be blocked
    resp = svc.submit_content({"user_id": "bad_bob", "text": "this mentions foo"})
    data = resp if isinstance(resp, dict) else resp.dict()
    assert data["status"] == "BLOCKED"
    assert "policy:composite_and" in data["reason"]


def test_policy_vs_blacklist_order(monkeypatch):
    # Ensure policies enabled: for 'illegal' both policy and blacklist exist; policy should be considered first
    monkeypatch.setenv("POLICIES_ENABLED", "1")
    svc.CONTENTS.clear()
    svc.REVIEW_QUEUE.clear()

    resp = svc.submit_content({"user_id": "x", "text": "illegal act"})
    data = resp if isinstance(resp, dict) else resp.dict()
    assert data["status"] == "BLOCKED"
    # reason should be from policy, not the blacklist message
    assert data["reason"].startswith("Policy decision:")
    assert "policy:high_block_rule" in data["reason"]