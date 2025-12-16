from typing import List, Dict, Any, Optional, Tuple
import json
import os
from dataclasses import dataclass


@dataclass
class PolicyResult:
    action: str
    reason: str
    policy_id: str


class Rule:
    def matches(self, user_id: str, text: str) -> Tuple[bool, str]:
        raise NotImplementedError()


class KeywordRule(Rule):
    def __init__(self, keywords: List[str]):
        self.keywords = [k.lower() for k in keywords]

    def matches(self, user_id: str, text: str) -> Tuple[bool, str]:
        lower = text.lower()
        matched = [k for k in self.keywords if k in lower]
        return (len(matched) > 0, f"keyword match: {matched}" if matched else "")


class UserRule(Rule):
    def __init__(self, user_ids: Optional[List[str]] = None, user_prefixes: Optional[List[str]] = None):
        self.user_ids = set(user_ids or [])
        self.user_prefixes = user_prefixes or []

    def matches(self, user_id: str, text: str) -> Tuple[bool, str]:
        if user_id in self.user_ids:
            return True, f"user id exact match: {user_id}"
        prefixes = [p for p in self.user_prefixes if user_id.startswith(p)]
        if prefixes:
            return True, f"user prefix match: {prefixes}"
        return False, ""


class CompositeRule(Rule):
    def __init__(self, operator: str, rules: List[Rule]):
        self.operator = operator.upper()
        self.rules = rules

    def matches(self, user_id: str, text: str) -> Tuple[bool, str]:
        reasons = []
        if self.operator == "AND":
            for r in self.rules:
                m, reason = r.matches(user_id, text)
                if not m:
                    return False, ""
                reasons.append(reason)
            return True, f"AND({';'.join(reasons)})"
        else:  # OR
            for r in self.rules:
                m, reason = r.matches(user_id, text)
                if m:
                    return True, f"OR({reason})"
            return False, ""


class Policy:
    def __init__(self, policy_dict: Dict[str, Any]):
        self.id = policy_dict.get("id") or policy_dict.get("name") or "unnamed"
        self.name = policy_dict.get("name", self.id)
        self.action = policy_dict["action"]
        self.reason = policy_dict.get("reason", "policy matched")
        self.condition = self._parse_condition(policy_dict.get("condition", {}))

    def _parse_condition(self, cond: Dict[str, Any]) -> Rule:
        t = cond.get("type")
        if t == "keyword":
            return KeywordRule(cond.get("keywords", []))
        if t == "user":
            return UserRule(cond.get("user_ids"), cond.get("user_prefixes"))
        if t == "composite":
            op = cond.get("operator", "OR")
            rules = [self._parse_condition(c) for c in cond.get("operands", [])]
            return CompositeRule(op, rules)
        # default empty rule that never matches
        return Rule()

    def matches(self, user_id: str, text: str) -> Optional[PolicyResult]:
        m, reason = self.condition.matches(user_id, text)
        if m:
            return PolicyResult(action=self.action, reason=f"{self.reason}; {reason}", policy_id=self.id)
        return None


class PolicyEngine:
    def __init__(self):
        self.policies: List[Policy] = []

    def load_from_file(self, path: str) -> None:
        if not path or not os.path.exists(path):
            self.policies = []
            return
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.policies = [Policy(p) for p in data]

    def evaluate(self, user_id: str, text: str) -> Optional[PolicyResult]:
        for p in self.policies:
            res = p.matches(user_id, text)
            if res:
                return res
        return None


# Single engine instance used by service
engine = PolicyEngine()

# Helper to load default file
DEFAULT_POLICY_FILE = os.environ.get("POLICY_FILE", "policy.json")
engine.load_from_file(DEFAULT_POLICY_FILE)
