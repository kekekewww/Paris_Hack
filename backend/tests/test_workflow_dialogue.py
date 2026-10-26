"""Structured dialogue regressions; synthetic transport, never a real LLM claim."""
import copy

import pytest

from backend.app.ai.providers import AIError, validate_assistant_response
from backend.app.ai.retrieval import OfficialRetriever
from backend.app.ai.semantic_dialogue import FACTS, request_content, validate_semantics


def item(claim=None, **conditions):
    return {"claim_type_id": claim, "conditions": {"cause": "unknown", "surgery": "unknown", "receipt_type": "unknown", "payment_method": "unknown", **conditions},
            "details": {}, "dialogue_state": {"facts": {}, "deferred_fields": [], "pending_question": None}, "messages": [], "revision": 2}


def generated(content, **known):
    facts = {field: {"value": "unknown", "turn": None, "quote": ""} for field in FACTS}
    for field, (value, quote) in known.items():
        turn = next(turn for turn in reversed(content["dialogue"]) if turn["role"] == "user" and quote in turn["content"])
        facts[field] = {"value": value, "turn": turn["turn"], "quote": quote}
    return {"facts": facts, "question": "confirm_claim", "message": "請確認本次就醫資訊。"}


def invalid():
    raise AIError("INVALID_LLM_RESPONSE", "invalid", 503)


def answer(case, message, **known):
    before = copy.deepcopy(case)
    content = request_content(case, message)
    result = validate_semantics(generated(content, **known), content, OfficialRetriever(), invalid)
    assert case == before
    return result


def test_admission_does_not_skip_checklist_condition_question():
    result = answer(item(), "媽媽住院三天，有手術", inpatient=("yes", "住院三天"), surgery=("yes", "有手術"))
    assert result["response_type"] == "clarification"
    assert result["pending_question"]["field"] == "cause"
    assert result["proposed_case_updates"] == {}
    assert result["dialogue_state"]["facts"]["inpatient"] == "yes"


@pytest.mark.parametrize("field", ["cause", "surgery", "receipt_type", "payment_method"])
def test_unknown_condition_can_be_deferred_without_reasking(field):
    case = item(cause="illness", surgery="no", receipt_type="daily", payment_method="other")
    case["conditions"][field] = "unknown"
    case["dialogue_state"]["facts"] = {"inpatient": "yes", "cause": "illness", "surgery": "no"}
    case["dialogue_state"]["pending_question"] = {"field": field, "kind": "fact", "asked_at_revision": 2}
    result = answer(case, "不知道，稍後確認")
    assert field in result["dialogue_state"]["deferred_fields"]
    assert result["pending_question"]["kind"] == "proposal"
    assert result["proposed_case_updates"]["claim_type_id"] == "inpatient"


def test_short_answer_uses_pending_field_instead_of_other_restatement_anchors():
    case = item(cause="illness", receipt_type="daily", payment_method="other")
    case["dialogue_state"]["facts"] = {"inpatient": "yes"}
    case["dialogue_state"]["pending_question"] = {"field": "surgery", "kind": "fact", "asked_at_revision": 2}
    case["messages"] = [{"role": "assistant", "content": "已了解住院，請問這次有手術嗎？", "response": {"response_type": "clarification"}}]
    result = answer(case, "沒有", surgery=("no", "沒有"))
    assert result["dialogue_state"]["facts"]["inpatient"] == "yes"
    assert result["dialogue_state"]["facts"]["surgery"] == "no"


def test_rejecting_candidate_does_not_negate_admission_or_erase_known_facts():
    case = item()
    case["dialogue_state"]["facts"] = {"inpatient": "yes", "surgery": "yes"}
    case["dialogue_state"]["pending_question"] = {"field": "claim_type_id", "kind": "proposal", "asked_at_revision": 2}
    result = answer(case, "不是")
    assert result["dialogue_state"]["facts"]["inpatient"] == "yes"
    assert result["dialogue_state"]["facts"]["surgery"] == "yes"
    assert result["proposed_case_updates"] == {}
    assert result["pending_question"]["field"] == "correction"


def test_proposal_short_answer_cannot_be_misused_as_new_denied_fact():
    case = item()
    case["dialogue_state"]["pending_question"] = {"field": "claim_type_id", "kind": "proposal", "asked_at_revision": 2}
    with pytest.raises(AIError):
        answer(case, "不是", inpatient=("no", "不是"))


