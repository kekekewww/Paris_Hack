"""合成資料回歸：人工備妥與案件變更均須明確確認當前版本。

此檔只使用隔離暫存資料庫及受控 provider，不呼叫模型或 OCR。
"""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from hashlib import sha256
import threading
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("CASE_DB_PATH", str(tmp_path / "manual-ready.sqlite3"))
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "1000")
    monkeypatch.setenv("LLM_PROVIDER", "grounded_rules")
    from backend.app.main import create_app

    return create_app()


@pytest.fixture
def client(app):
    with TestClient(app) as result:
        yield result


def create_case(client):
    response = client.post("/api/v1/cases", json={
        "entry_path": "direct", "claim_type_id": "inpatient",
        "conditions": {"cause": "illness", "surgery": "no", "payment_method": "other",
                       "diagnosis_has_surgery_details": "no"},
    })
    assert response.status_code == 201, response.text
    return response.json()


def document(case, identifier="application"):
    return next(item for item in case["documents"] if item["id"] == identifier)


def document_url(case):
    return f"/api/v1/cases/{case['id']}/documents/application"


@pytest.fixture
def synthetic_analyzer(monkeypatch):
    from backend.app.ocr import analyzer

    calls = []

    def controlled_analysis(data, filename, content_type, doc):
        analysis_id = str(uuid4())
        calls.append(analysis_id)
        box = {"page_number": 1, "x": 0.1, "y": 0.1, "width": 0.2, "height": 0.1}
        return {
            "analysis_id": analysis_id, "document_id": doc["id"], "analysis_status": "uncertain",
            "provider": "controlled_test_analyzer", "is_simulated": False, "extracted_fields": [],
            "findings": [{"id": f"{analysis_id}-name", "field": "name", "field_name": "姓名",
                          "severity": "warning", "message": "合成欄位待人工確認", "suggestion": "請人工核對",
                          "confidence": 0.5, "page_number": 1, "bounding_box": deepcopy(box),
                          "source_id": "cardif-claims", "requires_human_review": True}],
            "confidence": 0.5, "page_number": 1, "bounding_boxes": [box],
            "requires_human_review": True, "disclaimer": "合成測試資料，非正式核准。",
        }

    monkeypatch.setattr(analyzer, "analyze_document", controlled_analysis)
    return calls


