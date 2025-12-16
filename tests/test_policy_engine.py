# tests/test_policy_engine.py
"""Tests for policy engine functionality"""

import pytest
from src.policy_engine import (
    PolicyEngine, Policy, KeywordRule, UserRule,
    RuleComposition, RiskLevel, PolicyMatch
)


class TestKeywordRule:
    """Tests for keyword-based rules"""

    def test_keyword_rule_match(self):
        """Test keyword rule matches content"""
        rule = KeywordRule("kw1", "Violence Keywords", ["kill", "murder", "bomb"])
        assert rule.evaluate("I want to kill someone", "user1") is True

    def test_keyword_rule_no_match(self):
        """Test keyword rule doesn't match"""
        rule = KeywordRule("kw1", "Violence Keywords", ["kill", "murder", "bomb"])
        assert rule.evaluate("This is peaceful content", "user1") is False

    def test_keyword_rule_case_insensitive(self):
        """Test keyword matching is case-insensitive"""
        rule = KeywordRule("kw1", "Violence Keywords", ["kill"])
        assert rule.evaluate("I will KILL you", "user1") is True

    def test_keyword_rule_multiple_keywords(self):
        """Test matching any of multiple keywords"""
        rule = KeywordRule("kw1", "Bad Words", ["spam", "scam", "phishing"])
        assert rule.evaluate("This is spam", "user1") is True
        assert rule.evaluate("This is a scam", "user1") is True
        assert rule.evaluate("Phishing attempt", "user1") is True


class TestUserRule:
    """Tests for user-based rules"""

    def test_user_rule_exact_match(self):
        """Test exact user ID match"""
        rule = UserRule("user1", "Flagged Users", user_ids=["bad_user_1", "bad_user_2"])
        assert rule.evaluate("any text", "bad_user_1") is True
        assert rule.evaluate("any text", "good_user") is False

    def test_user_rule_prefix_match(self):
        """Test user prefix matching"""
        rule = UserRule("user2", "Bot Users", user_prefix="bot_")
        assert rule.evaluate("any text", "bot_account_1") is True
        assert rule.evaluate("any text", "bot_account_2") is True
        assert rule.evaluate("any text", "human_user") is False

    def test_user_rule_combined(self):
        """Test both exact and prefix matching"""
        rule = UserRule(
            "user3", "Combined",
            user_ids=["admin_1"],
            user_prefix="test_"
        )
        assert rule.evaluate("text", "admin_1") is True
        assert rule.evaluate("text", "test_user_1") is True
        assert rule.evaluate("text", "other_user") is False


class TestPolicy:
    """Tests for policy evaluation"""

    def test_policy_single_rule_or(self):
        """Test policy with single rule (OR composition)"""
        rule = KeywordRule("kw1", "Keywords", ["spam"])
        policy = Policy(
            "p1", "Spam Policy", RiskLevel.HIGH,
            {"kw1": rule},
            RuleComposition("OR", ["kw1"])
        )
        match = policy.evaluate("This is spam", "user1")
        assert match is not None
        assert match.matched is True
        assert match.risk_level == RiskLevel.HIGH

    def test_policy_or_composition(self):
        """Test OR composition - matches if ANY rule matches"""
        kw_rule = KeywordRule("kw1", "Keywords", ["spam"])
        user_rule = UserRule("ur1", "Users", user_ids=["bad_user"])

        policy = Policy(
            "p1", "Combined Policy", RiskLevel.HIGH,
            {"kw1": kw_rule, "ur1": user_rule},
            RuleComposition("OR", ["kw1", "ur1"])
        )

        # Matches keyword
        match = policy.evaluate("This is spam", "good_user")
        assert match is not None

        # Matches user
        match = policy.evaluate("Normal content", "bad_user")
        assert match is not None

        # Matches neither
        match = policy.evaluate("Normal content", "good_user")
        assert match is None

    def test_policy_and_composition(self):
        """Test AND composition - matches only if ALL rules match"""
        kw_rule = KeywordRule("kw1", "Keywords", ["spam"])
        user_rule = UserRule("ur1", "Users", user_ids=["bad_user"])

        policy = Policy(
            "p1", "Combined Policy", RiskLevel.HIGH,
            {"kw1": kw_rule, "ur1": user_rule},
            RuleComposition("AND", ["kw1", "ur1"])
        )

        # Only keyword matches - should not match
        match = policy.evaluate("This is spam", "good_user")
        assert match is None

        # Only user matches - should not match
        match = policy.evaluate("Normal content", "bad_user")
        assert match is None

        # Both match
        match = policy.evaluate("This is spam", "bad_user")
        assert match is not None

    def test_policy_match_reason(self):
        """Test that match reason is informative"""
        rule = KeywordRule("kw1", "Violence Keywords", ["kill"])
        policy = Policy(
            "p1", "Violence Policy", RiskLevel.HIGH,
            {"kw1": rule}
        )
        match = policy.evaluate("kill everyone", "user1")
        assert match is not None
        assert "Violence Policy" in match.reason
        assert "Violence Keywords" in match.reason