def test_workflow_workspace_correction_has_proposed_updates_without_mutation():
    case = item("inpatient", cause="illness", surgery="no", receipt_type="daily", payment_method="other")
    case["dialogue_state"]["facts"] = {"inpatient": "yes"}
    result = answer(case, "更正，有手術", surgery=("yes", "有手術"))
    assert result["response_type"] == "case_update_proposal"
    assert result["proposed_case_updates"]["conditions"]["surgery"] == "yes"
    assert result["proposed_case_updates"].get("claim_type_id", "inpatient") == "inpatient"
    validate_assistant_response(result, OfficialRetriever())


def test_detail_extraction_keeps_partial_dates_and_unverified_multiple_products():
    case = item()
    content = request_content(case, "媽媽10月3日住院，還沒出院，診斷是肺炎，商品代碼ABC和DEF")
    payload = generated(content, inpatient=("yes", "住院"))
    text = content["dialogue"][-1]
    payload["details"] = {field: {"value": value, "turn": text["turn"], "quote": quote} for field, value, quote in [
        ("insured_relation", "parent", "媽媽"), ("diagnosis_name", "肺炎", "診斷是肺炎"),
        ("visit_dates.admission", "10月3日", "10月3日住院"), ("visit_dates.discharge_pending", True, "還沒出院"),
        ("policy_products", [{"code": "ABC", "version": None, "verification_status": "unverified"}, {"code": "DEF", "version": None, "verification_status": "unverified"}], "商品代碼ABC和DEF")
    ]}
    result = validate_semantics(payload, content, OfficialRetriever(), invalid)
    details = result["dialogue_state"]["details"]
    assert details["visit_dates"]["admission"] == "10月3日"
    assert details["visit_dates"]["discharge_pending"] is True
    assert details["insured_relation"] == "parent"
    assert {product["code"] for product in details["policy_products"]} == {"ABC", "DEF"}


@pytest.mark.parametrize("value,quote", [("2026-10-03", "10月3日住院"), ("肺癌", "診斷是肺炎"), ("王小明", "媽媽")])
def test_model_details_cannot_invent_year_diagnosis_or_person_name(value, quote):
    content = request_content(item(), "媽媽10月3日住院，診斷是肺炎")
    payload = generated(content, inpatient=("yes", "住院"))
    field = "visit_dates.admission" if value.startswith("2026") else "diagnosis_name" if value == "肺癌" else "insured_relation"
    payload["details"] = {field: {"value": value, "turn": content["dialogue"][-1]["turn"], "quote": quote}}
    with pytest.raises(AIError):
        validate_semantics(payload, content, OfficialRetriever(), invalid)


def test_structured_fact_context_does_not_include_ocr_identifiers_or_document_bytes():
    case = item()
    case.update(id="never-send-id", documents=[{"ocr": "never-send-ocr"}], details={"diagnosis_name": "肺炎"})
    content = request_content(case, "有住院")
    assert content["workflow_version"] == 2
    assert "never-send" not in str(content)


def test_unrelated_weather_turn_preserves_pending_and_does_not_repeat_question():
    case = item()
    case["dialogue_state"]["facts"] = {"inpatient": "yes"}
    pending = {"field": "cause", "kind": "fact", "asked_at_revision": 2}
    case["dialogue_state"]["pending_question"] = pending
    result = answer(case, "明天台北會下雨嗎？")
    assert result["response_type"] == "uncertain"
    assert result["pending_question"] == pending
    assert "疾病還是意外" not in result["message"]
    assert result["proposed_case_updates"] == {}


def test_structured_unknown_correction_does_not_retain_a_superseded_positive_fact():
    case = item()
    case["dialogue_state"]["facts"] = {"inpatient": "yes", "surgery": "yes"}
    result = answer(case, "更正，手術還不確定")
    assert result["dialogue_state"]["facts"]["surgery"] == "unknown"
    assert result["dialogue_state"]["facts"]["inpatient"] == "yes"


def test_short_answer_to_ambiguous_cause_does_not_choose_accident_or_illness():
    case = item()
    case["dialogue_state"]["facts"] = {"inpatient": "yes"}
    case["dialogue_state"]["pending_question"] = {"field": "cause", "kind": "fact", "asked_at_revision": 2}
    result = answer(case, "是")
    assert result["dialogue_state"]["facts"]["cause"] == "unknown"
    assert result["pending_question"]["field"] == "cause"


def test_pending_care_setting_short_answer_is_bound_to_inpatient_only():
    case = item()
    case["dialogue_state"]["pending_question"] = {"field": "care_setting", "kind": "fact", "asked_at_revision": 2}
    result = answer(case, "沒有", inpatient=("no", "沒有"))
    assert result["dialogue_state"]["facts"]["inpatient"] == "no"
    assert result["dialogue_state"]["facts"]["outpatient"] == "unknown"
    assert result["pending_question"]["field"] == "outpatient"


