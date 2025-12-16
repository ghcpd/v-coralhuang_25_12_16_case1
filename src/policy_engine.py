# src/policy_engine.py
# Policy-driven moderation engine with configurable rules and composition logic

import json
from typing import Dict, List, Optional, Any, Literal
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class PolicyMatch:
    """Result of policy evaluation"""
    matched: bool
    risk_level: RiskLevel
    rule_id: str
    rule_name: str
    reason: str


class RuleType(str, Enum):
    KEYWORD = "keyword"
    USER = "user"


class BaseRule:
    """Base class for all rule types"""

    def __init__(self, rule_id: str, rule_name: str, rule_type: RuleType):
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.rule_type = rule_type

    def evaluate(self, text: str, user_id: str) -> bool:
        """Return True if rule matches"""
        raise NotImplementedError


class KeywordRule(BaseRule):
    """Keyword-based rule: matches if text contains any keyword"""

    def __init__(self, rule_id: str, rule_name: str, keywords: List[str]):
        super().__init__(rule_id, rule_name, RuleType.KEYWORD)
        self.keywords = [kw.lower() for kw in keywords]

    def evaluate(self, text: str, user_id: str) -> bool:
        lower_text = text.lower()
        return any(kw in lower_text for kw in self.keywords)


class UserRule(BaseRule):
    """User-based rule: matches if user_id is in list or matches prefix"""

    def __init__(
        self,
        rule_id: str,
        rule_name: str,
        user_ids: Optional[List[str]] = None,
        user_prefix: Optional[str] = None,
    ):
        super().__init__(rule_id, rule_name, RuleType.USER)
        self.user_ids = set(user_ids or [])
        self.user_prefix = user_prefix

    def evaluate(self, text: str, user_id: str) -> bool:
        if user_id in self.user_ids:
            return True
        if self.user_prefix and user_id.startswith(self.user_prefix):
            return True
        return False


@dataclass
class RuleComposition:
    """Represents AND/OR composition of rules"""
    operator: Literal["AND", "OR"]
    rule_ids: List[str]


class Policy:
    """Represents a single moderation policy"""

    def __init__(
        self,
        policy_id: str,
        name: str,
        risk_level: RiskLevel,
        rules: Dict[str, BaseRule],
        composition: Optional[RuleComposition] = None,
    ):
        self.policy_id = policy_id
        self.name = name
        self.risk_level = risk_level
        self.rules = rules
        self.composition = composition or RuleComposition(operator="OR", rule_ids=list(rules.keys()))

    def evaluate(self, text: str, user_id: str) -> Optional[PolicyMatch]:
        """Evaluate policy against content. Returns PolicyMatch if matched, else None"""

        # Get rule evaluation results
        rule_results = {rule_id: rule.evaluate(text, user_id) for rule_id, rule in self.rules.items()}

        # Apply composition logic
        if self.composition.operator == "OR":
            # Match if ANY rule matches
            matched = any(rule_results.get(rid, False) for rid in self.composition.rule_ids)
            matched_rules = [rid for rid in self.composition.rule_ids if rule_results.get(rid, False)]
        elif self.composition.operator == "AND":
            # Match if ALL rules match
            matched = all(rule_results.get(rid, False) for rid in self.composition.rule_ids)
            matched_rules = self.composition.rule_ids if matched else []
        else:
            matched = False
            matched_rules = []

        if not matched:
            return None

        # Build reason from matched rules
        reason_parts = [f"[{self.name}]"]
        for rule_id in matched_rules:
            rule = self.rules[rule_id]
            reason_parts.append(f"{rule.rule_name} ({rule.rule_type.value})")

        reason = " matched: " + ", ".join(reason_parts)

        return PolicyMatch(
            matched=True,
            risk_level=self.risk_level,
            rule_id=self.policy_id,
            rule_name=self.name,
            reason=reason,
        )


class PolicyEngine:
    """Main policy engine that loads and evaluates policies"""

    def __init__(self):
        self.policies: Dict[str, Policy] = {}
        self.enabled = False

    def load_from_file(self, file_path: str) -> None:
        """Load policies from JSON file"""
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"Policy file {file_path} not found. Policies disabled.")
            self.enabled = False
            return

        try:
            with open(path, "r") as f:
                data = json.load(f)

            self._load_from_dict(data)
            self.enabled = True
            logger.info(f"Loaded {len(self.policies)} policies from {file_path}")
        except Exception as e:
            logger.error(f"Failed to load policies: {e}")
            self.enabled = False
            raise

    def _load_from_dict(self, data: Dict[str, Any]) -> None:
        """Load policies from dictionary (for testing)"""
        self.policies = {}

        for policy_dict in data.get("policies", []):
            policy_id = policy_dict["id"]
            name = policy_dict["name"]
            risk_level = RiskLevel(policy_dict["risk_level"])

            # Parse rules
            rules = {}
            for rule_dict in policy_dict.get("rules", []):
                rule_id = rule_dict["id"]
                rule_name = rule_dict["name"]
                rule_type = rule_dict["type"]

                if rule_type == "keyword":
                    rule = KeywordRule(rule_id, rule_name, rule_dict["keywords"])
                elif rule_type == "user":
                    rule = UserRule(
                        rule_id,
                        rule_name,
                        user_ids=rule_dict.get("user_ids"),
                        user_prefix=rule_dict.get("user_prefix"),
                    )
                else:
                    logger.warning(f"Unknown rule type: {rule_type}")
                    continue

                rules[rule_id] = rule

            # Parse composition
            composition_dict = policy_dict.get("composition")
            composition = None
            if composition_dict:
                composition = RuleComposition(
                    operator=composition_dict["operator"],
                    rule_ids=composition_dict["rule_ids"],
                )

            policy = Policy(policy_id, name, risk_level, rules, composition)
            self.policies[policy_id] = policy

    def evaluate(self, text: str, user_id: str) -> Optional[PolicyMatch]:
        """
        Evaluate all policies in order. Return first match (highest priority).
        Returns None if no policy matches.
        """
        if not self.enabled or not self.policies:
            return None

        for policy in self.policies.values():
            match = policy.evaluate(text, user_id)
            if match:
                return match

        return None
