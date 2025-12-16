import pytest
import subprocess
import time
import requests
import json
import os

BASE_URL = "http://127.0.0.1:8001"

@pytest.fixture(scope="session", autouse=True)
def start_server():
    # Start the server
    proc = subprocess.Popen(['uvicorn', 'baseline_moderation_service:app', '--host', '127.0.0.1', '--port', '8001'])
    time.sleep(3)  # Wait for server to start
    yield
    # Stop the server
    proc.terminate()
    proc.wait()

def setup_function():
    # Reset policies before each test
    # Since we can't directly access POLICIES, we need to restart or something, but for simplicity, assume tests are isolated
    pass

def teardown_function():
    # Clean up
    pass

def test_health():
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}

def test_blacklist_operations():
    # Test add
    response = requests.post(f"{BASE_URL}/blacklist", params={"keyword": "test"})
    assert response.status_code == 200
    assert "test" in response.json()["keywords"]

    # Test list
    response = requests.get(f"{BASE_URL}/blacklist")
    assert "test" in response.json()["keywords"]

    # Test remove
    response = requests.delete(f"{BASE_URL}/blacklist", params={"keyword": "test"})
    assert response.status_code == 200
    assert "test" not in response.json()["keywords"]

def test_baseline_blacklist_block():
    # No policy file, should use baseline
    response = requests.post(f"{BASE_URL}/content/submit", json={"user_id": "user1", "text": "This is spam"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "BLOCKED"
    assert "spam" in data["reason"]

def test_baseline_manual_review():
    # No policy, no blacklist hit
    response = requests.post(f"{BASE_URL}/content/submit", json={"user_id": "user1", "text": "This is normal content"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PENDING_REVIEW"
    assert "manual review" in data["reason"]

def test_policy_auto_approve():
    # Create policy file
    policies = [
        {
            "name": "auto_approve",
            "logic": "or",
            "rules": [{"type": "keyword", "value": "good"}],
            "action": "approve",
            "reason": "Good content"
        }
    ]
    with open('policy.json', 'w') as f:
        json.dump({"policies": policies}, f)
    requests.post(f"{BASE_URL}/reload_policies")

    response = requests.post(f"{BASE_URL}/content/submit", json={"user_id": "user1", "text": "This is good content"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "APPROVED"
    assert data["reason"] == "Good content"

def test_policy_auto_reject():
    policies = [
        {
            "name": "auto_reject",
            "logic": "or",
            "rules": [{"type": "keyword", "value": "bad"}],
            "action": "reject",
            "reason": "Bad content"
        }
    ]
    with open('policy.json', 'w') as f:
        json.dump({"policies": policies}, f)
    requests.post(f"{BASE_URL}/reload_policies")

    response = requests.post(f"{BASE_URL}/content/submit", json={"user_id": "user1", "text": "This is bad content"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "REJECTED"
    assert data["reason"] == "Bad content"

def test_policy_auto_block():
    policies = [
        {
            "name": "auto_block",
            "logic": "or",
            "rules": [{"type": "keyword", "value": "spam"}],
            "action": "block",
            "reason": "Spam blocked"
        }
    ]
    with open('policy.json', 'w') as f:
        json.dump({"policies": policies}, f)
    requests.post(f"{BASE_URL}/reload_policies")

    response = requests.post(f"{BASE_URL}/content/submit", json={"user_id": "user1", "text": "This is spam"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "BLOCKED"
    assert data["reason"] == "Spam blocked"

def test_policy_manual_review():
    policies = [
        {
            "name": "manual_review",
            "logic": "or",
            "rules": [{"type": "keyword", "value": "questionable"}],
            "action": "review",
            "reason": "Needs review"
        }
    ]
    with open('policy.json', 'w') as f:
        json.dump({"policies": policies}, f)
    requests.post(f"{BASE_URL}/reload_policies")

    response = requests.post(f"{BASE_URL}/content/submit", json={"user_id": "user1", "text": "This is questionable"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PENDING_REVIEW"
    assert data["reason"] == "Needs review"

def test_policy_and_logic():
    policies = [
        {
            "name": "and_test",
            "logic": "and",
            "rules": [
                {"type": "keyword", "value": "bad"},
                {"type": "user", "value": "user1"}
            ],
            "action": "reject",
            "reason": "AND match"
        }
    ]
    with open('policy.json', 'w') as f:
        json.dump({"policies": policies}, f)
    requests.post(f"{BASE_URL}/reload_policies")

    # Should match
    response = requests.post(f"{BASE_URL}/content/submit", json={"user_id": "user1", "text": "This is bad"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "REJECTED"
    assert data["reason"] == "AND match"

    # Should not match (missing keyword)
    response = requests.post(f"{BASE_URL}/content/submit", json={"user_id": "user1", "text": "This is good"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PENDING_REVIEW"  # Fallback to baseline

def test_policy_or_logic():
    policies = [
        {
            "name": "or_test",
            "logic": "or",
            "rules": [
                {"type": "keyword", "value": "good"},
                {"type": "user", "value": "trusted"}
            ],
            "action": "approve",
            "reason": "OR match"
        }
    ]
    with open('policy.json', 'w') as f:
        json.dump({"policies": policies}, f)
    requests.post(f"{BASE_URL}/reload_policies")

    # Match keyword
    response = requests.post(f"{BASE_URL}/content/submit", json={"user_id": "user2", "text": "This is good"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "APPROVED"
    assert data["reason"] == "OR match"

    # Match user
    response = requests.post(f"{BASE_URL}/content/submit", json={"user_id": "trusted", "text": "This is normal"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "APPROVED"
    assert data["reason"] == "OR match"

def test_get_content():
    response = requests.post(f"{BASE_URL}/content/submit", json={"user_id": "user1", "text": "Test content"})
    content_id = response.json()["content_id"]

    response = requests.get(f"{BASE_URL}/content/{content_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "user1"
    assert data["text"] == "Test content"

def test_review_queue():
    requests.post(f"{BASE_URL}/content/submit", json={"user_id": "user1", "text": "Pending content"})

    response = requests.get(f"{BASE_URL}/review/queue")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) >= 1

def test_review_content():
    response = requests.post(f"{BASE_URL}/content/submit", json={"user_id": "user1", "text": "Pending content"})
    content_id = response.json()["content_id"]

    response = requests.post(f"{BASE_URL}/review/{content_id}", json={"reviewer_id": "reviewer1", "decision": "APPROVED", "note": "Approved"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "APPROVED"

    # Check updated content
    response = requests.get(f"{BASE_URL}/content/{content_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "APPROVED"
    assert data["reviewer_id"] == "reviewer1"
    assert data["review_note"] == "Approved"