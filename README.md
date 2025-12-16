# Content Moderation Service (Extended)

Overview
--------
This project contains a simple FastAPI-based Content Moderation Service. Baseline features (unchanged unless policies enabled):

- Keyword blacklist blocking (BLOCKED)
- Manual review queue for non-blocked content (PENDING_REVIEW)
- Human review decisions (APPROVED / REJECTED)

New Feature: Policy-driven Multi-stage Moderation
-------------------------------------------------
Policies are configuration-driven, loaded from an external file `policy.json` (JSON array). When policies are loaded, the service evaluates policies first. If a policy matches, its action is applied and is final. If no policy matches, the original blacklist behavior is used.

This choice (policy-first) enables administrators to express overrides or fine-grained automated decisions via policy configuration.

Policy file format (policy.json)
--------------------------------
A policy is a JSON object with fields:

- id (string): unique id
- name (string): human name
- condition (object): rule to match (see rule types)
- action (string): one of APPROVED, PENDING_REVIEW, REJECTED, BLOCKED
- reason (string): explanation used in the response

Supported condition types:
- keyword: {"type": "keyword", "keywords": ["foo", "bar"]}
- user: {"type": "user", "user_ids": ["u1"], "user_prefixes": ["bad_"]}
- composite: {"type": "composite", "operator": "AND"|"OR", "operands": [<condition>, ...]}

Example (policy.json included):

[
  {"id":"low_auto_approve","condition":{"type":"keyword","keywords":["friendly"]},"action":"APPROVED","reason":"Low risk"},
  {"id":"medium_manual_review","condition":{"type":"keyword","keywords":["maybe"]},"action":"PENDING_REVIEW","reason":"Medium"}
]

API Endpoints
-------------
- GET /health
- GET /blacklist
- POST /blacklist?keyword=...
- DELETE /blacklist?keyword=...

- POST /content/submit  (body: {user_id, text})
  - returns: {content_id, status, reason}
  - When policies are enabled, policies are evaluated first and take precedence.
  - Otherwise, blacklist behavior preserved.

- GET /content/{content_id}
- GET /review/queue
- POST /review/{content_id} (body: {reviewer_id, decision, note})

- GET /policies  (list loaded policies)
- POST /policies/reload?file_path=... (reload policies from file)
- POST /policies/clear (clear in-memory policies -> fallback to baseline behavior)

Running the service
-------------------
Install requirements and run with uvicorn:

python -m pip install -r requirements.txt
uvicorn baseline_moderation_service:app --reload

Running tests
-------------
Use the convenience script:

python run_tests

It will create a virtual environment, install dependencies, and run pytest.

Design Decisions
----------------
- Policy-first evaluation: policies are checked before blacklist. This allows policies to override baseline behavior intentionally.
- Policy engine is implemented to be extensible: new rule types can be added in `policy/engine.py` by implementing `Rule` subclasses and mapping them in `_parse_condition`.
- Policies loaded from external file (default `policy.json`) and can be reloaded/cleared via API for testability.

Files
-----
- baseline_moderation_service.py (main API)
- policy/engine.py (policy engine implementation)
- policy.json (example policies)
- requirements.txt
- run_tests (test runner script)
- tests/ (pytest test suite)

