# tests/conftest.py
"""Pytest configuration and fixtures"""

import pytest
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from moderation_service import app, clear_state, policy_engine, initialize_policy_engine
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """FastAPI test client"""
    clear_state()
    return TestClient(app)


@pytest.fixture
def sample_policy():
    """Sample policy configuration for testing"""
    return {
        "policies": [
            {
                "id": "low_risk_bots",
                "name": "Auto-approve bot users",
                "risk_level": "LOW",
                "rules": [
                    {
                        "id": "bot_users",
                        "name": "Bot user IDs",
                        "type": "user",
                        "user_prefix": "bot_"
                    }
                ],
                "composition": {
                    "operator": "OR",
                    "rule_ids": ["bot_users"]
                }
            },
            {
                "id": "medium_risk_new_users",
                "name": "Route new users to review",
                "risk_level": "MEDIUM",
                "rules": [
                    {
                        "id": "new_users",
                        "name": "New user IDs",
                        "type": "user",
                        "user_prefix": "new_user_"
                    }
                ],
                "composition": {
                    "operator": "OR",
                    "rule_ids": ["new_users"]
                }
            },
            {
                "id": "high_risk_violence",
                "name": "Auto-reject violent content",
                "risk_level": "HIGH",
                "rules": [
                    {
                        "id": "violence_keywords",
                        "name": "Violence keywords",
                        "type": "keyword",
                        "keywords": ["kill", "murder", "bomb", "attack"]
                    },
                    {
                        "id": "flagged_users",
                        "name": "Flagged user list",
                        "type": "user",
                        "user_ids": ["user_123", "user_456"]
                    }
                ],
                "composition": {
                    "operator": "OR",
                    "rule_ids": ["violence_keywords", "flagged_users"]
                }
            },
            {
                "id": "combined_rule",
                "name": "Require both keyword AND user match",
                "risk_level": "HIGH",
                "rules": [
                    {
                        "id": "spam_kw",
                        "name": "Spam keywords",
                        "type": "keyword",
                        "keywords": ["spam", "phishing"]
                    },
                    {
                        "id": "premium_users",
                        "name": "Premium user IDs",
                        "type": "user",
                        "user_ids": ["premium_1", "premium_2"]
                    }
                ],
                "composition": {
                    "operator": "AND",
                    "rule_ids": ["spam_kw", "premium_users"]
                }
            }
        ]
    }


@pytest.fixture
def policy_file(tmp_path, sample_policy):
    """Create a temporary policy.json file"""
    policy_path = tmp_path / "policy.json"
    with open(policy_path, "w") as f:
        json.dump(sample_policy, f)
    return str(policy_path)
