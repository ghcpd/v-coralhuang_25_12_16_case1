# tests/test_baseline_regression.py
"""Tests for baseline moderation behavior (backward compatibility)"""

import pytest
from moderation_service import (
    app, clear_state, BLACKLIST,
    initialize_policy_engine, POLICY_ENABLED
)
from fastapi.testclient import TestClient


@pytest.fixture
def client_no_policy():
    """Client with policies disabled"""
    clear_state()
    initialize_policy_engine(enable_policies=False)
    return TestClient(app)


def test_baseline_health_check(client_no_policy):
    """Test health endpoint"""
    response = client_no_policy.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_baseline_blacklist_keyword_blocking(client_no_policy):
    """Test that blacklist still works when policies are disabled"""
    response = client_no_policy.post(
        "/content/submit",
        json={"user_id": "user1", "text": "This is spam content"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "BLOCKED"
    assert "Blacklisted keyword hit" in data["reason"]


def test_baseline_non_blocked_goes_to_review(client_no_policy):
    """Test that non-blocked content goes to manual review"""
    response = client_no_policy.post(
        "/content/submit",
        json={"user_id": "user1", "text": "This is perfectly fine content"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PENDING_REVIEW"
    assert data["reason"] == "Requires manual review"


def test_baseline_multiple_blacklist_keywords(client_no_policy):
    """Test matching different blacklist keywords"""
    keywords = ["spam", "scam", "illegal"]
    for kw in keywords:
        response = client_no_policy.post(
            "/content/submit",
            json={"user_id": "user1", "text": f"This content contains {kw}"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "BLOCKED"


def test_baseline_review_queue(client_no_policy):
    """Test manual review queue operations"""
    # Submit content for review
    response = client_no_policy.post(
        "/content/submit",
        json={"user_id": "user1", "text": "Normal content for review"}
    )
    content_id = response.json()["content_id"]

    # Get review queue
    response = client_no_policy.get("/review/queue")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["content_id"] == content_id


def test_baseline_approve_content(client_no_policy):
    """Test approving content in review"""
    # Submit content for review
    response = client_no_policy.post(
        "/content/submit",
        json={"user_id": "user1", "text": "Normal content for review"}
    )
    content_id = response.json()["content_id"]

    # Approve the content
    response = client_no_policy.post(
        f"/review/{content_id}",
        json={"reviewer_id": "reviewer1", "decision": "APPROVED"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"

    # Verify content is removed from queue
    response = client_no_policy.get("/review/queue")
    assert response.json()["count"] == 0


def test_baseline_reject_content(client_no_policy):
    """Test rejecting content in review"""
    # Submit content for review
    response = client_no_policy.post(
        "/content/submit",
        json={"user_id": "user1", "text": "Content to reject"}
    )
    content_id = response.json()["content_id"]

    # Reject the content
    response = client_no_policy.post(
        f"/review/{content_id}",
        json={"reviewer_id": "reviewer1", "decision": "REJECTED", "note": "Inappropriate"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "REJECTED"

    # Verify content is removed from queue
    response = client_no_policy.get("/review/queue")
    assert response.json()["count"] == 0


def test_baseline_cannot_review_blocked_content(client_no_policy):
    """Test that blocked content cannot be reviewed"""
    # Submit content that gets blocked
    response = client_no_policy.post(
        "/content/submit",
        json={"user_id": "user1", "text": "This is spam"}
    )
    content_id = response.json()["content_id"]

    # Try to review it - should fail
    response = client_no_policy.post(
        f"/review/{content_id}",
        json={"reviewer_id": "reviewer1", "decision": "APPROVED"}
    )
    assert response.status_code == 409
    assert "cannot review" in response.json()["detail"]


def test_baseline_add_remove_blacklist(client_no_policy):
    """Test dynamic blacklist management"""
    # Add keyword
    response = client_no_policy.post(
        "/blacklist",
        json={},
        params={"keyword": "newbad"}
    )
    assert response.status_code == 200
    assert "newbad" in response.json()["keywords"]

    # Test it blocks
    response = client_no_policy.post(
        "/content/submit",
        json={"user_id": "user1", "text": "This contains newbad"}
    )
    assert response.json()["status"] == "BLOCKED"

    # Remove keyword
    response = client_no_policy.delete(
        "/blacklist",
        params={"keyword": "newbad"}
    )
    assert response.status_code == 200

    # Test it no longer blocks
    response = client_no_policy.post(
        "/content/submit",
        json={"user_id": "user1", "text": "This contains newbad"}
    )
    assert response.json()["status"] == "PENDING_REVIEW"


def test_baseline_get_content(client_no_policy):
    """Test retrieving content item"""
    response = client_no_policy.post(
        "/content/submit",
        json={"user_id": "user1", "text": "Content to retrieve"}
    )
    content_id = response.json()["content_id"]

    response = client_no_policy.get(f"/content/{content_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["content_id"] == content_id
    assert data["user_id"] == "user1"
    assert data["text"] == "Content to retrieve"


def test_baseline_get_nonexistent_content(client_no_policy):
    """Test retrieving non-existent content"""
    response = client_no_policy.get("/content/nonexistent")
    assert response.status_code == 404
