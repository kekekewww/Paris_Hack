"""Offline semantic conversation tests; real-provider acceptance is separate."""
import asyncio
import copy
import json

import httpx
import pytest

from backend.app.ai import openai_compatible as adapter
from backend.app.ai.providers import AIError


FIELDS = ("cause", "inpatient", "outpatient", "emergency", "critical_diagnosis", "surgery")


@pytest.fixture(autouse=True)
def reset_verification():
    adapter.verification_snapshot(None)
    yield
    adapter.verification_snapshot(None)


def case(claim=None, *history):
    return {"id": "never-send-case-id", "claim_type_id": claim, "conditions": {"cause": "unknown", "surgery": "unknown"},
            "documents": [{"id": "application", "ocr": "never-send-ocr"}],
            "messages": [{"role": "user", "content": text} for text in history]}


def settings():
    return adapter.OpenAICompatibleSettings(api_key="offline-only", model="openrouter/free", base_url="https://openrouter.ai/api/v1")


def completion(content):
    return {"model": "synthetic/concrete:free", "usage": {"cost": 0, "prompt_tokens": 300, "completion_tokens": 200, "total_tokens": 500},
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(content, ensure_ascii=False)}}]}


def semantic(request, question="describe_event", message="您好，請簡單描述本次發生的情況。", **known):
    dialogue = json.loads(json.loads(request.content)["messages"][1]["content"])["dialogue"]
    facts = {key: {"value": "unknown", "turn": None, "quote": ""} for key in FIELDS}
    for field, (value, quote) in known.items():
        turn = next(item for item in reversed(dialogue) if item["role"] == "user" and quote in item["content"])
        facts[field] = {"value": value, "turn": turn["turn"], "quote": quote}
    return {"facts": facts, "question": question, "message": message}


def run(item, message, handler):
    before = copy.deepcopy(item)
    provider = adapter.OpenAICompatibleProvider(settings(), transport=httpx.MockTransport(handler))
    answer = asyncio.run(provider.respond(item, message))
    assert item == before
    return answer


@pytest.mark.parametrize("current,reply", [
    ("可能是重大疾病，但我還不確定", "您提到可能是重大疾病，請問本次是否已就醫及有沒有住院？"),
    ("醫師說疑似癌症，尚未確診", "了解目前疑似癌症且尚未確診，請問本次是否已就醫及有沒有住院？"),
])
def test_supported_uncertain_critical_restatement_keeps_facts_unknown(current, reply):
    def handler(request):
        return httpx.Response(200, json=completion(semantic(request, "care_setting", reply)))

    answer = run(case(), current, handler)
    assert answer["message"] == reply and answer["missing_information"] == ["care_setting"]
    assert answer["response_type"] == "clarification"
    assert answer["suggested_claim_types"] == [] and answer["proposed_case_updates"] == {}


def test_uncertain_critical_restatement_does_not_override_supported_emergency_visit():
    def handler(request):
        return httpx.Response(200, json=completion(semantic(request, "confirm_claim",
            "您提到可能是重大疾病，請確認是否先查看門診文件資訊？", emergency=("yes", "有去急診"))))

    answer = run(case(), "有去急診，可能是重大疾病，但還不確定", handler)
    assert [entry["id"] for entry in answer["suggested_claim_types"]] == ["outpatient"]
    assert answer["proposed_case_updates"]["claim_type_id"] == "outpatient"
    assert answer["source_references"][0]["source_id"] == "cardif-claims"


def test_uncertain_critical_restatement_keeps_explicit_no_admission_question_gate():
    def handler(request):
        return httpx.Response(200, json=completion(semantic(request, "outpatient_or_emergency",
            "您提到可能是重大疾病，請問本次有去門診或急診嗎？", inpatient=("no", "沒有住院"))))

    answer = run(case(None, "沒有住院"), "可能是重大疾病，但我還不確定", handler)
    assert answer["missing_information"] == ["outpatient_or_emergency"]
    assert answer["suggested_claim_types"] == [] and answer["proposed_case_updates"] == {}


