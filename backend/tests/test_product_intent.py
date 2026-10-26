"""Keep complete mixed narratives while refusing unsupported product specifics."""
import asyncio
import json

import httpx
import pytest

from backend.app.ai.openai_compatible import OpenAICompatibleProvider, OpenAICompatibleSettings
from backend.app.ai.providers import is_product_question


@pytest.mark.parametrize("message,expected", [
    ("我發生車禍，商品代碼IHI_C_1131001", False),
    ("媽媽10/14住院、10/16膽囊切除手術、疾病非意外、還沒出院、商品IHI_C_1131001與IHO_1131001", False),
    ("昨日車禍，商品代碼IHI_C_1131001", False),
    ("有住院三天，商品代碼IHI_C_1131001", False),
    ("商品 IHI_C_1131001 的手術證明有什麼要求？", True),
    ("商品代碼IHI_C_1131001的手術條款是什麼？", True),
    ("商品代碼IHI_C_1131001的住院條款是什麼？", True),
    ("我想詢問商品IHI_C_1131001的手術證明要求", True),
])
def test_product_intent_requires_an_actual_event_assertion(message, expected):
    assert is_product_question(message) is expected


def settings():
    return OpenAICompatibleSettings(api_key="synthetic-offline-only", model="openrouter/free", base_url="https://openrouter.ai/api/v1")


def test_accident_and_product_code_original_sentence_reaches_semantic_extraction():
    message = "我發生車禍，商品代碼IHI_C_1131001"
    observed = []

    def transport(request):
        content = json.loads(json.loads(request.content)["messages"][1]["content"])
        observed.append(content)
        assert content["dialogue"][-1]["content"] == message
        turn = content["dialogue"][-1]["turn"]
        facts = {field: {"value": "unknown", "turn": None, "quote": ""} for field in ("cause", "inpatient", "outpatient", "emergency", "critical_diagnosis", "surgery")}
        facts["cause"] = {"value": "accident", "turn": turn, "quote": "發生車禍"}
        response = {"facts": facts, "question": "care_setting", "message": "請問本次有住院嗎？", "details": {
            "policy_products": {"value": [{"code": "IHI_C_1131001", "version": None, "verification_status": "unverified"}], "turn": turn, "quote": "商品代碼IHI_C_1131001"}}}
        return httpx.Response(200, json={"model": "synthetic/concrete:free", "usage": {"cost": 0, "prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200},
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(response, ensure_ascii=False)}}]})

    case = {"claim_type_id": None, "conditions": {}, "details": {}, "documents": [], "messages": [], "dialogue_state": {"facts": {}, "details": {}, "conditions": {}, "pending_question": None}, "revision": 0}
    result = asyncio.run(OpenAICompatibleProvider(settings(), transport=httpx.MockTransport(transport)).respond(case, message))
    assert len(observed) == 1 and result["provider"] == "openai_compatible"
    assert result["dialogue_state"]["facts"]["cause"] == "accident"
    assert result["pending_question"]["field"] == "care_setting"
    assert result["dialogue_state"]["details"]["policy_products"] == [{"code": "IHI_C_1131001", "version": None, "verification_status": "unverified"}]
    assert result["proposed_case_updates"] == {}


@pytest.mark.parametrize("message", ["商品 IHI_C_1131001 的手術證明有什麼要求？", "商品代碼IHI_C_1131001的手術條款是什麼？"])
def test_unknown_product_specific_questions_do_not_use_generic_surgery_evidence(message):
    def transport(request):
        pytest.fail("An unverified product question must not use medical intake or generic evidence")

    case = {"claim_type_id": "inpatient", "conditions": {}, "documents": [], "messages": []}
    result = asyncio.run(OpenAICompatibleProvider(settings(), transport=httpx.MockTransport(transport)).respond(case, message))
    assert result["response_type"] == "uncertain"
    assert "沒有可精確核對" in result["message"] and "待查證" in result["message"]
    assert result["source_references"] == [] and result["proposed_case_updates"] == {}
    assert "需另附手術證明" not in result["message"]
