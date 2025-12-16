# Content Moderation Service (Extended)

✅ This project extends the baseline content moderation service with a **policy-driven, multi-stage moderation engine** that can auto-approve, route-to-review, or auto-reject/block content based on external, configurable policies.

---

## Project layout

```
.
├── baseline_moderation_service.py   # main service (FastAPI optional import)
├── policy.json                      # external policy configuration (JSON list)
├── requirements.txt                  # dependencies for tests and optional FastAPI
├── run_tests                         # one-click test runner (python run_tests)
├── README.md
└── tests/
    └── test_policy_engine.py        # pytest-based coverage for required behaviors
```

---

## Baseline functionality (unchanged)

- Keyword blacklist blocking (substring match) — blocked content receives `BLOCKED` and a reason
- Submissions without blacklist hits go to manual review (`PENDING_REVIEW`) in the baseline
- Reviewers can `APPROVE` or `REJECT` queued items (final states: `APPROVED` / `REJECTED`)

If policies are disabled (or no policy file is present), the service behaves exactly like the baseline.

---

## New: Policy-driven moderation (high level)

- Policies are **NOT** hard-coded — they are loaded from `policy.json` (list of policy objects).
- Policy rules supported (extensible):
  - `keyword` rules (match any / all keywords)
  - `user` rules (explicit `ids` or `prefixes`)
  - `operator`: `AND` / `OR` composition across rules in a policy
- Policy `outcome` values: `LOW_RISK`, `MEDIUM_RISK`, `HIGH_RISK`.
  - `LOW_RISK` → auto `APPROVED`
  - `MEDIUM_RISK` → `PENDING_REVIEW` (queued)
  - `HIGH_RISK` → auto `REJECTED` or `BLOCKED` depending on policy `action` (e.g. `BLOCK`)
- Decision `reason` includes the matching policy name and matched rule for traceability.

Execution order: **Policy evaluation runs first and takes precedence over the legacy blacklist.**
Rationale: policies are explicit business rules and should be able to override the baseline blacklist (this reduces manual work and prevents configuration drift). This behavior is documented and covered by tests.

---

## `policy.json` (format & examples)

`policy.json` is a JSON array of policy objects. Example entries are included in the repository. Each policy contains:

- `name` (string) — optional friendly identifier
- `operator` (`AND` / `OR`) — how to combine the policy's `rules`
- `rules` — an array of rule objects; each rule has a `type`:
  - `keyword`: `{ "type": "keyword", "keywords": ["spam"], "match": "any" }` (match any or all)
  - `user`: `{ "type": "user", "ids": ["u1"], "prefixes": ["trusted_"] }`
- `outcome`: `LOW_RISK` / `MEDIUM_RISK` / `HIGH_RISK`
- `action` (optional): for `HIGH_RISK`, `BLOCK` (or `REJECT` / unspecified)

You can extend the design with new rule types without changing the core decision flow — the engine skips unknown rule types.

---

## Running the tests (one-click)

From the project root run:

```powershell
python run_tests
```

This creates a `.venv`, installs `requirements.txt`, and runs `pytest`.

---

## Design notes / key decisions

- **Policy-first execution** (policies override blacklist) — chosen to meet the product roadmap aim of reducing manual operations via explicit automation.
- The policy engine is file-backed and non-invasive: when policies are disabled/missing/malformed, the system falls back to baseline behavior to preserve compatibility.
- Tests focus on behavior (API function calls) so they run in constrained environments even if FastAPI/pydantic are not installed.

---

If you want any additional rule types (e.g. regex keyword match, sentiment thresholds, remote policy fetching), I can add those and tests the same way.
