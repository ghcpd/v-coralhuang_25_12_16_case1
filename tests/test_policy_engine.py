import os
import json
import tempfile
# Import the service directly - module is clean and has no FastAPI/pydantic imports
import baseline_moderation_service as svc


def setup_module(module):
    # Reload policies from disk and reset state
    svc.get_policy_engine().reload_policies()
    svc.content_store.clear()
    svc.review_queue.clear()


def reset_state():
    # Reset global stores between tests
    svc.BLACKLIST = ["spam", "scam", "phishing"]
    svc.content_store.clear()
    svc.review_queue.clear()
    svc.get_policy_engine().reload_policies()


def test_baseline_behavior_when_policies_disabled():
    """Test that without policies, the baseline blacklist + manual review behavior works."""
    reset_state()
    # Temporarily disable policies by creating empty policy file
    engine = svc.get_policy_engine()
    engine.enabled = False
    engine.policies = []
    
    # Submit clean content (no blacklist hit) → should go to manual review
    result = svc.submit_content(user_id="user1", text="Hello world")
    assert result["status"] == svc.ContentStatus.PENDING_REVIEW
    assert result["content_id"] in svc.review_queue
    
    # Submit blacklisted content → should be blocked
    result = svc.submit_content(user_id="user2", text="This is spam")
    assert result["status"] == svc.ContentStatus.BLOCKED
    assert "spam" in result["reason"].lower()


def test_low_risk_auto_approval():
    """Test LOW_RISK policy outcome → auto-approve."""
    reset_state()
    
    # Verify policy.json has a LOW_RISK policy (trusted user prefix)
    engine = svc.get_policy_engine()
    assert engine.enabled, "Policies should be loaded from policy.json"
    
    # Submit content matching LOW_RISK policy (trusted_ prefix user)
    result = svc.submit_content(user_id="trusted_user123", text="Hello")
    assert result["status"] == svc.ContentStatus.APPROVED
    assert "policy" in result["reason"].lower() or "auto-approved" in result["reason"].lower()
    assert result["content_id"] not in svc.review_queue


def test_medium_routing_to_manual_review():
    """Test MEDIUM_RISK policy outcome → queue for review."""
    reset_state()
    
    # Submit content matching MEDIUM_RISK policy (promotional keyword)
    result = svc.submit_content(user_id="user1", text="Check out this promotional offer")
    assert result["status"] == svc.ContentStatus.PENDING_REVIEW
    assert result["content_id"] in svc.review_queue
    assert "policy" in result["reason"].lower()


def test_high_risk_block_and_reject():
    """Test HIGH_RISK policy outcome → auto-block."""
    reset_state()
    
    # Submit content matching HIGH_RISK policy (scam keyword)
    result = svc.submit_content(user_id="user1", text="This is a scam offer")
    assert result["status"] == svc.ContentStatus.BLOCKED
    assert "policy" in result["reason"].lower() or "blocked" in result["reason"].lower()
    assert result["content_id"] not in svc.review_queue


def test_and_rule_requires_all_conditions():
    """Test AND operator in policies — all rules must match."""
    reset_state()
    
    # Submit content that matches only ONE condition of an AND policy
    # (should NOT match the policy)
    result = svc.submit_content(user_id="user1", text="urgent")
    # Should fall back to baseline (no blacklist hit → manual review)
    assert result["status"] == svc.ContentStatus.PENDING_REVIEW
    
    # Submit content matching ALL conditions of an AND policy
    result = svc.submit_content(user_id="user1", text="urgent action required")
    # Should match the HIGH_RISK AND policy
    assert result["status"] == svc.ContentStatus.BLOCKED


def test_policy_can_override_blacklist():
    """Test that policies take precedence over the baseline blacklist."""
    reset_state()
    
    # Add "spam" to blacklist
    svc.BLACKLIST = ["spam"]
    
    # Submit content with "spam" keyword but from trusted user
    # Policy (LOW_RISK for trusted_) should override blacklist
    result = svc.submit_content(user_id="trusted_admin", text="spam filter test")
    assert result["status"] == svc.ContentStatus.APPROVED
    assert "policy" in result["reason"].lower() or "auto-approved" in result["reason"].lower()