@pytest.mark.parametrize("diagnosis,value,question,reply", [
    ("醫師已確診重大疾病", "yes", "confirm_claim", "請確認本次已確診重大疾病資訊。"),
    ("沒有重大疾病", "no", "care_setting", "請問本次是否已就醫及有沒有住院？"),
])
def test_explicit_critical_facts_keep_their_existing_provenance_rules(diagnosis, value, question, reply):
    def handler(request):
        return httpx.Response(200, json=completion(semantic(request, question, reply, critical_diagnosis=(value, diagnosis))))

    answer = run(case(), diagnosis, handler)
    if value == "yes":
        assert [entry["id"] for entry in answer["suggested_claim_types"]] == ["critical_illness"]
        assert answer["source_references"][0]["source_id"] == "cardif-claims"
    else:
        assert answer["proposed_case_updates"] == {} and answer["suggested_claim_types"] == []


@pytest.mark.parametrize("current,reply", [
    ("可能是重大疾病，但我還不確定", "您已確診重大疾病，請問本次是否已就醫？"),
    ("可能是重大疾病，但我還不確定", "確定不是重大疾病，請問本次是否已就醫？"),
    ("可能是重大疾病，但我還不確定", "目前尚未確診重大疾病，請問本次是否已就醫？"),
    ("可能是重大疾病，但我還不確定", "您提到可能是癌症，請問本次是否已就醫？"),
    ("可能是重大疾病，但我還不確定", "可能需要住院，但您已確診重大疾病。請問本次是否已就醫？"),
    ("可能是重大疾病，但我還不確定", "您提到疑似重大疾病，確診癌症。請問本次是否已就醫？"),
    ("可能是重大疾病，但我還不確定", "您提到疑似重大疾病且已確診重大疾病，請問本次是否已就醫？"),
    ("可能是重大疾病，但我還不確定", "可能需住院您已確診重大疾病，請問本次是否已就醫？"),
    ("可能是重大疾病，但我還不確定", "可能需住院罹患重大疾病，請問本次是否已就醫？"),
    ("疑似癌症，但重大疾病尚未確診", "目前疑似癌症且尚未確診，請問本次是否已就醫？"),
    ("疑似重大疾病，尚未確診", "您提到疑似重大疾病。您有肺癌。請問本次是否已就醫及有沒有住院？"),
    ("疑似重大疾病，尚未確診", "您提到疑似重大疾病。肺癌尚未確診。請問本次是否已就醫及有沒有住院？"),
    ("沒有重大疾病", "您可能有重大疾病，請問本次是否已就醫？"),
    ("你好", "您可能有重大疾病，請問本次是否已就醫？"),
])
def test_uncertainty_cannot_authorize_diagnosis_denial_or_a_new_critical_topic(current, reply):
    def handler(request):
        return httpx.Response(200, json=completion(semantic(request, "care_setting", reply)))

    with pytest.raises(AIError) as caught:
        run(case(), current, handler)
    assert caught.value.code == "INVALID_LLM_RESPONSE" and caught.value.status == 503


@pytest.mark.parametrize("message", ["你好", "我出車禍了", "沒有住院"])
def test_every_ordinary_intake_turn_reaches_the_model_and_is_labelled_real_provider(message):
    observed = []

    def handler(request):
        observed.append(request)
        payload = semantic(request)
        if message == "我出車禍了":
            payload = semantic(request, "care_setting", "了解，請問本次是否已就醫？", cause=("accident", "出車禍"))
        elif message == "沒有住院":
            payload = semantic(request, "outpatient_or_emergency", "已了解沒有住院，請問曾看門診或去急診嗎？",
                               cause=("accident", "出車禍"), inpatient=("no", "沒有住院"))
        return httpx.Response(200, json=completion(payload))

    item = case(None, "我出車禍了") if message == "沒有住院" else case()
    answer = run(item, message, handler)
    assert len(observed) == 1
    assert answer["provider"] == "openai_compatible" and answer["is_simulated"] is False
    assert answer["response_type"] == "clarification"
    assert answer["proposed_case_updates"] == {}


