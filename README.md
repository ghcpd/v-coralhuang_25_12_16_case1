# Baseline Content Moderation Service (extended)

✅ **Baseline features**:
- Keyword blacklist blocking (immediate BLOCKED)
- Manual review queue for PENDING_REVIEW
- Human reviewer decisions (APPROVED / REJECTED)

🔧 **New feature: Policy-driven multi-stage moderation**

This extension adds a configurable policy engine that can automatically approve, route to manual review, reject or block content based on external policies.

Key points:
- Policies are loaded from `policy.json` (JSON array of policies).
- Policy rules supported: **keyword**, **user**, and **composite (AND / OR)**.
- Policies are configuration-driven (no hard-coded rules).
- **Execution order:** Policies are evaluated *first* if enabled (default). If no policy matches, the existing blacklist behavior is used as a fallback.

Files added / modified

- `baseline_moderation_service.py` (modified): now consults the policy engine when `POST /content/submit` is called.
- `policy/engine.py` (new): lightweight, extensible policy decision engine.
- `policy.json` (new): example policy configuration used by tests.
- `tests/` (new): pytest suite covering baseline regression and policy-driven flows.
- `requirements.txt` (new): Python dependencies.
- `run_tests` (new): one-click test script (run with `python run_tests`).

Policy file format (example)

`policy.json` is a JSON array. Each policy is an object with keys:
- `id` (string) - unique id
- `name` (string) - optional human name
- `rule` (object) - rule definition (see types below)
- `action` (string) - one of `APPROVED`, `PENDING_REVIEW`, `REJECTED`, `BLOCKED`
- `reason` (string) - human-readable reason used in responses

Rule types:
- Keyword rule: `{ "type": "keyword", "keywords": ["spam", "buy now"] }`
- User rule: `{ "type": "user", "user_ids": ["bad_user"], "prefixes": ["spammer_"] }`
- Composite rule: `{ "type": "composite", "op": "AND", "rules": [ <subrules...> ] }` (op can be `AND` or `OR`)

Design notes

- Policies are evaluated in file order and **first-match wins**. This keeps resolution deterministic and easy to reason about. If you need priority, order policies accordingly.
- The policy engine is extensible: adding new rule types only requires implementing a new Rule subclass and parsing logic in `policy/engine.py`.
- Backward compatibility: set `POLICIES_ENABLED=0` (or any falsy value) to disable policies and restore exact baseline behavior.

Running the service and tests

1. Install dependencies:

   python -m pip install -r requirements.txt

2. Run tests:

   python run_tests

3. Run the service locally (dev):

   uvicorn baseline_moderation_service:app --reload

Environment & behavior

- `POLICY_FILE` environment variable can be used to point to a different policy JSON file path (default `policy.json`).
- `POLICIES_ENABLED` environment variable (default: enabled) toggles policy evaluation. When enabled, policy engine is consulted first; if it returns no decision, the blacklist is used.

Examples & Testing

- Submit content that matches policy `low_hello` (`"hello"`) → auto `APPROVED` with a policy reason.
- Submit content that contains `"buy now"` → `PENDING_REVIEW` (policy `medium_sales`).
- Submit from user `"bad_user"` → `REJECTED` (policy `high_spam_user`).
- Composite example: user `bad_bob` with text containing `"foo"` → `BLOCKED` (composite AND rule).

If you need any changes (different execution order, new rule types, or richer decision combining), I can update the engine and tests accordingly.
