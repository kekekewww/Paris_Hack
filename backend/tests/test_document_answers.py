"""Specific official-document answers; only synthetic offline model envelopes.

These tests catch returning a related paragraph instead of answering the query,
or treating an official URL as proof of an unsupported sentence.
"""
import asyncio
import copy
import json

import httpx
import pytest

from backend.app.ai.openai_compatible import OpenAICompatibleProvider, OpenAICompatibleSettings
from backend.app.ai.retrieval import OfficialRetriever


CASE = {"id": "synthetic-document-answer", "claim_type_id": "inpatient",
        "conditions": {"cause": "unknown", "surgery": "unknown"}, "documents": [], "messages": []}


def answer(question, ids, *, claim_type="inpatient", retriever=None, document_id=None):
    def transport(request):
        content = json.loads(json.loads(request.content)["messages"][1]["content"])
        assert set(content) == {"query", "evidence"}
        assert set(ids) <= {item["id"] for item in content["evidence"]}
        envelope = {"model": "synthetic/concrete:free", "usage": {
            "cost": 0, "prompt_tokens": 240, "completion_tokens": 140, "total_tokens": 380},
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"evidence_ids": ids})}}]}
        return httpx.Response(200, json=envelope)

    provider = OpenAICompatibleProvider(OpenAICompatibleSettings(
        api_key="offline-document-answer-key", model="openrouter/free", base_url="https://openrouter.ai/api/v1"),
        retriever, transport=httpx.MockTransport(transport))
    case = {**copy.deepcopy(CASE), "claim_type_id": claim_type}
    before = copy.deepcopy(case)
    result = asyncio.run(provider.respond(case, question, document_id))
    assert case == before and result["proposed_case_updates"] == {}
    return result


@pytest.mark.parametrize("question,expected", [
    ("診斷書已記載手術部位與方式，手術證明還需要另附嗎？", "可免另附手術證明"),
    ("本次沒有手術，手術證明還需要另附嗎？", "可免另附手術證明"),
    ("有手術但診斷書未記載部位與方式，手術證明需要嗎？", "需另附手術證明"),
])
def test_surgery_answer_leads_with_the_query_condition_not_a_whole_paragraph(question, expected):
    result = answer(question, ["surgery-condition"])
    first = result["message"].splitlines()[0]
    assert first.startswith("直接回答：") and expected in first
    assert "適用條件：" in result["message"]
    assert "診斷書" in result["message"] and "部位" in result["message"] and "方式" in result["message"]
    assert "保單" in result["message"] and "核准" in result["message"]
    assert {(item["source_id"], item["page_number"]) for item in result["source_references"]} == {
        ("cardif-inpatient-guide", 3)}


def test_application_signature_answer_identifies_the_field_and_preserves_ocr_limit():
    result = answer("申請書簽名與日期要填寫嗎？", ["application-precheck"])
    first = result["message"].splitlines()[0]
    assert first.startswith("直接回答：") and "簽名" in first and "日期" in first
    assert "姓名、保單號碼" not in first
    assert "法律真實性" in result["message"]
    assert "適用條件：" in result["message"] and "來源 [1]" in result["message"]
    assert {item["source_id"] for item in result["source_references"]} == {"cardif-application"}


def test_ordinary_diagnosis_copy_answer_keeps_the_hospital_stamp_exception():
    result = answer("診斷書只有普通影印本可以嗎？", ["diagnosis-format"])
    first = result["message"].splitlines()[0]
    assert first.startswith("直接回答：") and "普通影印本不符合" in first
    assert "正本" in result["message"] and "紅色印章" in result["message"] and "副本" in result["message"]


def test_related_but_insufficient_official_evidence_is_not_used_as_the_answer():
    result = answer("手術證明是否需要另附？", ["discrepancy:surgery-detail"])
    assert result["response_type"] == "uncertain"
    assert "證據不足" in result["message"]
    assert result["source_references"] == []
    assert "官網簡表較粗" not in result["message"]


def test_template_cannot_survive_a_changed_canonical_qualifier_just_because_the_id_and_url_match():
    registry = OfficialRetriever().registry
    item = next(item for item in registry["knowledge"] if item["knowledge_id"] == "surgery-condition")
    item["text"] = "只要有手術就一定要另附手術證明。"
    result = answer("手術證明是否需要另附？", ["surgery-condition"], retriever=OfficialRetriever(registry))
    assert result["response_type"] == "uncertain"
    assert "證據不足" in result["message"]
    assert result["source_references"] == []
    assert "可免" not in result["message"] and "一定要" not in result["message"]


def test_partial_multi_question_answer_names_the_unanswered_part():
    result = answer("診斷書的普通影印本可以嗎？申請書的簽名與日期要填寫嗎？", ["diagnosis-format"])
    assert "普通影印本不符合" in result["message"].splitlines()[0]
    assert "申請書欄位：本次證據不足" in result["message"]
    assert "申請人簽名與日期" not in result["message"]
    assert {item["source_id"] for item in result["source_references"]} == {"cardif-inpatient-guide"}