@pytest.mark.parametrize("question,allowed", [("care_setting", True), ("outpatient_or_emergency", False)])
def test_accident_after_a_greeting_cannot_skip_unknown_admission(question, allowed):
    item = case(None, "你好")
    item["messages"].append({"role": "assistant", "content": "您好，請簡單描述這次發生的情況。", "response": {"response_type": "clarification"}})

    def handler(request):
        message = "了解車禍情況，請問本次是否已就醫，以及有沒有住院？" if allowed else "了解，請問本次有去門診或急診嗎？"
        payload = semantic(request, question, message, cause=("accident", "出車禍"))
        return httpx.Response(200, json=completion(payload))

    if allowed:
        answer = run(item, "我出車禍了", handler)
        assert answer["response_type"] == "clarification"
        assert answer["missing_information"] == ["care_setting"]
        assert answer["suggested_claim_types"] == [] and answer["proposed_case_updates"] == {}
    else:
        with pytest.raises(AIError) as caught:
            run(item, "我出車禍了", handler)
        assert caught.value.code == "INVALID_LLM_RESPONSE" and caught.value.status == 503


def test_model_semantics_can_recognize_a_visit_and_only_propose_a_registry_claim():
    def handler(request):
        return httpx.Response(200, json=completion(semantic(request, "confirm_claim", "了解，本次有到診所看診，請確認是否先查看門診文件。",
            cause=("accident", "出車禍"), inpatient=("no", "沒有住院"), outpatient=("yes", "到診所看診"))))

    answer = run(case(None, "我出車禍了", "沒有住院"), "我昨天到診所看診", handler)
    assert answer["response_type"] == "claim_suggestion"
    assert [claim["id"] for claim in answer["suggested_claim_types"]] == ["outpatient"]
    assert answer["proposed_case_updates"]["conditions"]["cause"] == "accident"
    assert answer["source_references"] and answer["requires_human_review"] is True


@pytest.mark.parametrize("current,care_field,care_quote,prior_no_admission", [
    ("只有急診，當天回家，沒有手術", "emergency", "只有急診", True),
    ("只有門診，沒有手術", "outpatient", "只有門診", False),
])
def test_exclusive_visit_evidence_leaves_other_care_facts_independent(current, care_field, care_quote, prior_no_admission):
    item = case(None, "你好", "我出車禍了", *( ["沒有住院"] if prior_no_admission else [] ))
    item["messages"].append({"role": "assistant", "content": "請問本次有到門診或急診嗎？", "response": {"response_type": "clarification"}})

    def handler(request):
        known = {"cause": ("accident", "出車禍"), care_field: ("yes", care_quote), "surgery": ("no", "沒有手術")}
        if prior_no_admission:
            known["inpatient"] = ("no", "沒有住院")
        payload = semantic(request, "confirm_claim", "請確認是否先查看門診文件資訊？", **known)
        return httpx.Response(200, json=completion(payload))

    answer = run(item, current, handler)
    assert answer["response_type"] == "claim_suggestion"
    assert [entry["id"] for entry in answer["suggested_claim_types"]] == ["outpatient"]
    assert answer["proposed_case_updates"] == {"claim_type_id": "outpatient", "conditions": {"cause": "accident", "surgery": "no", "receipt_type": "unknown"}}
    assert answer["source_references"][0]["source_id"] == "cardif-claims"
    assert answer["source_references"][0]["official_url"] == "https://life.cardif.com.tw/zh/a314"
    assert answer["requires_human_review"] is True
    if care_field == "emergency":
        assert "急診是否適用仍待個別保單及官方確認" in answer["message"]