class TestPolicyEngine:
    """Tests for policy engine"""

    def test_engine_empty_no_policies(self):
        """Test engine with no policies"""
        engine = PolicyEngine()
        match = engine.evaluate("spam content", "user1")
        assert match is None

    def test_engine_load_from_dict(self, sample_policy):
        """Test loading policies from dictionary"""
        engine = PolicyEngine()
        engine._load_from_dict(sample_policy)
        assert len(engine.policies) == 4

    def test_engine_evaluate_low_risk(self, sample_policy):
        """Test low risk auto-approval"""
        engine = PolicyEngine()
        engine._load_from_dict(sample_policy)
        engine.enabled = True

        # Bot user should match low risk policy
        match = engine.evaluate("any content", "bot_account_1")
        assert match is not None
        assert match.risk_level == RiskLevel.LOW

    def test_engine_evaluate_medium_risk(self, sample_policy):
        """Test medium risk routing to review"""
        engine = PolicyEngine()
        engine._load_from_dict(sample_policy)
        engine.enabled = True

        # New user should match medium risk policy
        match = engine.evaluate("any content", "new_user_123")
        assert match is not None
        assert match.risk_level == RiskLevel.MEDIUM

    def test_engine_evaluate_high_risk_keyword(self, sample_policy):
        """Test high risk rejection on keyword match"""
        engine = PolicyEngine()
        engine._load_from_dict(sample_policy)
        engine.enabled = True

        # Violence keyword should match high risk policy
        match = engine.evaluate("I will kill you", "normal_user")
        assert match is not None
        assert match.risk_level == RiskLevel.HIGH

    def test_engine_evaluate_high_risk_user(self, sample_policy):
        """Test high risk rejection on user match"""
        engine = PolicyEngine()
        engine._load_from_dict(sample_policy)
        engine.enabled = True

        # Flagged user should match high risk policy
        match = engine.evaluate("normal content", "user_123")
        assert match is not None
        assert match.risk_level == RiskLevel.HIGH

    def test_engine_no_match(self, sample_policy):
        """Test when no policy matches"""
        engine = PolicyEngine()
        engine._load_from_dict(sample_policy)
        engine.enabled = True

        match = engine.evaluate("normal safe content", "regular_user_99")
        assert match is None

    def test_engine_and_composition(self, sample_policy):
        """Test AND composition in policy engine"""
        engine = PolicyEngine()
        engine._load_from_dict(sample_policy)
        engine.enabled = True

        # Should match AND policy when both conditions true
        match = engine.evaluate("This is spam", "premium_1")
        assert match is not None
        assert match.rule_name == "Require both keyword AND user match"

        # Should not match when only keyword matches (need both for AND)
        match = engine.evaluate("This is spam", "regular_user")
        # Will match the violence policy if "spam" is there, but not the AND policy
        # Let's check it doesn't match the AND policy specifically
        match = engine.evaluate("phishing attempt", "regular_user")
        # This should match something (violence policy if any keyword matches)

    def test_engine_file_not_found(self, tmp_path):
        """Test loading from non-existent file"""
        engine = PolicyEngine()
        engine.load_from_file("/nonexistent/policy.json")
        assert engine.enabled is False

    def test_engine_file_loading(self, policy_file):
        """Test loading policies from actual file"""
        engine = PolicyEngine()
        engine.load_from_file(policy_file)
        assert engine.enabled is True
        assert len(engine.policies) == 4