def analyze(client, case):
    response = client.post(document_url(case) + "/analyze", files={
        "file": ("synthetic.pdf", b"%PDF-1.7\ncontrolled synthetic document", "application/pdf"),
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_case_exposes_structured_state_without_invented_identity_or_verification(client):
    case = create_case(client)
    assert type(case["revision"]) is int
    assert case["revision"] >= 0
    assert case["details"]["insured_relation"] == "unknown"
    assert case["details"]["policy_products"] == []
    assert case["details"]["visit_dates"]["discharge_pending"] is False
    assert case["dialogue_state"]["pending_question"] is None


def test_manual_ready_requires_a_current_analysis(client):
    case = create_case(client)
    response = client.patch(document_url(case), json={"status": "manual_ready"})
    assert response.status_code in {400, 409, 422}
    assert document(client.get(f"/api/v1/cases/{case['id']}").json())["status"] == "not_started"


def test_current_analysis_id_required_for_finding_confirmation(client, synthetic_analyzer):
    case = analyze(client, create_case(client))
    finding_id = document(case)["analysis"]["findings"][0]["id"]
    response = client.patch(document_url(case), json={"confirmed_findings": [finding_id]})
    assert response.status_code in {400, 409, 422}
    assert document(client.get(f"/api/v1/cases/{case['id']}").json())["confirmed_findings"] == []


def test_stale_analysis_id_cannot_confirm_current_findings(client, synthetic_analyzer):
    case = analyze(client, create_case(client))
    old_analysis_id = document(case)["analysis"]["analysis_id"]
    case = analyze(client, case)
    current = document(case)
    assert current["analysis"]["analysis_id"] != old_analysis_id
    response = client.patch(document_url(case), json={
        "analysis_id": old_analysis_id,
        "confirmed_findings": [current["analysis"]["findings"][0]["id"]],
    })
    assert response.status_code == 409, response.text
    assert document(client.get(f"/api/v1/cases/{case['id']}").json())["confirmed_findings"] == []


def test_manual_ready_does_not_skip_unconfirmed_findings(client, synthetic_analyzer):
    case = analyze(client, create_case(client))
    current = document(case)
    response = client.patch(document_url(case), json={
        "status": "manual_ready", "analysis_id": current["analysis"]["analysis_id"],
    })
    assert response.status_code in {400, 409, 422}, response.text
    unchanged = document(client.get(f"/api/v1/cases/{case['id']}").json())
    assert unchanged["status"] == "needs_attention"
    assert unchanged["analysis"] == current["analysis"]


def test_confirming_findings_alone_never_marks_ready(client, synthetic_analyzer):
    case = analyze(client, create_case(client))
    current = document(case)
    response = client.patch(document_url(case), json={
        "analysis_id": current["analysis"]["analysis_id"],
        "confirmed_findings": [finding["id"] for finding in current["analysis"]["findings"]],
    })
    assert response.status_code == 200, response.text
    changed = document(response.json())
    assert changed["confirmed_findings"]
    assert changed["status"] == "needs_attention"
    assert changed["analysis"] == current["analysis"]


def test_explicit_manual_ready_preserves_ocr_and_is_cleared_by_reanalysis(client, synthetic_analyzer):
    case = analyze(client, create_case(client))
    current = document(case)
    response = client.patch(document_url(case), json={
        "status": "manual_ready", "analysis_id": current["analysis"]["analysis_id"],
        "confirmed_findings": [finding["id"] for finding in current["analysis"]["findings"]],
    })
    assert response.status_code == 200, response.text
    ready = document(response.json())
    assert ready["status"] == "manual_ready"
    assert ready["analysis"] == current["analysis"]
    assert ready["analysis"]["requires_human_review"] is True
    repeated = document(analyze(client, response.json()))
    assert repeated["status"] == "needs_attention"
    assert repeated["confirmed_findings"] == []
    assert repeated["analysis"]["analysis_id"] != ready["analysis"]["analysis_id"]


def test_ready_document_cannot_be_reset_by_stale_analysis_confirmation(client, synthetic_analyzer):
    case = analyze(client, create_case(client))
    old_analysis_id = document(case)["analysis"]["analysis_id"]
    case = analyze(client, case)
    current = document(case)
    response = client.patch(document_url(case), json={
        "status": "manual_ready", "analysis_id": current["analysis"]["analysis_id"],
        "confirmed_findings": [finding["id"] for finding in current["analysis"]["findings"]],
    })
    assert response.status_code == 200, response.text
    ready = response.json()
    response = client.patch(document_url(case), json={"analysis_id": old_analysis_id, "confirmed_findings": []})
    assert response.status_code == 409, response.text
    assert document(client.get(f"/api/v1/cases/{case['id']}").json()) == document(ready)


def test_revoking_current_finding_confirmation_revokes_manual_ready(client, synthetic_analyzer):
    case = analyze(client, create_case(client))
    current = document(case)
    ready = client.patch(document_url(case), json={
        "status": "manual_ready", "analysis_id": current["analysis"]["analysis_id"],
        "confirmed_findings": [finding["id"] for finding in current["analysis"]["findings"]],
    })
    assert ready.status_code == 200
    response = client.patch(document_url(case), json={"analysis_id": current["analysis"]["analysis_id"], "confirmed_findings": []})
    assert response.status_code == 200
    result = document(response.json())
    assert result["status"] == "needs_attention"
    assert result["confirmed_findings"] == []
    assert result["analysis"] == current["analysis"]


def test_document_change_invalidates_pending_proposal_without_a_dead_confirmation_prompt(client, controlled_proposal):
    case = create_case(client)
    payload = proposed_change(client, case)
    changed = client.patch(document_url(case), json={"status": "uploaded"})
    assert changed.status_code == 200
    state = changed.json()["dialogue_state"]
    assert state["active_proposal"] is None
    assert (state.get("pending_question") or {}).get("kind") != "proposal"
    old = payload["response"]["proposal"]
    stale = client.patch(f"/api/v1/cases/{case['id']}", json={"proposal_action": "accept", "proposal_id": old["id"], "expected_revision": changed.json()["revision"]})
    assert stale.status_code == 409


def test_manual_precheck_and_required_exemption_stay_forbidden(client):
    case = create_case(client)
    for status, code in (("precheck_passed", "INVALID_DOCUMENT_STATUS"), ("not_applicable", "REQUIRED_DOCUMENT")):
        response = client.patch(document_url(case), json={"status": status})
        assert response.status_code in {400, 409, 422}
        assert response.json()["error"]["code"] == code


@pytest.fixture
def controlled_proposal(monkeypatch):
    from backend.app.ai import conversation
    from backend.app.ai.providers import _base

    async def reply(case, message, document_id=None):
        response = _base("您提出本次改為有手術，請確認這項修改。", "claim_suggestion")
        response["proposed_case_updates"] = {"conditions": {"surgery": "yes"}}
        return response

    monkeypatch.setattr(conversation, "respond", reply)


def proposed_change(client, case):
    response = client.post(f"/api/v1/cases/{case['id']}/messages", json={"message": "更正，本次有手術。"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["case"]["conditions"]["surgery"] == "no"
    assert document(payload["case"], "surgery")["applicability"] is False
    assert payload["response"]["proposed_case_updates"] == {"conditions": {"surgery": "yes"}}
    assert payload["response"]["proposal"]["id"]
    assert payload["response"]["proposal"]["base_revision"] == payload["case"]["revision"]
    return payload


def test_accept_current_proposal_updates_official_checklist_once(client, controlled_proposal):
    payload = proposed_change(client, create_case(client))
    case, proposal = payload["case"], payload["response"]["proposal"]
    response = client.patch(f"/api/v1/cases/{case['id']}", json={
        "proposal_action": "accept", "proposal_id": proposal["id"],
        "expected_revision": case["revision"],
    })
    assert response.status_code == 200, response.text
    changed = response.json()
    assert changed["conditions"]["surgery"] == "yes"
    assert document(changed, "surgery")["applicability"] is True
    assert changed["revision"] > case["revision"]
    duplicate = client.patch(f"/api/v1/cases/{case['id']}", json={
        "proposal_action": "accept", "proposal_id": proposal["id"],
        "expected_revision": changed["revision"],
    })
    assert duplicate.status_code == 409, duplicate.text


def test_reject_proposal_preserves_conditions_documents_and_known_facts(client, controlled_proposal):
    payload = proposed_change(client, create_case(client))
    case, proposal = payload["case"], payload["response"]["proposal"]
    response = client.patch(f"/api/v1/cases/{case['id']}", json={
        "proposal_action": "reject", "proposal_id": proposal["id"],
        "expected_revision": case["revision"],
    })
    assert response.status_code == 200, response.text
    rejected = response.json()
    for field in ("claim_type_id", "conditions", "details", "documents"):
        assert rejected[field] == case[field]
    assert rejected["dialogue_state"]["facts"] == case["dialogue_state"]["facts"]
    assert rejected["dialogue_state"]["pending_question"]["field"] == "correction"
    assert rejected["dialogue_state"]["pending_question"]["kind"] == "fact"
    again = client.patch(f"/api/v1/cases/{case['id']}", json={
        "proposal_action": "accept", "proposal_id": proposal["id"], "expected_revision": rejected["revision"],
    })
    assert again.status_code == 409, again.text


def test_stale_proposal_does_not_overwrite_new_conditions(client, controlled_proposal):
    payload = proposed_change(client, create_case(client))
    case, proposal = payload["case"], payload["response"]["proposal"]
    current = client.patch(f"/api/v1/cases/{case['id']}", json={"conditions": {"payment_method": "remittance"}})
    assert current.status_code == 200, current.text
    response = client.patch(f"/api/v1/cases/{case['id']}", json={
        "proposal_action": "accept", "proposal_id": proposal["id"], "expected_revision": case["revision"],
    })
    assert response.status_code == 409, response.text
    preserved = client.get(f"/api/v1/cases/{case['id']}").json()
    assert preserved["conditions"]["surgery"] == "no"
    assert preserved["conditions"]["payment_method"] == "remittance"
    assert document(preserved, "passbook")["applicability"] is True


def test_wrong_proposal_id_cannot_apply_even_with_current_revision(client, controlled_proposal):
    payload = proposed_change(client, create_case(client))
    case = payload["case"]
    response = client.patch(f"/api/v1/cases/{case['id']}", json={
        "proposal_action": "accept", "proposal_id": str(uuid4()), "expected_revision": case["revision"],
    })
    assert response.status_code == 409, response.text
    assert client.get(f"/api/v1/cases/{case['id']}").json()["conditions"]["surgery"] == "no"


def test_analysis_persists_content_hash_without_raw_file_bytes(client, synthetic_analyzer):
    case = analyze(client, create_case(client))
    metadata = document(case)["file"]
    expected = sha256(b"%PDF-1.7\ncontrolled synthetic document").hexdigest()
    assert metadata["sha256"] == expected
    assert set(metadata) == {"name", "type", "size", "sha256"}
    reloaded = client.get(f"/api/v1/cases/{case['id']}").json()
    assert document(reloaded)["file"] == metadata


def test_new_answer_consumes_old_proposal_even_with_latest_revision(client, controlled_proposal, monkeypatch):
    from backend.app.ai import conversation
    from backend.app.ai.providers import _base

    payload = proposed_change(client, create_case(client))
    case, proposal = payload["case"], payload["response"]["proposal"]

    async def no_change_reply(case, message, document_id=None):
        return _base("請依官方說明核對資料。")

    monkeypatch.setattr(conversation, "respond", no_change_reply)
    answer = client.post(f"/api/v1/cases/{case['id']}/messages", json={"message": "先不用修改。"})
    assert answer.status_code == 200, answer.text
    current = answer.json()["case"]
    assert current["revision"] > case["revision"]
    assert current["dialogue_state"]["active_proposal"] is None
    response = client.patch(f"/api/v1/cases/{case['id']}", json={
        "proposal_action": "accept", "proposal_id": proposal["id"], "expected_revision": current["revision"],
    })
    assert response.status_code == 409, response.text
    assert client.get(f"/api/v1/cases/{case['id']}").json()["conditions"] == current["conditions"]


def test_short_yes_refreshes_proposal_without_applying_it(client, controlled_proposal, monkeypatch):
    from backend.app.ai import conversation
    from backend.app.ai.providers import _base

    payload = proposed_change(client, create_case(client))
    case, old_proposal = payload["case"], payload["response"]["proposal"]

    async def confirmation_reply(case, message, document_id=None):
        response = _base("請點選確認修改以套用這份差異。", "clarification")
        response["pending_question"] = {"field": "confirm_claim", "kind": "proposal"}
        return response

    monkeypatch.setattr(conversation, "respond", confirmation_reply)
    answer = client.post(f"/api/v1/cases/{case['id']}/messages", json={"message": "是"})
    assert answer.status_code == 200, answer.text
    current = answer.json()["case"]
    refreshed = answer.json()["response"].get("proposal")
    assert current["conditions"] == case["conditions"]
    assert current["documents"] == case["documents"]
    assert refreshed is not None, "A short acceptance must retain a reviewable proposal, without applying it."
    assert refreshed["id"] != old_proposal["id"]
    assert refreshed["base_revision"] == current["revision"]
    assert answer.json()["response"]["proposed_case_updates"] == {"conditions": {"surgery": "yes"}}
    stale = client.patch(f"/api/v1/cases/{case['id']}", json={
        "proposal_action": "accept", "proposal_id": old_proposal["id"], "expected_revision": current["revision"],
    })
    assert stale.status_code == 409, stale.text
    accepted = client.patch(f"/api/v1/cases/{case['id']}", json={
        "proposal_action": "accept", "proposal_id": refreshed["id"], "expected_revision": current["revision"],
    })
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["conditions"]["surgery"] == "yes"
    duplicate = client.patch(f"/api/v1/cases/{case['id']}", json={
        "proposal_action": "accept", "proposal_id": refreshed["id"], "expected_revision": accepted.json()["revision"],
    })
    assert duplicate.status_code == 409, duplicate.text


def test_short_yes_after_rejection_cannot_resurrect_old_proposal(client, controlled_proposal, monkeypatch):
    from backend.app.ai import conversation
    from backend.app.ai.providers import _base

    payload = proposed_change(client, create_case(client))
    case, proposal = payload["case"], payload["response"]["proposal"]
    rejected = client.patch(f"/api/v1/cases/{case['id']}", json={
        "proposal_action": "reject", "proposal_id": proposal["id"], "expected_revision": case["revision"],
    })
    assert rejected.status_code == 200, rejected.text

    async def clarification(case, message, document_id=None):
        response = _base("請說明您想更正哪一項。", "clarification")
        response["pending_question"] = {"field": "correction", "kind": "fact"}
        return response

    monkeypatch.setattr(conversation, "respond", clarification)
    answer = client.post(f"/api/v1/cases/{case['id']}/messages", json={"message": "是"})
    assert answer.status_code == 200, answer.text
    current = answer.json()["case"]
    assert current["conditions"] == case["conditions"]
    assert current["dialogue_state"]["facts"] == case["dialogue_state"]["facts"]
    assert current["dialogue_state"]["active_proposal"] is None
    assert not answer.json()["response"]["proposed_case_updates"]
    assert not answer.json()["response"].get("proposal")
    accepted = client.patch(f"/api/v1/cases/{case['id']}", json={
        "proposal_action": "accept", "proposal_id": proposal["id"], "expected_revision": current["revision"],
    })
    assert accepted.status_code == 409, accepted.text


def test_case_patch_is_not_blocked_by_ocr_and_stale_analysis_is_not_saved(client, synthetic_analyzer, monkeypatch):
    from backend.app.ocr import analyzer

    original = analyzer.analyze_document
    started, release = threading.Event(), threading.Event()

    def controlled_analysis(*args):
        started.set()
        assert release.wait(3), "Controlled OCR was not released within its bounded test window."
        return original(*args)

    monkeypatch.setattr(analyzer, "analyze_document", controlled_analysis)
    case = create_case(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        analysis_future = pool.submit(client.post, document_url(case) + "/analyze", files={
            "file": ("synthetic.pdf", b"%PDF-1.7\ncontrolled synthetic document", "application/pdf"),
        })
        try:
            assert started.wait(1), "Controlled OCR did not start."
            patch_future = pool.submit(client.patch, f"/api/v1/cases/{case['id']}", json={
                "conditions": {"payment_method": "remittance"},
            })
            try:
                patch = patch_future.result(timeout=0.6)
                patched_before_release = True
            except FutureTimeoutError:
                patched_before_release = False
        finally:
            release.set()
        patch = patch_future.result(timeout=2)
        analysis_response = analysis_future.result(timeout=2)
    assert patched_before_release, "A case edit must complete while OCR is still waiting, before test release."
    assert patch.status_code == 200, patch.text
    assert analysis_response.status_code == 409, analysis_response.text
    assert analysis_response.json()["error"]["code"] == "ANALYSIS_CASE_CHANGED"
    current = client.get(f"/api/v1/cases/{case['id']}").json()
    assert current["conditions"]["payment_method"] == "remittance"
    assert document(current)["analysis"] is None
    assert document(current)["file"] is None