@pytest.mark.parametrize("current,care_field,care_quote,inferred_field,inferred_quote,prior_no_admission", [
    ("只有急診，當天回家，沒有手術", "emergency", "只有急診", "outpatient", "只有急診，當天回家，沒有手術", True),
    ("只有急診，當天回家，沒有手術", "emergency", "只有急診", "inpatient", "當天回家", True),
    ("只有門診，沒有手術", "outpatient", "只有門診", "emergency", "只有門診", False),
    ("只有門診，沒有手術", "outpatient", "只有門診", "inpatient", "只有門診", False),
])
def test_exclusive_visit_or_returning_home_cannot_fabricate_another_care_negative(current, care_field, care_quote, inferred_field, inferred_quote, prior_no_admission):
    item = case(None, "我出車禍了", *( ["沒有住院"] if prior_no_admission else [] ))

    def handler(request):
        known = {"cause": ("accident", "出車禍"), care_field: ("yes", care_quote), "surgery": ("no", "沒有手術")}
        if prior_no_admission:
            known["inpatient"] = ("no", "沒有住院")
        known[inferred_field] = ("no", inferred_quote)
        return httpx.Response(200, json=completion(semantic(request, "confirm_claim", "請確認是否先查看門診文件資訊？", **known)))

    with pytest.raises(AIError) as caught:
        run(item, current, handler)
    assert caught.value.code == "INVALID_LLM_RESPONSE" and caught.value.status == 503


def test_workspace_ordinary_correction_uses_semantics_without_mutating_confirmed_case():
    def handler(request):
        content = semantic(request, "confirm_claim", "已了解本次沒有住院，只有急診。請確認是否要調整原先選擇。",
                           inpatient=("no", "沒住院"), emergency=("yes", "只有看急診"))
        return httpx.Response(200, json=completion(content))
    answer = run(case("inpatient"), "其實我沒住院，只有看急診", handler)
    assert answer["provider"] == "openai_compatible"
    assert answer["response_type"] == "clarification"
    assert answer["proposed_case_updates"] == {} and answer["suggested_claim_types"] == []
    assert "確認" in answer["message"]


@pytest.mark.parametrize("mutation", ["made_up_fact", "wrong_user_turn", "assistant_quote", "contradiction", "extra_key", "bad_enum",
                                     "known_question", "url", "amount", "approval", "document_requirement", "too_long", "missing_fact"])
def test_untrusted_semantic_facts_and_messages_are_rejected_without_fallback(mutation):
    def handler(request):
        result = semantic(request, "outpatient_or_emergency", "已了解沒有住院，請問曾看門診或去急診嗎？", inpatient=("no", "沒有住院"))
        if mutation == "made_up_fact": result["facts"]["outpatient"] = {"value": "yes", "turn": 1, "quote": "沒有住院"}
        elif mutation == "wrong_user_turn": result["facts"]["inpatient"]["turn"] = 999
        elif mutation == "assistant_quote": result["facts"]["inpatient"]["turn"] = 2
        elif mutation == "contradiction": result["facts"]["inpatient"]["value"] = "yes"
        elif mutation == "extra_key": result["proposed_case_updates"] = {"documents": []}
        elif mutation == "bad_enum": result["facts"]["cause"]["value"] = "approved"
        elif mutation == "known_question": result["question"] = "inpatient"; result["message"] = "您有沒有住院？"
        elif mutation == "url": result["message"] = "請到 https://evil.test/ 申請。"
        elif mutation == "amount": result["message"] = "本次可以獲賠十萬元。"
        elif mutation == "approval": result["message"] = "我保證您符合資格並核准理賠。"
        elif mutation == "document_requirement": result["message"] = "您必須提供診斷證明與收據。"
        elif mutation == "too_long": result["message"] = "請確認" * 300
        elif mutation == "missing_fact": result["facts"].pop("surgery")
        return httpx.Response(200, json=completion(result))
    item = case(None, "沒有住院")
    item["messages"].append({"role": "assistant", "content": "沒有住院", "response": {"response_type": "clarification"}})
    with pytest.raises(AIError) as caught:
        run(item, "沒有住院", handler)
    assert caught.value.code == "INVALID_LLM_RESPONSE" and caught.value.status == 503