def test_receipt_type_model_fact_cannot_invert_a_negated_payment_choice():
    case = item()
    content = request_content(case, "我不要匯款")
    payload = generated(content)
    payload["condition_facts"] = {"payment_method": {"value": "remittance", "turn": content["dialogue"][-1]["turn"], "quote": "匯款"}}
    with pytest.raises(AIError):
        validate_semantics(payload, content, OfficialRetriever(), invalid)


@pytest.mark.parametrize("field,old_quote,new_text,value", [
    ("payment_method", "我要匯款", "更正，不要匯款", "remittance"),
    ("diagnosis_name", "診斷是肺炎", "更正，診斷是流感", "肺炎"),
    ("visit_dates.admission", "10月3日住院", "更正，10月5日住院", "10月3日"),
])
def test_supplementary_fields_reject_quotes_superseded_by_newer_user_turn(field, old_quote, new_text, value):
    case = item()
    case["messages"] = [{"role": "user", "content": old_quote}]
    content = request_content(case, new_text)
    payload = generated(content)
    group = "condition_facts" if field == "payment_method" else "details"
    payload[group] = {field: {"value": value, "turn": 1, "quote": old_quote}}
    with pytest.raises(AIError):
        validate_semantics(payload, content, OfficialRetriever(), invalid)


@pytest.mark.parametrize("field,value", [("visit_dates", {"admission": "姓名：王小明 0912345678"}),
                                         ("policy_products", [{"code": "ABC", "version": "姓名：王小明 0912345678", "verification_status": "unverified"}]),
                                         ("deferred_fields", ["姓名：王小明 0912345678"])])
def test_identifying_text_cannot_be_hidden_in_structured_detail_fields(field, value):
    from backend.app.models import CaseDetails
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        CaseDetails.model_validate({field: value})


def test_cause_contrast_preserves_affirmed_illness_and_rejects_negated_accident():
    case = item()
    result = answer(case, "媽媽住院、疾病非意外", inpatient=("yes", "住院"), cause=("illness", "疾病非意外"))
    assert result["dialogue_state"]["facts"]["cause"] == "illness"
    with pytest.raises(AIError):
        answer(case, "媽媽住院、疾病非意外", inpatient=("yes", "住院"), cause=("accident", "疾病非意外"))


@pytest.mark.parametrize("field,value,text", [("diagnosis_name", "肺炎", "診斷不是肺炎"),
                                             ("surgery_name", "肺切除", "我沒有接受肺切除手術"),
                                             ("visit_dates.admission", "10月3日", "我10月3日出院")])
def test_detail_names_and_dates_require_affirmed_correct_event(field, value, text):
    content = request_content(item(), text)
    payload = generated(content)
    payload["details"] = {field: {"value": value, "turn": content["dialogue"][-1]["turn"], "quote": text}}
    with pytest.raises(AIError):
        validate_semantics(payload, content, OfficialRetriever(), invalid)


def test_workspace_explicit_unknown_is_a_reviewable_change_not_silent_erasure():
    case = item("inpatient", cause="illness", surgery="yes", payment_method="other")
    case["dialogue_state"]["facts"] = {"inpatient": "yes", "surgery": "yes"}
    result = answer(case, "更正，手術還不確定")
    assert result["response_type"] == "case_update_proposal"
    assert result["proposed_case_updates"]["conditions"]["surgery"] == "unknown"
    assert case["conditions"]["surgery"] == "yes"


def test_prior_quote_cannot_override_a_newer_structured_fact_even_after_history_clipping():
    case = item("outpatient", cause="illness", surgery="no", payment_method="other")
    case["dialogue_state"]["facts"] = {"inpatient": "no", "outpatient": "yes"}
    case["messages"] = [{"role": "user", "content": "有住院"}]
    with pytest.raises(AIError):
        answer(case, "繼續", inpatient=("yes", "有住院"))


def test_new_case_details_are_not_reset_by_empty_dialogue_draft():
    case = item("inpatient")
    case["details"] = {"insured_relation": "parent", "diagnosis_name": "肺炎", "visit_dates": {"admission": "10月3日"}}
    result = answer(case, "繼續")
    assert result["proposed_case_updates"] == {}
    assert result["dialogue_state"]["details"]["diagnosis_name"] == "肺炎"
    assert result["dialogue_state"]["details"]["visit_dates"]["admission"] == "10月3日"


