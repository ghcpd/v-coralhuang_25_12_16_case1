# Content Moderation Service with Policy-Driven Multi-Stage Decisions

## Overview

This is an **extended content moderation service** built on FastAPI that combines:
- **Baseline functionality**: Keyword blacklist blocking and manual review queue
- **Policy-driven automation**: Configurable multi-stage moderation decisions based on external policy files

The system automatically categorizes content into LOW/MEDIUM/HIGH risk levels and makes decisions accordingly while maintaining full backward compatibility with the original baseline.

## Baseline Functionality

The original system provides:

1. **Keyword Blacklist Blocking**: Content matching keywords in the blacklist is immediately blocked
2. **Manual Review Queue**: Non-blocked content enters a FIFO review queue for human decision
3. **Human Review Decisions**: Reviewers can approve or reject queued content

## New Feature: Policy-Driven Multi-Stage Moderation

### What's New

When a policy configuration is loaded, the service makes automated decisions BEFORE routing to manual review:

- **LOW Risk** → Automatically APPROVED (bypass manual review)
- **MEDIUM Risk** → Routed to PENDING_REVIEW (manual review required)
- **HIGH Risk** → Automatically REJECTED (or BLOCKED)

This dramatically reduces operational overhead while maintaining safety.

### Policy Configuration

Policies are defined in a **JSON file** (e.g., `policy.json`) and must NOT be hard-coded.

#### Policy File Format

```json
{
  "policies": [
    {
      "id": "policy_id_1",
      "name": "Human-readable policy name",
      "risk_level": "LOW|MEDIUM|HIGH",
      "rules": [
        {
          "id": "rule_id_1",
          "name": "Rule name",
          "type": "keyword|user",
          "keywords": ["word1", "word2"],  // for type: keyword
          "user_ids": ["user1", "user2"],  // for type: user
          "user_prefix": "prefix_"         // for type: user (prefix matching)
        }
      ],
      "composition": {
        "operator": "OR|AND",
        "rule_ids": ["rule_id_1", "rule_id_2"]
      }
    }
  ]
}
```

#### Rule Types

**1. Keyword Rules**
```json
{
  "id": "violence_kw",
  "name": "Violence Keywords",
  "type": "keyword",
  "keywords": ["kill", "murder", "bomb", "attack"]
}
```
Matches if any keyword appears in the content (case-insensitive substring match).

**2. User Rules**
```json
{
  "id": "bot_users",
  "name": "Bot User IDs",
  "type": "user",
  "user_prefix": "bot_"
}
```
Matches if:
- User ID is in the `user_ids` list (exact match), OR
- User ID starts with `user_prefix`

#### Rule Composition

**OR Composition** (default):
```json
"composition": {
  "operator": "OR",
  "rule_ids": ["rule_1", "rule_2"]
}
```
Policy matches if **ANY** rule matches.

**AND Composition**:
```json
"composition": {
  "operator": "AND",
  "rule_ids": ["rule_1", "rule_2"]
}
```
Policy matches only if **ALL** rules match.

### Design Decisions

**1. Policy Evaluation Order**
- Policies are checked FIRST (in definition order)
- Blacklist is checked SECOND (if no policy matches)
- This gives policies priority for automation decisions

**2. Extensibility**
- New rule types can be added by:
  1. Extending `BaseRule` class in `src/policy_engine.py`
  2. Updating the policy loader in `_load_from_dict()`
  3. No changes to core decision logic needed

**3. Response Clarity**
- Every decision includes a `reason` field explaining:
  - Which policy/rule matched
  - Why the decision was made
  - Full traceability for auditing

## Project Structure

```
.
├── baseline_moderation_service.py    # Original baseline (reference)
├── moderation_service.py              # Extended service with policies
├── policy.json                        # Example policy configuration
├── requirements.txt                   # Python dependencies
├── run_tests.ps1                      # Windows test script
├── run_tests.sh                       # Linux/macOS test script
├── README.md                          # This file
├── src/
│   ├── __init__.py
│   └── policy_engine.py               # Policy engine implementation
└── tests/
    ├── __init__.py
    ├── conftest.py                    # Pytest fixtures
    ├── test_baseline_regression.py    # Baseline functionality tests
    ├── test_policy_engine.py          # Policy engine unit tests
    └── test_moderation_service_with_policies.py  # Integration tests
```