@pytest.mark.parametrize("status,code", [(429, "LLM_RATE_LIMITED"), (401, "LLM_PROVIDER_ERROR"), (503, "LLM_PROVIDER_ERROR")])
def test_semantic_provider_errors_remain_explicit_without_a_rules_fallback(status, code):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, text="private provider error")
    with pytest.raises(AIError) as caught:
        run(case(), "你好", handler)
    assert caught.value.code == code and caught.value.status == 503
    assert len(calls) == 1 and "private" not in caught.value.message


def test_semantic_request_keeps_free_guards_and_only_minimal_context():
    def handler(request):
        body = json.loads(request.content)
        content = json.loads(body["messages"][1]["content"])
        assert set(content) == {"dialogue", "confirmed_case"}
        assert all(set(item) == {"turn", "role", "content"} for item in content["dialogue"])
        assert body["provider"] == {"max_price": {"prompt": 0, "completion": 0, "request": 0, "image": 0},
                                    "require_parameters": True, "allow_fallbacks": False}
        assert body["reasoning"] == {"effort": "minimal"} and body["store"] is False
        assert body["max_completion_tokens"] == 4096
        assert "never-send-case-id" not in request.content.decode() and "never-send-ocr" not in request.content.decode()
        return httpx.Response(200, json=completion(semantic(request)))
    assert run(case(), "你好", handler)["provider"] == "openai_compatible"


@pytest.mark.parametrize("text,cause_quote,admission_quote,surgery_quote", [
    ("昨天過馬路被機車撞到，在醫院睡了三晚，醫師沒有幫我開刀", "被機車撞到", "在醫院睡了三晚", "醫師沒有幫我開刀"),
    ("摔車之後被留院觀察三個晚上，沒有動刀", "摔車", "被留院觀察三個晚上", "沒有動刀"),
])
def test_model_understood_paraphrases_are_not_locked_to_the_old_classifier_keywords(text, cause_quote, admission_quote, surgery_quote):
    def handler(request):
        return httpx.Response(200, json=completion(semantic(request, "confirm_claim", "了解，依您描述可先查看住院文件資訊，請確認本次情形。",
            cause=("accident", cause_quote), inpatient=("yes", admission_quote), surgery=("no", surgery_quote))))
    answer = run(case(), text, handler)
    assert answer["suggested_claim_types"][0]["id"] == "inpatient"
    assert answer["proposed_case_updates"]["conditions"] == {"cause": "accident", "surgery": "no", "receipt_type": "unknown"}


def test_ambiguous_paraphrase_can_be_clarified_by_the_model_instead_of_guessed():
    def handler(request):
        return httpx.Response(200, json=completion(semantic(request, "inpatient", "您提到在醫院過夜，請確認有辦理住院嗎？")))
    answer = run(case(), "在醫院睡了三晚", handler)
    assert answer["response_type"] == "clarification" and answer["proposed_case_updates"] == {}


@pytest.mark.parametrize("kind", ["dropped_fact", "old_fact", "unconfirmed_cancer", "direct_negation", "bad_cost"])
def test_semantic_cannot_erase_or_invent_evidence_backed_state(kind):
    item, current = case(), "沒有住院"
    if kind == "old_fact": item = case(None, "我住院了")
    if kind == "unconfirmed_cancer": current = "是癌症嗎？"
    if kind == "direct_negation": current = "醫師沒有幫我開刀"
    def handler(request):
        if kind == "old_fact": result = semantic(request, "confirm_claim", "請確認住院資訊。", inpatient=("yes", "我住院了"))
        elif kind == "unconfirmed_cancer": result = semantic(request, "confirm_claim", "請確認本次已確診癌症。", critical_diagnosis=("yes", "癌症"))
        elif kind == "direct_negation": result = semantic(request, "medical_records", "請確認本次就醫紀錄。", surgery=("yes", current))
        else: result = semantic(request, "care_setting", "請問本次是否已就醫？")
        response = completion(result)
        if kind == "bad_cost": response["usage"]["cost"] = False
        return httpx.Response(200, json=response)
    with pytest.raises(AIError) as caught:
        run(item, current, handler)
    assert caught.value.code == "INVALID_LLM_RESPONSE"


