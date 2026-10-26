"""Exact current-question options are actionable in the real HTTP rules mode."""
import asyncio
import copy
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.ai.providers import GroundedRulesProvider
from backend.app.ai.semantic_dialogue import _pending


def case(field, **known):
    conditions = {"cause": "accident", "surgery": "no", "payment_method": "other", **known}
    conditions[field] = "unknown"
    return {"claim_type_id": None, "conditions": conditions, "details": {}, "documents": [], "messages": [], "revision": 0,
            "dialogue_state": {"facts": {"inpatient": "yes"}, "conditions": conditions.copy(), "details": {}, "deferred_fields": [], "pending_question": _pending(field, 0)}}


@pytest.mark.parametrize("field,message,expected", [
    ("cause", "意外", "accident"), ("cause", "accident", "accident"), ("cause", "疾病", "illness"),
    ("payment_method", "直接匯款", "remittance"), ("payment_method", "其他方式", "other"),
    ("payment_method", "other", "other"), ("surgery", "沒有手術", "no"),
])
def test_exact_pending_option_label_or_value_advances_local_workflow(field, message, expected):
    item = case(field)
    before = copy.deepcopy(item)
    result = asyncio.run(GroundedRulesProvider().respond(item, message))
    assert item == before
    assert result["provider"] == "grounded_rules" and result["is_simulated"] is False
    assert result["response_type"] == "claim_suggestion"
    assert result["proposed_case_updates"]["conditions"][field] == expected
    assert result["pending_question"]["kind"] == "proposal"


@pytest.mark.parametrize("field,message", [("cause", "稍後確認"), ("cause", "unknown"),
                                          ("payment_method", "稍後確認"), ("payment_method", "unknown")])
def test_current_unknown_option_defers_once_and_advances(field, message):
    result = asyncio.run(GroundedRulesProvider().respond(case(field), message))
    assert field in result["dialogue_state"]["deferred_fields"]
    assert result["response_type"] == "claim_suggestion"
    assert result["proposed_case_updates"]["conditions"][field] == "unknown"


def test_the_exact_displayed_accident_label_is_bound_to_current_question():
    item = case("cause")
    item["dialogue_state"]["pending_question"]["options"][1]["label"] = "事故"
    result = asyncio.run(GroundedRulesProvider().respond(item, "事故"))
    assert result["proposed_case_updates"]["conditions"]["cause"] == "accident"


@pytest.mark.parametrize("message", ["請問其他方式有什麼？", "我的朋友說其他方式", "不是其他方式", "其他方式是什麼意思"])
def test_substring_or_negated_option_phrase_is_not_an_option_answer(message):
    result = asyncio.run(GroundedRulesProvider().respond(case("payment_method"), message))
    assert result["response_type"] == "clarification"
    assert result["pending_question"]["field"] == "payment_method"
    assert result["dialogue_state"]["conditions"]["payment_method"] == "unknown"


def test_real_http_payment_other_option_reaches_candidate_without_changing_case(tmp_path, monkeypatch):
    monkeypatch.setenv("CASE_DB_PATH", str(tmp_path / "pending-options.sqlite3"))
    monkeypatch.setenv("LLM_PROVIDER", "grounded_rules")
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "1000")
    from backend.app.main import create_app

    with TestClient(create_app()) as client:
        created = client.post("/api/v1/cases", json={"entry_path": "guided"})
        assert created.status_code == 201
        identifier = created.json()["id"]
        first = client.post(f"/api/v1/cases/{identifier}/messages", json={"message": "我因車禍住院三天，沒有手術，想準備文件。"})
        assert first.status_code == 200, first.text
        assert first.json()["response"]["pending_question"]["field"] == "payment_method"
        result = client.post(f"/api/v1/cases/{identifier}/messages", json={"message": "其他方式"})
        assert result.status_code == 200, result.text
        payload = result.json()
        assert payload["response"]["response_type"] == "claim_suggestion"
        assert payload["response"]["proposed_case_updates"]["conditions"]["payment_method"] == "other"
        assert payload["response"]["proposal"]["base_revision"] == payload["case"]["revision"]
        assert payload["case"]["claim_type_id"] is None
        assert payload["case"]["conditions"]["payment_method"] == "unknown"
        assert payload["case"]["documents"] == []


@pytest.mark.parametrize("field,message,value", [("cause", "accident", "accident"), ("cause", "事故", "accident"), ("payment_method", "其他方式", "other")])
def test_model_mode_still_calls_and_validates_model_before_consuming_an_exact_option(field, message, value):
    from backend.app.ai.openai_compatible import OpenAICompatibleProvider, OpenAICompatibleSettings

    item = case(field)
    if message == "事故":
        item["dialogue_state"]["pending_question"]["options"][1]["label"] = message
    observed = []

    def transport(request):
        content = json.loads(json.loads(request.content)["messages"][1]["content"])
        observed.append(content)
        current = content["dialogue"][-1]
        assert current["content"] == message
        facts = {name: {"value": "unknown", "turn": None, "quote": ""} for name in ("cause", "inpatient", "outpatient", "emergency", "critical_diagnosis", "surgery")}
        if field == "cause":
            facts["cause"] = {"value": value, "turn": current["turn"], "quote": message}
        result = {"facts": facts, "question": "confirm_claim", "message": "請確認本次就醫資訊。"}
        return httpx.Response(200, json={"model": "synthetic/concrete:free", "usage": {"cost": 0, "prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200},
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(result, ensure_ascii=False)}}]})

    config = OpenAICompatibleSettings(api_key="synthetic-offline-only", model="openrouter/free", base_url="https://openrouter.ai/api/v1")
    result = asyncio.run(OpenAICompatibleProvider(config, transport=httpx.MockTransport(transport)).respond(item, message))
    assert len(observed) == 1 and result["provider"] == "openai_compatible"
    assert result["proposed_case_updates"]["conditions"][field] == value
