"""The model receives an executable flat evidence example; unsafe shapes stay rejected."""
import copy
import json

import pytest

from backend.app.ai.providers import AIError
from backend.app.ai.retrieval import OfficialRetriever
from backend.app.ai.semantic_dialogue import FACTS, prompt_for, request_content, validate_semantics


MESSAGE = "媽媽因疾病在3/2住院，3/4接受關節修復手術，還沒出院。"


def content():
    return request_content({"claim_type_id": None, "conditions": {}, "details": {}, "dialogue_state": {"facts": {}, "details": {}}, "messages": [], "revision": 0}, MESSAGE)


def generated(details):
    facts = {name: {"value": "unknown", "turn": None, "quote": ""} for name in FACTS}
    for field, value, quote in [("cause", "illness", "因疾病"), ("inpatient", "yes", "3/2住院"), ("surgery", "yes", "接受關節修復手術")]:
        facts[field] = {"value": value, "turn": 1, "quote": quote}
    return {"facts": facts, "question": "confirm_claim", "message": "請確認本次就醫資訊。", "details": details}


def invalid():
    raise AIError("INVALID_LLM_RESPONSE", "synthetic contract rejection", 503)


def test_prompt_supplies_a_flat_date_evidence_example_accepted_by_the_unchanged_validator():
    context = content()
    examples = [line.removeprefix("DETAILS_EXAMPLE_JSON=") for line in prompt_for(context).splitlines() if line.startswith("DETAILS_EXAMPLE_JSON=")]
    assert len(examples) == 1, "The nested-date live failure needs an explicit flat JSON evidence example"
    details = json.loads(examples[0])
    assert "visit_dates" not in details
    assert {"visit_dates.admission", "visit_dates.discharge_pending", "surgery_date"} <= set(details)
    assert all(set(evidence) == {"value", "turn", "quote"} for evidence in details.values())
    result = validate_semantics(generated(details), context, OfficialRetriever(), invalid)
    assert result["dialogue_state"]["details"]["visit_dates"]["admission"] == "3/2"
    assert result["dialogue_state"]["details"]["surgery_date"] == "3/4"
    assert result["dialogue_state"]["details"]["visit_dates"]["discharge_pending"] is True


@pytest.mark.parametrize("details", [
    {"visit_dates": {"admission": {"value": "10/14", "turn": 1, "quote": "10/14住院"}}},
    {"visit_dates.admission": {"value": "2026/10/14", "turn": 1, "quote": "10/14住院"}},
    {"visit_dates.admission": {"value": "10/16", "turn": 1, "quote": MESSAGE}},
    {"visit_dates.admission": {"value": "姓名：王小明 0912345678", "turn": 1, "quote": MESSAGE}},
])
def test_flat_schema_guidance_does_not_relax_structure_dates_or_privacy(details):
    with pytest.raises(AIError):
        validate_semantics(generated(copy.deepcopy(details)), content(), OfficialRetriever(), invalid)


def test_workflow_prompt_uses_neutral_compatibility_ack_and_keeps_server_question_authority():
    context = content()
    examples = [line.removeprefix("WORKFLOW_ACK_JSON=") for line in prompt_for(context).splitlines()
                if line.startswith("WORKFLOW_ACK_JSON=")]
    assert len(examples) == 1, "Unused model prose must not compete with the server's confirmed workflow"
    ack = json.loads(examples[0])
    assert ack == {"question": "scope", "message": "已記錄您提供的資訊。"}
    payload = generated({})
    payload.update(ack)
    result = validate_semantics(payload, context, OfficialRetriever(), invalid)
    assert result["pending_question"]["field"] == "payment_method"
    assert result["message"] == result["pending_question"]["prompt"]
    assert result["message"] != ack["message"]
    assert result["dialogue_state"]["facts"]["inpatient"] == "yes"
    assert result["proposed_case_updates"] == {}


@pytest.mark.parametrize("message", [None, "長" * 501, "保證可以給付100萬元", "理賠資格已核准", "姓名：王小明，電話0912345678"])
def test_neutral_ack_guidance_keeps_existing_message_safety_rejections(message):
    payload = generated({})
    payload["message"] = message
    with pytest.raises(AIError):
        validate_semantics(payload, content(), OfficialRetriever(), invalid)