def test_out_of_scope_still_uses_model_dialogue_without_inventing_an_answer():
    def handler(request):
        return httpx.Response(200, json=completion(semantic(request, "scope", "我能協助理賠文件準備，您想了解哪個就醫事件？")))
    assert run(case("inpatient"), "火星船票", handler)["provider"] == "openai_compatible"


def test_successful_semantic_default_transport_can_verify_only_after_full_validation(monkeypatch):
    async def handler(self, request):
        return httpx.Response(200, json=completion(semantic(request)), request=request)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", handler)
    config = settings()
    provider = adapter.OpenAICompatibleProvider(config)
    assert adapter.verification_snapshot(config) is None
    assert asyncio.run(provider.respond(case(), "你好"))["provider"] == "openai_compatible"
    assert adapter.verification_snapshot(config)["cost"] == 0


@pytest.mark.parametrize("kind", ["unknown_admission_message", "unknown_cancer_message", "medical_instruction", "truncated_negation",
                                     "truncated_uncertainty", "truncated_surgery", "unrelated_quote"])
def test_reviewed_provenance_and_natural_message_attacks_are_rejected(kind):
    text = "你好"
    if kind == "truncated_negation": text = "沒有住院"
    if kind == "truncated_uncertainty": text = "還不確定是否有手術"
    if kind == "truncated_surgery": text = "醫師沒有幫我開刀"
    if kind == "unrelated_quote": text = "住院三天，你好"
    def handler(request):
        if kind == "unknown_admission_message": result = semantic(request, "care_setting", "您已住院，請問本次是否有去門診？")
        elif kind == "unknown_cancer_message": result = semantic(request, "critical_diagnosis", "您已確診癌症，請問是哪位醫師確認的？")
        elif kind == "medical_instruction": result = semantic(request, "care_setting", "請停止目前的藥物，立即安排手術。請問是否已就醫？")
        elif kind == "truncated_negation": result = semantic(request, "confirm_claim", "請確認本次住院資訊。", inpatient=("yes", "住院"))
        elif kind == "truncated_uncertainty": result = semantic(request, "medical_records", "請確認本次就醫紀錄。", surgery=("yes", "手術"))
        elif kind == "truncated_surgery": result = semantic(request, "medical_records", "請確認本次就醫紀錄。", surgery=("yes", "開刀"))
        else: result = semantic(request, "confirm_claim", "請確認本次住院資訊。", inpatient=("yes", "住院三天"), surgery=("yes", "你好"))
        return httpx.Response(200, json=completion(result))
    with pytest.raises(AIError) as caught:
        run(case(), text, handler)
    assert caught.value.code == "INVALID_LLM_RESPONSE"


def test_a_short_negative_answer_cannot_be_inverted_into_a_positive_fact():
    item = case(None, "我出車禍了")
    item["messages"].append({"role": "assistant", "content": "請問有沒有住院？", "response": {"response_type": "clarification"}})
    def handler(request):
        return httpx.Response(200, json=completion(semantic(request, "confirm_claim", "請確認住院資料。", inpatient=("yes", "沒有"))))
    with pytest.raises(AIError) as caught:
        run(item, "沒有", handler)
    assert caught.value.code == "INVALID_LLM_RESPONSE"


