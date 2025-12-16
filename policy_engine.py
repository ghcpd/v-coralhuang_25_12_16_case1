import json
import os
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# Removed FastAPI dependency from policy engine to keep tests lightweight



class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

# Mapping risk -> default action
DEFAULT_ACTION = {
    RiskLevel.LOW: "APPROVED",
    RiskLevel.MEDIUM: "PENDING_REVIEW",
    RiskLevel.HIGH: "REJECTED",
}


def _match_keyword(text: str, rule: Dict[str, Any]) -> bool:
    keywords = rule.get("keywords") or []
    operator = (rule.get("operator") or "ANY").upper()
    text_lower = text.lower()
    if not keywords:
        return False
    matches = [kw.lower() in text_lower for kw in keywords]
    if operator == "ALL":
        return all(matches)
    # default to ANY
    return any(matches)


def _match_user(user_id: str, rule: Dict[str, Any]) -> bool:
    users = rule.get("users") or []
    operator = (rule.get("operator") or "ANY").upper()
    prefix = rule.get("prefix", False)
    if not users:
        return False
    if prefix:
        matches = [user_id.startswith(u) for u in users]
    else:
        matches = [user_id == u for u in users]
    if operator == "ALL":
        return all(matches)
    return any(matches)


def _eval_rule(rule: Dict[str, Any], text: str, user_id: str) -> Optional[Dict[str, Any]]:
    rtype = rule.get("type")
    if rtype == "keyword":
        if _match_keyword(text, rule):
            return rule
    elif rtype == "user":
        if _match_user(user_id, rule):
            return rule
    elif rtype == "composite":
        op = (rule.get("operator") or "ANY").upper()
        subrules: List[Dict[str, Any]] = rule.get("rules") or []
        matched = []
        for r in subrules:
            res = _eval_rule(r, text, user_id)
            if res:
                matched.append(res)
        if op == "ALL" and len(matched) == len(subrules):
            # composite fully matched -> determine action
            # If the composite defines an action, prefer it. Otherwise derive from subrules.
            if "action" in rule:
                return {**rule, "matched_subrules": matched}

            # Derive action from matched subrules: choose highest risk action
            # Reaction is similar to evaluate() logic: pick highest priority among matches
            def _prio(r):
                return {"LOW": 1, "MEDIUM": 2, "HIGH": 3}.get(r.get("risk", "LOW"), 1)

            best = max(matched, key=_prio, default=None)
            ret = {**rule, "matched_subrules": matched}
            if best and "action" in best:
                ret["action"] = best["action"]
                ret["risk"] = best.get("risk")
            return ret

        elif op == "ANY" and matched:
            # return first match inside composite or derive action
            if "action" in rule:
                return {**rule, "matched_subrules": matched}

            best = max(matched, key=lambda r: {"LOW": 1, "MEDIUM": 2, "HIGH": 3}.get(r.get("risk", "LOW"), 1), default=None)
            ret = {**rule, "matched_subrules": matched}
            if best and "action" in best:
                ret["action"] = best["action"]
                ret["risk"] = best.get("risk")
            return ret
    return None


class PolicyEngine:
    def __init__(self, policy_file: Optional[str] = None):
        self.policy_file = policy_file or os.environ.get("POLICY_FILE") or "policy.json"
        self.rules: List[Dict[str, Any]] = []
        if os.path.exists(self.policy_file):
            try:
                with open(self.policy_file, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    self.rules = data.get("rules", [])
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid policy file: {e}")
        # if file missing -> rules stay empty => no policy

    def evaluate(self, text: str, user_id: str) -> Tuple[Optional[str], Optional[str]]:
        # returns (action, reason)
        if not self.rules:
            return None, None

        matched_rules: List[Tuple[Dict[str, Any], int]] = []
        for rule in self.rules:
            res = _eval_rule(rule, text, user_id)
            if res:
                # derive severity priority: HIGH(3) > MEDIUM(2) > LOW(1)
                prio = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}.get(res.get("risk", "LOW"), 1)
                matched_rules.append((res, prio))

        if not matched_rules:
            return None, None

        # pick highest priority rule
        matched_rules.sort(key=lambda x: x[1], reverse=True)
        best_rule = matched_rules[0][0]
        risk = best_rule.get("risk", "LOW").upper()
        action = best_rule.get("action") or DEFAULT_ACTION.get(RiskLevel(risk), "PENDING_REVIEW")
        # create reason string
        rule_id = best_rule.get("id") or "<unnamed>"
        reason = f"Policy rule '{rule_id}' matched with risk {risk}. Action: {action}"
        return action, reason
