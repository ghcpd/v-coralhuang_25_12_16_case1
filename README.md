# Baseline Content Moderation Service (with Policy-driven engine)

This repository implements a **baseline content moderation service** (FastAPI) with an **extensible, policy-driven moderation engine**.  The new feature allows automated decisions (auto‑approve / auto‑reject / send to manual review) based on external policy rules.

## 🔎 Summary

- Baseline behavior (blacklist + manual review) is preserved and works unchanged when policies are **disabled**.
- When a policy file (JSON) is present and enabled, the request flow is **policy-first**:
  1. Evaluate policy rules for the submitted content.
  2. If a rule matches → apply the configured action (`APPROVED`, `REJECTED`, `PENDING_REVIEW`, `BLOCKED`).
  3. If no rule matches → fall back to original blacklist + manual review behavior.

## 🧭 Policy file (JSON)

Policies are **not hard-coded**. Create a `policy.json` (or point `POLICY_FILE` environment variable to any path) with the following shape:

```json
{
  "rules": [
    {
      "id": "r1",
      "type": "keyword",
      "keywords": ["safe", "welcome"],
      "operator": "ANY",            // ALL or ANY (default ANY)
      "risk": "LOW",
      "action": "APPROVED"
    },
    {
      "id": "r2",
      "type": "user",
      "users": ["user123"],
      "prefix": false,
      "operator": "ANY",
      "risk": "HIGH",
      "action": "REJECTED"
    },
    {
      "id": "composite1",
      "type": "composite",
      "operator": "ALL",            /* ANY / ALL */
      "rules": [
        {"type": "keyword", "keywords": ["spam"], "risk": "HIGH", "action": "REJECTED"},
        {"type": "user", "users": ["userX"], "operator": "ANY", "risk": "HIGH", "action": "REJECTED"}
      ]
    }
  ]
}
```

**Rule types supported**:
- `keyword` — matches if (any/all) keywords appear in the text.
- `user` — matches exact user ids or prefix matches.
- `composite` — composition of sub-rules with `operator` (ALL/ANY).

**Extensibility**: new rule types can be added in `policy_engine.py` without changing main app flow.

## ⚙️ How to run

1. Install **Python 3.11+** (the recommended environment for the included deps).
2. Install dependencies and run tests via the provided script:

```bash
# Unix/Mac
bash run_tests.sh
```

```cmd
:: Windows PowerShell
run_tests.bat
```

3. Run the service (example):

```bash
uvicorn baseline_moderation_service:app --reload
```

4. Set `POLICY_FILE` environment var to point to your policy JSON file if you want to enable rules.

## ✅ Tests

- `pytest -q` runs the suite in `tests/`.
- Tests cover:
  - Baseline behavior (blacklist, manual review)
  - Low/medium/high risk policy actions
  - Rule composition (AND / OR)
  - Reason field traceability (policy id included)

## 📌 Design decisions

- **Policy-first design**: when a policy file exists and a rule matches, the decision is made by policy rules; otherwise, we fall back to the originating blacklist behavior to preserve backwards compatibility.
- **Policy format** is intentionally JSON to keep configuration external and human-editable.
- The engine is **extensible**: to add a new rule type, implement matching logic in `policy_engine.py` and add the rule type to supported set.

---

**Files added**:
- `policy_engine.py` — policy evaluation engine.
- `tests/test_moderation_service.py` — pytest tests.
- `run_tests.sh` / `run_tests.bat` — single command to run tests in a clean venv.
- `requirements.txt` — pinned runtime/test dependencies.