@pytest.mark.parametrize("message", ["您好，可以說說這次的狀況嗎？", "您好，請告訴我這次的事故或就醫情況。"])
def test_model_greeting_accepts_natural_event_invitation_without_fixed_wording(message):
    def handler(request):
        return httpx.Response(200, json=completion(semantic(request, "describe_event", message)))
    answer = run(case(), "你好", handler)
    assert answer["provider"] == "openai_compatible" and answer["message"] == message
    assert answer["response_type"] == "clarification" and answer["proposed_case_updates"] == {}


@pytest.mark.parametrize("message", ["要不要先以門診文件作為準備方向？", "您願意先從門診文件開始準備嗎？"])
def test_model_confirmation_can_use_natural_confirmation_phrasing(message):
    def handler(request):
        return httpx.Response(200, json=completion(semantic(request, "confirm_claim", message, outpatient=("yes", "已看過門診"))))
    answer = run(case(), "已看過門診", handler)
    assert answer["response_type"] == "claim_suggestion"
    assert answer["message"].startswith(message)
    assert "請確認類別與條件後再建立清單" in answer["message"]


def test_natural_alternative_question_is_not_mistaken_for_a_confirmed_visit():
    message = "已了解沒有住院，您是去急診還是門診呢？"
    def handler(request):
        return httpx.Response(200, json=completion(semantic(request, "outpatient_or_emergency", message, inpatient=("no", "沒有住院"))))
    answer = run(case(), "沒有住院", handler)
    assert answer["message"] == message
    assert answer["response_type"] == "clarification" and answer["proposed_case_updates"] == {}


@pytest.mark.parametrize("tokens,allowed", [(2000, True), (4096, True), (4097, False)])
def test_semantic_completion_usage_is_checked_against_its_requested_budget(tokens, allowed):
    def handler(request):
        assert json.loads(request.content)["max_completion_tokens"] == 4096
        result = completion(semantic(request))
        result["usage"]["completion_tokens"] = tokens
        result["usage"]["total_tokens"] = 300 + tokens
        return httpx.Response(200, json=result)
    if allowed:
        assert run(case(), "你好", handler)["provider"] == "openai_compatible"
    else:
        with pytest.raises(AIError) as caught:
            run(case(), "你好", handler)
        assert caught.value.code == "INVALID_LLM_RESPONSE"


@pytest.mark.parametrize("mutation", ["paid", "length"])
def test_larger_semantic_budget_keeps_zero_cost_and_nontruncation_guards(mutation):
    def handler(request):
        result = completion(semantic(request))
        result["usage"].update(completion_tokens=2000, total_tokens=2300)
        if mutation == "paid": result["usage"]["cost"] = 0.01
        else: result["choices"][0]["finish_reason"] = "length"
        return httpx.Response(200, json=result)
    with pytest.raises(AIError) as caught:
        run(case(), "你好", handler)
    assert caught.value.code == "INVALID_LLM_RESPONSE"


def test_semantic_budget_does_not_leak_into_a_later_evidence_request():
    budgets = []
    def handler(request):
        body = json.loads(request.content)
        budgets.append(body["max_completion_tokens"])
        content = json.loads(body["messages"][1]["content"])
        if "dialogue" in content:
            result = completion(semantic(request))
            result["usage"].update(completion_tokens=2000, total_tokens=2300)
        else:
            result = completion({"evidence_ids": [content["evidence"][0]["id"]]})
            result["usage"].update(completion_tokens=1801, total_tokens=2101)
        return httpx.Response(200, json=result)
    provider = adapter.OpenAICompatibleProvider(settings(), transport=httpx.MockTransport(handler))
    assert asyncio.run(provider.respond(case(), "你好"))["provider"] == "openai_compatible"
    with pytest.raises(AIError) as caught:
        asyncio.run(provider.respond(case("inpatient"), "手術證明是否需要另附？"))
    assert caught.value.code == "INVALID_LLM_RESPONSE"
    assert budgets == [4096, 1800]