@pytest.mark.parametrize("question", [
    "我沒有手術證明，是否需要另附手術證明？",
    "沒有手術紀錄，需要另附手術證明嗎？",
    "不是沒有手術，需要另附手術證明嗎？",
    "不是沒手術，需要另附手術證明嗎？",
    "並非沒有手術，需要另附手術證明嗎？",
    "我不知道有沒有手術，需要另附手術證明嗎？",
    "我沒有手術費明細，需要另附手術證明嗎？",
    "只有手術部位沒有方式，手術證明需要嗎？",
    "診斷書並未完整記載手術部位與方式，手術證明需要嗎？",
])
def test_missing_documents_and_incomplete_details_cannot_turn_into_no_surgery_exemption(question):
    result = answer(question, ["surgery-condition"])
    assert "需另附手術證明" in result["message"].splitlines()[0]
    assert "可免另附手術證明" not in result["message"].splitlines()[0]


@pytest.mark.parametrize("question", ["申請書的聯絡方式要填嗎？", "申請書的稅務聲明選項要填嗎？"])
def test_specific_application_field_answer_avoids_repeating_the_entire_form(question):
    result = answer(question, ["application-precheck"])
    first = result["message"].splitlines()[0]
    assert ("聯絡方式" if "聯絡" in question else "稅務聲明選項") in first
    assert "姓名、保單號碼" not in first


@pytest.mark.parametrize("mutation", ["source", "page"])
def test_template_rejects_a_different_official_source_or_page(mutation):
    registry = OfficialRetriever().registry
    item = next(item for item in registry["knowledge"] if item["knowledge_id"] == "surgery-condition")
    if mutation == "source":
        item.update(source_id="cardif-general-documents", page_number=1)
    else:
        item["page_number"] = 2
    result = answer("手術證明是否需要另附？", ["surgery-condition"], retriever=OfficialRetriever(registry))
    assert result["response_type"] == "uncertain" and result["source_references"] == []


@pytest.mark.parametrize("question", [
    "申請書的簽名要填嗎？用英文簽名可以嗎？",
    "申請書簽名日期怎麼填，電子簽章法律效力相同嗎？",
    "手術後需要冰敷幾天？",
    "診斷書還需附 PCR 檢驗報告嗎？",
    "診斷書還需附 HIV 檢驗報告嗎？",
    "診斷書還需附 ＰＣＲ 檢驗報告嗎？",
])
def test_unsupported_document_subquestions_do_not_become_semantic_intake(question):
    def forbidden_transport(request):
        pytest.fail("Unsupported official-document questions must not be replaced by semantic intake")

    provider = OpenAICompatibleProvider(OpenAICompatibleSettings(
        api_key="offline-document-answer-key", model="openrouter/free", base_url="https://openrouter.ai/api/v1"),
        transport=httpx.MockTransport(forbidden_transport))
    result = asyncio.run(provider.respond(copy.deepcopy(CASE), question))
    assert result["response_type"] == "uncertain" and result["source_references"] == []


@pytest.mark.parametrize("code", ["IHI_C_1131001", "IHO_1131001", "UNKNOWN_999999"])
def test_unverified_product_version_question_stays_explicitly_unknown_without_model_transport(code):
    def forbidden_transport(request):
        pytest.fail("An unverified product code cannot trigger unrelated medical intake")

    provider = OpenAICompatibleProvider(OpenAICompatibleSettings(
        api_key="offline-document-answer-key", model="openrouter/free", base_url="https://openrouter.ai/api/v1"),
        transport=httpx.MockTransport(forbidden_transport))
    result = asyncio.run(provider.respond(copy.deepcopy(CASE), f"商品代碼 {code} 的條款內容是什麼？"))
    assert result["response_type"] == "uncertain"
    assert "沒有" in result["message"] and "官方資料" in result["message"]
    assert result["proposed_case_updates"] == {} and result["suggested_claim_types"] == []


@pytest.mark.parametrize("question,ids", [
    ("診斷書普通影印本可以嗎？可以傳真嗎？", ["diagnosis-format"]),
    ("診斷書可以用影本嗎，多久內要申請？", ["diagnosis-format"]),
    ("申請書簽名要填嗎？簽名可以用蓋章嗎？", ["application-precheck"]),
    ("申請書簽名一定要用藍筆嗎？", ["application-precheck"]),
    ("申請書的稅務聲明欄位要勾哪個？", ["application-precheck"]),
    ("申請書的稅務聲明要怎麼勾選？", ["application-precheck"]),
    ("診斷書影本可用嗎，幾個月內要申請？", ["diagnosis-format"]),
    ("手術證明必須由醫師簽章嗎？另外診斷書普通影印本可以嗎？", ["surgery-condition", "diagnosis-format"]),
])
def test_unverified_specific_subquestion_is_not_hidden_by_a_supported_document_facet(question, ids):
    result = answer(question, ids)
    assert result["response_type"] == "uncertain"
    assert "證據不足" in result["message"] and result["source_references"] == []
    assert "請檢查" not in result["message"]


