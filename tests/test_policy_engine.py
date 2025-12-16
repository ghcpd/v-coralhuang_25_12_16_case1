import json
import os


def build_service():
    # import the service module and use functions directly to avoid httpx/httpcore import
    import baseline_moderation_service as bm
    return bm


def test_baseline_behavior_no_policies():
    bm = build_service()
    # ensure policies cleared
    bm.clear_policies()

    # blocked by blacklist
    req = bm.SubmitContentRequest(user_id="u1", text="this is spam content")
    res = bm.submit_content(req)
    assert res.status.value == "BLOCKED"
    assert "Blacklisted keyword" in (res.reason or "")

    # non-blacklist -> pending review
    req = bm.SubmitContentRequest(user_id="u2", text="normal text")
    res = bm.submit_content(req)
    assert res.status.value == "PENDING_REVIEW"
    assert "manual review" in (res.reason or "").lower()


def test_low_risk_auto_approve():
    bm = build_service()
    base = os.path.dirname(__file__) + os.sep + ".."
    policy_path = os.path.abspath(os.path.join(base, "policy.json"))
    r = bm.reload_policies(file_path=policy_path)
    assert r["loaded"] == 4

    req = bm.SubmitContentRequest(user_id="user1", text="friendly message")
    res = bm.submit_content(req)
    assert res.status.value == "APPROVED"
    assert "low_auto_approve" in (res.reason or "")
    # reason must include match details from rule engine
    assert "keyword match" in (res.reason or "").lower()


def test_medium_risk_pending_review():
    bm = build_service()
    req = bm.SubmitContentRequest(user_id="user3", text="this is maybe concerning")
    res = bm.submit_content(req)
    assert res.status.value == "PENDING_REVIEW"
    assert "medium_manual_review" in (res.reason or "")


def test_high_risk_block_by_user_prefix():
    bm = build_service()
    req = bm.SubmitContentRequest(user_id="bad_alice", text="hello")
    res = bm.submit_content(req)
    assert res.status.value == "BLOCKED"
    assert "high_block_by_user" in (res.reason or "")


def test_composite_and_rejects():
    bm = build_service()
    # user prefix bad_ and keyword danger -> composite rejects
    req = bm.SubmitContentRequest(user_id="bad_bob", text="danger ahead")
    res = bm.submit_content(req)
    assert res.status.value == "REJECTED"
    assert "composite_reject" in (res.reason or "")
    assert "AND(" in (res.reason or "") or "and(" in (res.reason or "")


def test_policy_over_blacklist_ordering(tmp_path):
    bm = build_service()
    # Clear then create a policy that approves 'illegal' to prove policy precedence
    bm.clear_policies()
    pol = [
        {
            "id": "unsafe_override",
            "name": "Override illegal -> approve",
            "condition": {"type": "keyword", "keywords": ["illegal"]},
            "action": "APPROVED",
            "reason": "override for illegal"
        }
    ]
    pfile = tmp_path / "tmp_policy.json"
    pfile.write_text(json.dumps(pol))

    r = bm.reload_policies(file_path=str(pfile))
    assert r["loaded"] == 1

    # Now submit text containing 'illegal' which normally would be blocked by blacklist.
    req = bm.SubmitContentRequest(user_id="u9", text="this is illegal")
    res = bm.submit_content(req)
    assert res.status.value == "APPROVED"
    assert "unsafe_override" in (res.reason or "")


def test_composite_or_behavior(tmp_path):
    bm = build_service()
    bm.clear_policies()
    pol = [
        {
            "id": "or_policy",
            "name": "OR policy",
            "condition": {"type": "composite", "operator": "OR", "operands": [
                {"type": "keyword", "keywords": ["maybeor"]},
                {"type": "user", "user_prefixes": ["or_"]}
            ]},
            "action": "PENDING_REVIEW",
            "reason": "or composite"
        }
    ]
    pfile = tmp_path / "or.json"
    pfile.write_text(json.dumps(pol))
    r = bm.reload_policies(file_path=str(pfile))
    assert r["loaded"] == 1

    # matches by keyword
    req = bm.SubmitContentRequest(user_id="u1", text="maybeor match")
    res = bm.submit_content(req)
    assert res.status.value == "PENDING_REVIEW"

    # matches by user prefix
    req = bm.SubmitContentRequest(user_id="or_alice", text="hello")
    res = bm.submit_content(req)
    assert res.status.value == "PENDING_REVIEW"