## Installation & Setup

### Prerequisites
- Python 3.8+
- pip

### Option 1: Manual Setup

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Option 2: Using Docker

```bash
docker build -t moderation-service .
docker run -p 8000:8000 moderation-service
```

## Running the Service

```bash
# Start the FastAPI server
uvicorn moderation_service:app --reload --host 0.0.0.0 --port 8000
```

Access the service at `http://localhost:8000`

API documentation: `http://localhost:8000/docs` (Swagger UI)

## Running Tests

### One-Click Test Execution

**Windows (PowerShell):**
```powershell
.\run_tests.ps1
```

**Linux/macOS (Bash):**
```bash
chmod +x run_tests.sh
./run_tests.sh
```

### With Options

```powershell
# With coverage report
.\run_tests.ps1 -Coverage

# Verbose output
.\run_tests.ps1 -Verbose

# Both
.\run_tests.ps1 -Coverage -Verbose
```

### Manual Test Execution

```bash
# Activate venv first
pytest tests/ -v                          # All tests
pytest tests/test_baseline_regression.py  # Baseline only
pytest tests/test_policy_engine.py        # Policy engine only
pytest tests/test_moderation_service_with_policies.py  # Integration tests
pytest tests/ --cov=src --cov-report=html  # Coverage report
```

## API Endpoints

### Health Check
```
GET /health
Response: {"ok": true}
```

### Submit Content for Moderation
```
POST /content/submit
Request: {
  "user_id": "string",
  "text": "string"
}
Response: {
  "content_id": "uuid",
  "status": "APPROVED|PENDING_REVIEW|REJECTED|BLOCKED",
  "reason": "string"
}
```

### Get Content
```
GET /content/{content_id}
Response: ContentItem
```

### Get Review Queue
```
GET /review/queue?limit=20
Response: {
  "count": int,
  "items": [ContentItem, ...]
}
```

### Submit Review Decision
```
POST /review/{content_id}
Request: {
  "reviewer_id": "string",
  "decision": "APPROVED|REJECTED",
  "note": "string (optional)"
}
Response: {
  "content_id": "uuid",
  "status": "APPROVED|REJECTED",
  "reviewer_id": "string"
}
```

### Configuration
```
GET /config
Response: {
  "policy_enabled": bool,
  "policy_priority": "first|blacklist",
  "policies_count": int,
  "blacklist_keywords": int
}
```

### Blacklist Management
```
GET /blacklist
Response: {"keywords": [string, ...]}

POST /blacklist?keyword=string
Response: {"added": bool, "keywords": [...]}

DELETE /blacklist?keyword=string
Response: {"removed": bool, "keywords": [...]}
```

## Configuration & Usage Examples

### Example 1: Basic Setup (No Policies)
```python
from moderation_service import app, initialize_policy_engine

# Policies disabled - uses baseline behavior only
initialize_policy_engine(enable_policies=False)
```

### Example 2: With Policies
```python
from moderation_service import app, initialize_policy_engine

# Load policies from file
initialize_policy_engine(policy_file="policy.json", enable_policies=True)
```

### Example 3: Using the Service
```bash
# Submit content
curl -X POST http://localhost:8000/content/submit \
  -H "Content-Type: application/json" \
  -d '{"user_id": "bot_account_1", "text": "Hello world"}'

# Response (auto-approved by LOW risk policy):
{
  "content_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "APPROVED",
  "reason": "Auto-approved: [Auto-approve bot users] matched: Bot user IDs (user)"
}
```

## Test Coverage

The test suite covers:

### Baseline Regression Tests (`test_baseline_regression.py`)
- ✓ Keyword blacklist blocking works
- ✓ Non-blocked content goes to review queue
- ✓ Human review decisions (approve/reject)
- ✓ Content retrieval
- ✓ Dynamic blacklist management

### Policy Engine Tests (`test_policy_engine.py`)
- ✓ Keyword rule matching (case-insensitive)
- ✓ User ID exact matching
- ✓ User prefix matching
- ✓ OR composition (match if ANY rule matches)
- ✓ AND composition (match if ALL rules match)
- ✓ Policy loading from file

### Integration Tests (`test_moderation_service_with_policies.py`)
- ✓ Low-risk auto-approval
- ✓ Medium-risk routing to review
- ✓ High-risk auto-rejection
- ✓ Rule composition (AND/OR)
- ✓ Reason field clarity and traceability
- ✓ Backward compatibility with blacklist
- ✓ Review queue behavior with policies
- ✓ Fallback to manual review when no policy matches

**Total: 40+ test cases** covering all requirements

## Design & Extensibility

### Adding a New Rule Type

1. Create a new rule class in `src/policy_engine.py`:
```python
class CustomRule(BaseRule):
    def __init__(self, rule_id: str, rule_name: str, custom_param: str):
        super().__init__(rule_id, rule_name, RuleType.CUSTOM)
        self.custom_param = custom_param

    def evaluate(self, text: str, user_id: str) -> bool:
        # Your logic here
        return True/False
```

2. Update the policy loader in `PolicyEngine._load_from_dict()`:
```python
elif rule_type == "custom":
    rule = CustomRule(
        rule_id, rule_name,
        custom_param=rule_dict.get("custom_param")
    )
```

3. Add corresponding policy configuration in JSON:
```json
{
  "id": "custom_rule",
  "name": "My Custom Rule",
  "type": "custom",
  "custom_param": "value"
}
```

### Backward Compatibility

**Without policy configuration:**
```
Content → [No Policy] → [Blacklist Check] → BLOCKED or PENDING_REVIEW
```

**With policy configuration:**
```
Content → [Policy Check] → [Blacklist Check] → APPROVED/REJECTED/PENDING_REVIEW/BLOCKED
```

The baseline always works; policies are opt-in and non-breaking.

## Production Deployment

### Containerized Deployment

```bash
# Build image
docker build -t moderation-service:latest .

# Run container
docker run -p 8000:8000 \
  -v $(pwd)/policy.json:/app/policy.json \
  moderation-service:latest

# With docker-compose
docker-compose up -d
```

### Environment Variables

```bash
POLICY_FILE=policy.json  # Path to policy configuration
ENABLE_POLICIES=true     # Enable/disable policy engine
POLICY_PRIORITY=first    # "first" or "blacklist"
```

## Performance Considerations

- **Policy matching**: O(1) per rule (keyword: substring search, user: set lookup)
- **Composition evaluation**: O(n) where n = number of rules in composition
- **Queue operations**: O(1) for append, O(n) for list retrieval
- **In-memory storage**: All content/policies stored in memory (suitable for demonstration; use DB for production)

## Troubleshooting

**Tests fail with import errors:**
```bash
# Ensure you're in the virtual environment
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
```

**Policy file not found:**
- Check the file path in `initialize_policy_engine(policy_file="...")`
- Verify file is valid JSON: `python -m json.tool policy.json`

**Policies not being applied:**
```python
# Check configuration
curl http://localhost:8000/config
```

---

## Summary

This implementation provides:

✅ **Fully configurable policy-driven decisions** (not hard-coded)  
✅ **Multiple rule types** (keyword, user) with extensible design  
✅ **Rule composition** (AND/OR logic)  
✅ **Complete backward compatibility** with baseline  
✅ **Clear, traceable decision reasons**  
✅ **Comprehensive test coverage** (40+ tests, all automated)  
✅ **Production-ready code** (logging, error handling, type hints)  
✅ **One-click test execution** (Windows & Linux/macOS)  
✅ **Dockerfile** for containerized deployment  

All deliverables are complete and runnable.
