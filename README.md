# Content Moderation Service

This is an extended content moderation service built on FastAPI, featuring policy-driven multi-stage moderation.

## Baseline Functionality

The service provides:

1. **Keyword Blacklist Blocking**: Content matching blacklist keywords is immediately blocked.
2. **Manual Review Queue**: Non-blocked content is queued for human review.
3. **Human Review Decisions**: Reviewers can approve or reject queued content.

## New Feature: Policy-Driven Moderation

Added configurable, policy-driven moderation that automates decisions before manual review:

- **Low Risk** → Automatically approved
- **Medium Risk** → Sent to manual review
- **High Risk** → Automatically rejected or blocked

Policies are loaded from `policy.json` and support keyword-based and user-based rules with AND/OR logic.

## Policy Configuration

Policies are defined in `policy.json` with the following structure:

```json
{
  "policies": [
    {
      "name": "policy_name",
      "logic": "and|or",
      "rules": [
        {"type": "keyword", "value": "keyword_value"},
        {"type": "user", "value": "user_id"}
      ],
      "action": "approve|reject|block|review",
      "reason": "explanation"
    }
  ]
}
```

- `logic`: "and" (all rules must match) or "or" (any rule must match)
- `rules`: List of conditions
  - `keyword`: Matches if the keyword appears in the content text (case-insensitive)
  - `user`: Matches if the user_id equals the value (case-insensitive)
- `action`: Decision action
- `reason`: Explanation included in the response

## Execution Order

When both policies and blacklist are enabled:

1. Policies are evaluated first
2. If no policy matches, fallback to baseline behavior (blacklist check, then manual review)

This order prioritizes automated policy decisions while maintaining backward compatibility.

## Running the Service

### With Virtual Environment

1. Create and activate virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the service:
   ```bash
   uvicorn baseline_moderation_service:app --reload
   ```

### With Docker

1. Build the image:
   ```bash
   docker build -t moderation-service .
   ```

2. Run the container:
   ```bash
   docker run -p 8000:8000 moderation-service
   ```

The service will be available at http://localhost:8000

## API Endpoints

- `GET /health`: Health check
- `GET /blacklist`: List blacklist keywords
- `POST /blacklist`: Add keyword to blacklist
- `DELETE /blacklist`: Remove keyword from blacklist
- `POST /content/submit`: Submit content for moderation
- `GET /content/{content_id}`: Get content details
- `GET /review/queue`: Get review queue
- `POST /review/{content_id}`: Review content

## Running Tests

Run the test suite with:

```bash
./run_tests.bat
```

Or directly:

```bash
python -m pytest tests/ -v
```

Tests cover baseline behavior, policy-driven decisions, and edge cases.