def test_first_critical_claim_retains_the_positive_pathology_requirement():
    result = answer("首次癌症申請需要病理報告嗎？", ["document:critical_illness:pathology"], claim_type="critical_illness")
    first = result["message"].splitlines()[0]
    assert "首次癌症或重大疾病申請需附病理或相關檢驗報告" in first
    assert "非首次" in result["message"] and "病況" in result["message"] and "保單" in result["message"]


def test_nonfirst_critical_claim_leads_with_its_condition_without_erasing_first_claim_rule():
    result = answer("這不是首次癌症申請，需要病理報告嗎？", ["document:critical_illness:pathology"], claim_type="critical_illness")
    first = result["message"].splitlines()[0]
    assert "非首次申請" in first and "病況" in first and "保單" in first
    assert "首次癌症或重大疾病申請需附病理或相關檢驗報告" in result["message"]


def test_general_critical_overview_does_not_prove_the_first_claim_requirement():
    result = answer("首次癌症申請需要病理報告嗎？", ["critical-uncertainty"], claim_type="critical_illness")
    assert result["response_type"] == "uncertain" and "證據不足" in result["message"]
    assert result["source_references"] == []


def test_mixed_medical_description_and_two_product_codes_still_reaches_semantic_extraction():
    message = "媽媽10/14住院、10/16膽囊切除手術、疾病非意外、還沒出院、商品IHI_C_1131001與IHO_1131001"
    observed = []

    def transport(request):
        content = json.loads(json.loads(request.content)["messages"][1]["content"])
        observed.append(content)
        assert content["workflow_version"] == 2
        current = content["dialogue"][-1]
        assert current["content"] == message
        facts = {field: {"value": "unknown", "turn": None, "quote": ""} for field in
                 ("cause", "inpatient", "outpatient", "emergency", "critical_diagnosis", "surgery")}
        for field, value, quote in (("cause", "illness", "疾病非意外"), ("inpatient", "yes", "10/14住院"),
                                    ("surgery", "yes", "10/16膽囊切除手術")):
            facts[field] = {"value": value, "turn": current["turn"], "quote": quote}
        generated = {"facts": facts, "question": "confirm_claim", "message": "請確認本次就醫資訊。",
                     "details": {field: {"value": value, "turn": current["turn"], "quote": quote}
                     for field, value, quote in (("insured_relation", "parent", "媽媽"),
                         ("visit_dates.admission", "10/14", "10/14住院"),
                         ("visit_dates.discharge_pending", True, "還沒出院"),
                         ("surgery_name", "膽囊切除手術", "10/16膽囊切除手術"),
                         ("surgery_date", "10/16", "10/16膽囊切除手術"),
                         ("policy_products", [{"code": "IHI_C_1131001", "version": None, "verification_status": "unverified"},
                                              {"code": "IHO_1131001", "version": None, "verification_status": "unverified"}],
                          "商品IHI_C_1131001與IHO_1131001"))}}
        return httpx.Response(200, json={"model": "synthetic/concrete:free", "usage": {
            "cost": 0, "prompt_tokens": 240, "completion_tokens": 140, "total_tokens": 380},
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(generated)}}]})

    case = {**copy.deepcopy(CASE), "claim_type_id": None, "details": {}, "revision": 0,
            "dialogue_state": {"facts": {}, "conditions": {}, "details": {}, "deferred_fields": [], "pending_question": None}}
    before = copy.deepcopy(case)
    provider = OpenAICompatibleProvider(OpenAICompatibleSettings(
        api_key="offline-document-answer-key", model="openrouter/free", base_url="https://openrouter.ai/api/v1"),
        transport=httpx.MockTransport(transport))
    result = asyncio.run(provider.respond(case, message))
    assert len(observed) == 1 and case == before
    facts = result["dialogue_state"]["facts"]
    details = result["dialogue_state"]["details"]
    assert facts["cause"] == "illness" and facts["inpatient"] == "yes" and facts["surgery"] == "yes"
    assert details["insured_relation"] == "parent" and details["visit_dates"]["admission"] == "10/14"
    assert details["visit_dates"]["discharge_pending"] is True and not details["visit_dates"].get("discharge")
    assert details["surgery_name"] == "膽囊切除手術" and details["surgery_date"] == "10/16"
    assert {item["code"] for item in details["policy_products"]} == {"IHI_C_1131001", "IHO_1131001"}
    assert all(item["verification_status"] == "unverified" and item["version"] is None for item in details["policy_products"])
    assert result["proposed_case_updates"] == {} and result["pending_question"]["field"] == "payment_method"
