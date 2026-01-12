import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple


class Rule:
    def matches(self, text: str, user_id: str) -> bool:
        raise NotImplementedError()


class KeywordRule(Rule):
    def __init__(self, keywords: List[str]):
        self.keywords = [k.lower() for k in keywords]

    def matches(self, text: str, user_id: str) -> bool:
        lower = text.lower()
        return any(k in lower for k in self.keywords)


class UserRule(Rule):
    def __init__(self, user_ids: Optional[List[str]] = None, prefixes: Optional[List[str]] = None):
        self.user_ids = set(user_ids or [])
        self.prefixes = prefixes or []

    def matches(self, text: str, user_id: str) -> bool:
        if user_id in self.user_ids:
            return True
        for p in self.prefixes:
            if user_id.startswith(p):
                return True
        return False


class CompositeRule(Rule):
    def __init__(self, op: str, rules: List[Rule]):
        self.op = op.upper()
        self.rules = rules

    def matches(self, text: str, user_id: str) -> bool:
        if self.op == "AND":
            return all(r.matches(text, user_id) for r in self.rules)
        else:
            # default OR
            return any(r.matches(text, user_id) for r in self.rules)


class Policy:
    def __init__(self, policy: Dict[str, Any]):
        self.id = policy.get("id")
        self.name = policy.get("name")
        self.action = policy.get("action")  # APPROVED/PENDING_REVIEW/REJECTED/BLOCKED
        self.reason = policy.get("reason")
        self.rule = self._parse_rule(policy.get("rule"))

    def _parse_rule(self, data: Dict[str, Any]) -> Rule:
        if not data or "type" not in data:
            raise ValueError("invalid rule")
        t = data["type"].lower()
        if t == "keyword":
            return KeywordRule(data.get("keywords", []))
        elif t == "user":
            return UserRule(data.get("user_ids"), data.get("prefixes"))
        elif t == "composite":
            op = data.get("op", "OR")
            subrules = [self._parse_rule(r) for r in data.get("rules", [])]
            return CompositeRule(op, subrules)
        else:
            raise ValueError(f"unknown rule type {t}")

    def matches(self, text: str, user_id: str) -> bool:
        return self.rule.matches(text, user_id)


class PolicyEngine:
    def __init__(self, path: str = "policy.json"):
        self.path = path
        self.policies: List[Policy] = []
        self._mtime: Optional[float] = None
        self._load_if_changed()

    def _load_if_changed(self):
        try:
            st = os.stat(self.path)
        except FileNotFoundError:
            # no policy file
            self.policies = []
            self._mtime = None
            return
        if self._mtime is None or st.st_mtime > self._mtime:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.policies = [Policy(p) for p in data]
            self._mtime = st.st_mtime

    def decide(self, text: str, user_id: str) -> Optional[Tuple[str, str]]:
        """Return (action, reason) if any policy matches, otherwise None.
        First-match wins (policies ordered in file)."""
        self._load_if_changed()
        for p in self.policies:
            try:
                if p.matches(text, user_id):
                    reason = f"policy:{p.id} name:{p.name} -> {p.reason or ''}".strip()
                    return p.action, reason
            except Exception:
                # ignore faulty policy/rule to be robust
                continue
        return None


# singleton
_default_engine: Optional[PolicyEngine] = None


def get_engine(path: Optional[str] = None) -> PolicyEngine:
    global _default_engine
    if _default_engine is None:
        _default_engine = PolicyEngine(path or os.environ.get("POLICY_FILE", "policy.json"))
    return _default_engine


if __name__ == "__main__":
    e = get_engine()
    print(f"Loaded {len(e.policies)} policies from {e.path}")
