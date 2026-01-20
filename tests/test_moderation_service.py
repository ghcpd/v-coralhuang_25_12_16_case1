import os
import json
import tempfile
import sys
import os as _os
sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(__file__), '..')))
from moderation_logic import (
    submit_content_logic,
    get_review_queue_logic,
    CONTENTS,
    REVIEW_QUEUE,
    BLACKLIST,
)


def reset_state():
    CONTENTS.clear()
    REVIEW_QUEUE.clear()
    # preserve BLACKLIST default


def test_baseline_no_policy_block_on_blacklist():
    # ensure no policy file in environment
    os.environ.pop("POLICY_FILE", None)
    if os.path.exists("policy.json"):
        os.remove("policy.json")
    reset_state()

    # add a custom keyword to blacklist
    BLACKLIST.append("bannedword")

    data = submit_content_logic("user1", "This contains bannedword")
    assert data["status"] == "BLOCKED"
    assert "Blacklisted keyword" in data["reason"]

    # cleanup
    BLACKLIST.remove("bannedword")


def test_policy_low_risk_auto_approve():
    reset_state()
    policy = {
        "rules": [
            {"id": "r1", "type": "keyword", "keywords": ["safe"], "risk": "LOW", "action": "APPROVED"}
        ]
    }
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tf:
        json.dump(policy, tf)
        tf.flush()
        os.environ["POLICY_FILE"] = tf.name

        data = submit_content_logic("user1", "This is safe content")
        assert data["status"] == "APPROVED"
        assert "r1" in data["reason"]

    os.remove(tf.name)


def test_policy_medium_risk_pending_review():
    reset_state()
    policy = {
        "rules": [
            {"id": "r2", "type": "keyword", "keywords": ["question"], "risk": "MEDIUM", "action": "PENDING_REVIEW"}
        ]
    }
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tf:
        json.dump(policy, tf)
        tf.flush()
        os.environ["POLICY_FILE"] = tf.name

        data = submit_content_logic("user2", "I have a question")
        assert data["status"] == "PENDING_REVIEW"
        assert "r2" in data["reason"]

    os.remove(tf.name)


def test_policy_high_risk_reject():
    reset_state()
    policy = {
        "rules": [
            {"id": "r3", "type": "keyword", "keywords": ["hate"], "risk": "HIGH", "action": "REJECTED"}
        ]
    }
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tf:
        json.dump(policy, tf)
        tf.flush()
        os.environ["POLICY_FILE"] = tf.name

        data = submit_content_logic("user3", "I hate this")
        assert data["status"] == "REJECTED"
        assert "r3" in data["reason"]

    os.remove(tf.name)


def test_policy_composite_and_rule():
    reset_state()
    policy = {
        "rules": [
            {
                "id": "r4",
                "type": "composite",
                "operator": "ALL",
                "rules": [
                    {"type": "keyword", "keywords": ["spam"], "risk": "HIGH", "action": "REJECTED"},
                    {"type": "user", "users": ["user5"], "operator": "ANY", "risk": "HIGH", "action": "REJECTED"}
                ],
            }
        ]
    }
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tf:
        json.dump(policy, tf)
        tf.flush()
        os.environ["POLICY_FILE"] = tf.name

        data = submit_content_logic("user5", "spam content here")
        assert data["status"] == "REJECTED"
        assert "r4" in data["reason"]

    os.remove(tf.name)


def test_policy_composite_or_rule():
    reset_state()
    policy = {
        "rules": [
            {
                "id": "r5",
                "type": "composite",
                "operator": "ANY",
                "rules": [
                    {"type": "keyword", "keywords": ["spam"], "risk": "HIGH", "action": "REJECTED"},
                    {"type": "user", "users": ["user6"], "operator": "ANY", "risk": "HIGH", "action": "REJECTED"}
                ],
            }
        ]
    }
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tf:
        json.dump(policy, tf)
        tf.flush()
        os.environ["POLICY_FILE"] = tf.name

        # Only one of the OR conditions matches -> still REJECTED
        data = submit_content_logic("user6", "harmless content")
        assert data["status"] == "REJECTED"
        assert "r5" in data["reason"]

    os.remove(tf.name)


def test_policy_high_risk_blocked_action():
    reset_state()
    policy = {
        "rules": [
            {"id": "r6", "type": "keyword", "keywords": ["blacklisted"], "risk": "HIGH", "action": "BLOCKED"}
        ]
    }
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tf:
        json.dump(policy, tf)
        tf.flush()
        os.environ["POLICY_FILE"] = tf.name

        data = submit_content_logic("user7", "this is blacklisted content")
        assert data["status"] == "BLOCKED"
        assert "r6" in data["reason"]

    os.remove(tf.name)


def test_policy_first_over_blacklist():
    reset_state()
    # add a blacklist keyword that would normally block
    BLACKLIST.append("blocked")

    policy = {
        "rules": [
            {"id": "r7", "type": "keyword", "keywords": ["safe"], "risk": "LOW", "action": "APPROVED"}
        ]
    }
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tf:
        json.dump(policy, tf)
        tf.flush()
        os.environ["POLICY_FILE"] = tf.name

        data = submit_content_logic("user8", "safe and blocked")
        assert data["status"] == "APPROVED"
        assert "r7" in data["reason"]

    os.remove(tf.name)
    BLACKLIST.remove("blocked")


def test_policy_user_rule():
    reset_state()
    policy = {
        "rules": [
            {"id": "r8", "type": "user", "users": ["special_user"], "operator": "ANY", "risk": "HIGH", "action": "REJECTED"}
        ]
    }
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tf:
        json.dump(policy, tf)
        tf.flush()
        os.environ["POLICY_FILE"] = tf.name

        data = submit_content_logic("special_user", "anything")
        assert data["status"] == "REJECTED"
        assert "r8" in data["reason"]

    os.remove(tf.name)