def test_new_discharge_date_clears_pending_without_inventing_year():
    case = item("inpatient")
    case["details"] = {"visit_dates": {"discharge_pending": True}}
    case["dialogue_state"]["details"] = case["details"]
    content = request_content(case, "更正，10月6日出院")
    payload = generated(content)
    payload["details"] = {"visit_dates.discharge": {"value": "10月6日", "turn": 1, "quote": "10月6日出院"}}
    result = validate_semantics(payload, content, OfficialRetriever(), invalid)
    assert result["proposed_case_updates"]["details"]["visit_dates"]["discharge"] == "10月6日"
    assert result["proposed_case_updates"]["details"]["visit_dates"]["discharge_pending"] is False


def test_additional_product_preserves_prior_unverified_product():
    case = item()
    original = {"code": "ABC", "version": None, "verification_status": "unverified"}
    case["dialogue_state"]["details"] = {"policy_products": [original]}
    content = request_content(case, "我還有商品DEF")
    payload = generated(content)
    payload["details"] = {"policy_products": {"value": [{"code": "DEF", "version": None, "verification_status": "unverified"}], "turn": 1, "quote": "商品DEF"}}
    result = validate_semantics(payload, content, OfficialRetriever(), invalid)
    assert result["dialogue_state"]["details"]["policy_products"][0] == original
    assert len(result["dialogue_state"]["details"]["policy_products"]) == 2


@pytest.mark.parametrize("field,value,text,quote", [
    ("surgery_name", "肺切除", "我沒有接受肺切除手術", "肺切除手術"),
    ("diagnosis_name", "肺炎", "並不是診斷是肺炎", "診斷是肺炎"),
    ("visit_dates.admission", "10月6日", "10月3日住院，10月6日出院", "10月3日住院，10月6日出院"),
    ("visit_dates.discharge", "10月3日", "10月3日住院，10月6日出院", "10月3日住院，10月6日出院"),
])
def test_detail_evidence_cannot_crop_negation_or_relabel_a_different_event_date(field, value, text, quote):
    content = request_content(item(), text)
    payload = generated(content)
    payload["details"] = {field: {"value": value, "turn": 1, "quote": quote}}
    with pytest.raises(AIError):
        validate_semantics(payload, content, OfficialRetriever(), invalid)


def test_denied_workspace_admission_asks_one_remaining_care_question():
    case = item("inpatient", cause="illness", surgery="no", payment_method="other")
    result = answer(case, "更正，沒有住院", inpatient=("no", "沒有住院"))
    assert result["pending_question"]["field"] == "outpatient"
    assert result["proposed_case_updates"] == {}
    assert case["claim_type_id"] == "inpatient"


def test_affirmed_surgery_detail_cannot_coexist_with_denied_surgery_fact():
    case = item("inpatient", surgery="no")
    content = request_content(case, "更正，我有肺切除手術")
    payload = generated(content)
    payload["details"] = {"surgery_name": {"value": "肺切除", "turn": 1, "quote": "我有肺切除手術"}}
    with pytest.raises(AIError):
        validate_semantics(payload, content, OfficialRetriever(), invalid)


@pytest.mark.parametrize("field,value", [("visit_dates", {"admission": "0912345678"}),
                                         ("policy_products", [{"code": "ABC", "version": "sk-or-v1-1234567890", "verification_status": "unverified"}])])
def test_date_and_version_character_whitelists_do_not_allow_phone_or_secret(field, value):
    from backend.app.models import CaseDetails
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        CaseDetails.model_validate({field: value})


@pytest.mark.parametrize("field,old,value", [("diagnosis_name", "診斷是肺炎", "肺炎"), ("visit_dates.admission", "10月3日住院", "10月3日"), ("payment_method", "我要匯款", "remittance")])
def test_manual_structured_update_cannot_be_rolled_back_by_old_quote(field, old, value):
    case = item("inpatient", surgery="no", cause="illness", payment_method="other")
    case["dialogue_state"].update(conditions=case["conditions"], details={"diagnosis_name": "流感", "visit_dates": {"admission": "10月5日"}})
    case["messages"] = [{"role": "user", "content": old}]
    content = request_content(case, "繼續")
    payload = generated(content)
    group = "condition_facts" if field == "payment_method" else "details"
    payload[group] = {field: {"value": value, "turn": 1, "quote": old}}
    with pytest.raises(AIError):
        validate_semantics(payload, content, OfficialRetriever(), invalid)


def test_local_workflow_does_not_invent_a_confirmed_critical_diagnosis():
    import asyncio
    from backend.app.ai.providers import GroundedRulesProvider
    case = item()
    result = asyncio.run(GroundedRulesProvider().respond(case, "癌症的文件怎麼準備？"))
    assert result["dialogue_state"]["facts"]["critical_diagnosis"] == "unknown"
    assert result["proposed_case_updates"] == {}
    assert result["provider"] == "grounded_rules"
