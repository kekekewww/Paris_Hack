"""Offline tests for the one explicitly authorized paid OpenRouter model."""
import asyncio
import copy
import json
import logging
import re
from types import SimpleNamespace

import httpx
import pytest

from backend.app.ai import conversation
from backend.app.ai import openai_compatible as adapter
from backend.app.ai.providers import AIError


MODEL = "deepseek/deepseek-v4.1-flash-1017"
CANONICAL_MODEL = "deepseek/deepseek-v4.1-flash-20261017"
CASE = {"id": "synthetic-paid-case", "claim_type_id": "inpatient",
        "conditions": {"cause": "unknown", "surgery": "unknown"}, "documents": [], "messages": []}
QUESTION = "手術證明是否需要另附？"


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    for name in ("LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL", "LLM_PROVIDER", "LLM_TIMEOUT_SECONDS", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    adapter.verification_snapshot(None)
    yield
    adapter.verification_snapshot(None)


def settings(**changes):
    return adapter.OpenAICompatibleSettings(**{
        "api_key": "offline-paid-synthetic-key", "model": MODEL,
        "base_url": "https://openrouter.ai/api/v1", **changes})


def configure(monkeypatch, **changes):
    for name, value in {"LLM_PROVIDER": "openai_compatible", "LLM_API_KEY": "offline-paid-synthetic-key",
                        "LLM_MODEL": MODEL, "LLM_BASE_URL": "https://openrouter.ai/api/v1", **changes}.items():
        monkeypatch.setenv(name, value)


def envelope(content, *, model=CANONICAL_MODEL, cost=0.0004, completion_tokens=140):
    return {"model": model, "usage": {"cost": cost, "prompt_tokens": 240,
            "completion_tokens": completion_tokens, "total_tokens": 240 + completion_tokens},
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(content, ensure_ascii=False)}}]}


def completion(request, **metadata):
    evidence = json.loads(json.loads(request.content)["messages"][1]["content"])["evidence"]
    return envelope({"evidence_ids": [evidence[0]["id"]]}, **metadata)


def respond_with(handler, *, config=None):
    provider = adapter.OpenAICompatibleProvider(config or settings(), transport=httpx.MockTransport(handler))
    return asyncio.run(provider.respond(copy.deepcopy(CASE), QUESTION))


def semantic_greeting():
    return {"facts": {name: {"value": "unknown", "turn": None, "quote": ""} for name in
            ("cause", "inpatient", "outpatient", "emergency", "critical_diagnosis", "surgery")},
            "question": "describe_event", "message": "您好，可以說說這次的狀況嗎？"}


def test_explicit_paid_model_uses_bounded_official_profile_without_cross_model_fallback():
    observed = {}

    def handler(request):
        observed.update(json.loads(request.content))
        assert str(request.url) == "https://openrouter.ai/api/v1/chat/completions"
        return httpx.Response(200, json=completion(request))

    answer = respond_with(handler)
    assert observed["model"] == MODEL
    assert observed["provider"] == {"max_price": {"prompt": 0.3, "completion": 1.2, "request": 0, "image": 0},
                                    "require_parameters": True, "allow_fallbacks": False, "only": ["deepseek"]}
    assert observed["reasoning"] == {"effort": "low"}
    assert observed["max_completion_tokens"] == 1800
    assert observed["response_format"] == {"type": "json_object"}
    assert observed["stream"] is False and observed["store"] is False
    assert not {"models", "plugins", "route"}.intersection(observed)
    assert answer["provider"] == "openai_compatible" and answer["is_simulated"] is False
    assert answer["source_references"] and answer["proposed_case_updates"] == {}
    assert not {"model", "cost", "usage"}.intersection(answer)


@pytest.mark.parametrize("returned_model", [MODEL, CANONICAL_MODEL])
@pytest.mark.parametrize("cost", [0, 0.0004, 0.05])
def test_paid_metadata_accepts_only_authorized_model_names_and_bounded_numeric_cost(returned_model, cost):
    assert respond_with(lambda request: httpx.Response(200, json=completion(
        request, model=returned_model, cost=cost)))["source_references"]


@pytest.mark.parametrize("cost", [None, False, True, "0", -0.0001, 0.0500001, float("nan"),
                                  float("inf"), -float("inf"), 1e100, 10 ** 1000])
def test_paid_metadata_rejects_invalid_or_excessive_cost(cost):
    with pytest.raises(AIError) as caught:
        respond_with(lambda request: httpx.Response(200, content=json.dumps(
            completion(request, cost=cost)).encode()))
    assert caught.value.code == "INVALID_LLM_RESPONSE"


@pytest.mark.parametrize("returned_model", ["openrouter/free", "openrouter/auto", "liquid/lfm-2.5-2.6b:free",
    "deepseek/deepseek-v4.1-flash", "deepseek/deepseek-v4.1-flash-20261017:free", MODEL.upper(), MODEL + " "])
def test_paid_metadata_rejects_any_unmatched_actual_model_even_at_zero_cost(returned_model):
    with pytest.raises(AIError) as caught:
        respond_with(lambda request: httpx.Response(200, json=completion(request, model=returned_model, cost=0)))
    assert caught.value.code == "INVALID_LLM_RESPONSE"


@pytest.mark.parametrize("changes", [
    {"model": CANONICAL_MODEL}, {"model": "deepseek/deepseek-v4.1-flash"}, {"model": "deepseek/deepseek-chat"},
    {"model": MODEL + ":free"}, {"model": MODEL.upper()},
    {"base_url": "https://openrouter.ai/v1"}, {"base_url": "https://openrouter.ai/api/v1/other"},
    {"base_url": "https://OPENROUTER.AI/api/v1"}, {"base_url": "https://openrouter.ai:443/api/v1"},
])
def test_paid_requested_model_and_endpoint_are_exact_allowlists(changes):
    with pytest.raises(AIError) as caught:
        settings(**changes)
    assert caught.value.code == "INVALID_LLM_CONFIG"


def test_paid_semantic_profile_retains_bounded_context_and_separate_token_budget():
    def handler(request):
        payload = json.loads(request.content)
        content = json.loads(payload["messages"][1]["content"])
        assert payload["model"] == MODEL and payload["max_completion_tokens"] == 4096
        assert set(content) == {"dialogue", "confirmed_case"}
        assert content["dialogue"] == [{"turn": 1, "role": "user", "content": "你好"}]
        assert "synthetic-paid-case" not in request.content.decode()
        return httpx.Response(200, json=envelope(semantic_greeting(), completion_tokens=4096))

    case = {**copy.deepcopy(CASE), "claim_type_id": None}
    provider = adapter.OpenAICompatibleProvider(settings(), transport=httpx.MockTransport(handler))
    answer = asyncio.run(provider.respond(case, "你好"))
    assert answer["response_type"] == "clarification" and answer["provider"] == "openai_compatible"
    assert answer["proposed_case_updates"] == {} and answer["suggested_claim_types"] == []
    assert adapter.verification_snapshot(settings()) is None


@pytest.mark.parametrize("field,value", [("cost", "missing"), ("completion_tokens", 1801),
    ("total_tokens", 1), ("prompt_tokens", True), ("completion_tokens", 1.5), ("total_tokens", 10 ** 100)])
def test_paid_profile_does_not_skip_existing_usage_accounting(field, value):
    def handler(request):
        result = completion(request)
        if value == "missing":
            result["usage"].pop(field)
        else:
            result["usage"][field] = value
        return httpx.Response(200, json=result)

    with pytest.raises(AIError) as caught:
        respond_with(handler)
    assert caught.value.code == "INVALID_LLM_RESPONSE"


@pytest.mark.parametrize("mutation", ["length", "oversized", "unknown_evidence", "extra_keys"])
def test_paid_metadata_cannot_bypass_content_and_envelope_validation(mutation):
    def handler(request):
        result = completion(request)
        if mutation == "length":
            result["choices"][0]["finish_reason"] = "length"
        elif mutation == "oversized":
            return httpx.Response(200, content=b"x" * (adapter.MAX_RESPONSE_BYTES + 1))
        else:
            content = {"evidence_ids": ["invented-id"]} if mutation == "unknown_evidence" else {
                "evidence_ids": ["surgery-condition"], "proposed_case_updates": {"claim_type_id": "outpatient"}}
            result["choices"][0]["message"]["content"] = json.dumps(content)
        return httpx.Response(200, json=result)

    with pytest.raises(AIError) as caught:
        respond_with(handler)
    assert caught.value.code == "INVALID_LLM_RESPONSE"
    assert adapter.verification_snapshot(settings()) is None


@pytest.mark.parametrize("status,code", [(429, "LLM_RATE_LIMITED"), (401, "LLM_PROVIDER_ERROR"), (402, "LLM_PROVIDER_ERROR"),
                                        (502, "LLM_PROVIDER_ERROR"), (503, "LLM_PROVIDER_ERROR")])
def test_paid_errors_are_safe_and_do_not_retry_or_describe_a_free_model(status, code):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, text="synthetic-private-paid-body")

    with pytest.raises(AIError) as caught:
        respond_with(handler)
    assert caught.value.code == code and caught.value.status == 503
    assert len(calls) == 1
    assert "免費" not in caught.value.message and "synthetic-private-paid-body" not in caught.value.message


def test_paid_timeout_retains_current_openrouter_default_and_maximum():
    assert settings().timeout_seconds == 300
    assert settings(timeout_seconds=299.5).timeout_seconds == 299.5
    with pytest.raises(AIError) as caught:
        settings(timeout_seconds=300.1)
    assert caught.value.code == "INVALID_LLM_CONFIG"


@pytest.mark.parametrize("change", [{"LLM_API_KEY": "new-offline-key"}, {"LLM_MODEL": "openrouter/free"},
                                    {"LLM_TIMEOUT_SECONDS": "299"}])
def test_paid_default_transport_verifies_only_after_validation_and_configuration_changes_clear_it(monkeypatch, change):
    configure(monkeypatch)

    async def handler(self, request):
        return httpx.Response(200, json=completion(request), request=request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", handler)
    assert conversation.provider_status()["llm_verified"] is False
    assert asyncio.run(conversation.respond(copy.deepcopy(CASE), QUESTION))["source_references"]
    assert conversation.provider_status()["llm_verified"] is True
    snapshot = adapter.verification_snapshot(settings())
    assert snapshot == {"model": CANONICAL_MODEL, "cost": 0.0004,
                        "prompt_tokens": 240, "completion_tokens": 140, "total_tokens": 380}
    configure(monkeypatch, **change)
    assert conversation.provider_status()["llm_verified"] is False
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
    configure(monkeypatch)
    assert conversation.provider_status()["llm_verified"] is False


@pytest.mark.parametrize("mutation", ["cost", "model", "content"])
def test_paid_failed_default_transport_response_cannot_establish_verification(monkeypatch, mutation):
    configure(monkeypatch)

    async def handler(self, request):
        result = completion(request)
        if mutation == "cost":
            result["usage"]["cost"] = 0.051
        elif mutation == "model":
            result["model"] = "different/provider-model"
        else:
            result["choices"][0]["message"]["content"] = json.dumps({"evidence_ids": ["unknown-id"]})
        return httpx.Response(200, json=result, request=request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", handler)
    with pytest.raises(AIError):
        asyncio.run(conversation.respond(copy.deepcopy(CASE), QUESTION))
    assert conversation.provider_status()["llm_verified"] is False


def assert_safe_rejection_log(caplog, caught, stage, field="none"):
    records = [record for record in caplog.records if record.name == adapter.__name__]
    assert len(records) == 1
    record = records[0]
    match = re.fullmatch(r"LLM validation rejected stage=(\w+) line=(\d+) field=(\w+)", record.getMessage())
    assert match and match.group(1) == stage and match.group(3) == field
    expected_line = 0
    trace = caught.value.__traceback__
    while trace is not None:
        if trace.tb_frame.f_code.co_name == stage:
            expected_line = trace.tb_lineno
        trace = trace.tb_next
    assert int(match.group(2)) == expected_line
    assert record.exc_info is None and record.stack_info is None
    assert "sensitive-dummy" not in caplog.text


@pytest.mark.parametrize("field", ["cause", "inpatient", "outpatient", "emergency", "critical_diagnosis", "surgery"])
def test_semantic_rejection_logs_only_stage_line_and_allowlisted_field(caplog, field):
    from backend.app.ai.semantic_dialogue import validate_semantics

    generated = semantic_greeting()
    generated["facts"][field]["quote"] = "sensitive-dummy-model-quote"
    generated["message"] = "您好，可以說說這次的狀況嗎？"
    content = {"dialogue": [{"turn": 1, "role": "user", "content": "sensitive-dummy-user-medical-message"}],
               "confirmed_case": {"claim_type_id": None, "conditions": {}}}
    provider = adapter.OpenAICompatibleProvider(settings(api_key="sensitive-dummy-credential"))
    with caplog.at_level(logging.WARNING, logger=adapter.__name__), pytest.raises(AIError) as caught:
        validate_semantics(generated, content, provider.retriever, provider._invalid)
    assert caught.value.code == "INVALID_LLM_RESPONSE"
    assert_safe_rejection_log(caplog, caught, "validate_semantics", field)


@pytest.mark.parametrize("stage", ["_openrouter_metadata", "_request_json", "respond"])
def test_adapter_rejection_logs_only_whitelisted_stage_and_actual_line(caplog, stage):
    def handler(request):
        result = completion(request)
        if stage == "_openrouter_metadata":
            result["usage"]["cost"] = "sensitive-dummy-cost"
        elif stage == "_request_json":
            result["choices"][0]["finish_reason"] = "sensitive-dummy-finish"
        else:
            content = {"evidence_ids": ["surgery-condition"], "sensitive-dummy-key": "sensitive-dummy-text"}
            result["choices"][0]["message"]["content"] = json.dumps(content)
        return httpx.Response(200, json=result)

    with caplog.at_level(logging.WARNING, logger=adapter.__name__), pytest.raises(AIError) as caught:
        respond_with(handler, config=settings(api_key="sensitive-dummy-credential"))
    assert caught.value.code == "INVALID_LLM_RESPONSE"
    assert_safe_rejection_log(caplog, caught, stage)


def test_unknown_rejection_caller_cannot_log_its_name_or_local_values(caplog):
    def sensitive_dummy_caller():
        field = ["sensitive-dummy-field"]
        message = "sensitive-dummy-prompt"
        adapter.OpenAICompatibleProvider._invalid()

    with caplog.at_level(logging.WARNING, logger=adapter.__name__), pytest.raises(AIError) as caught:
        sensitive_dummy_caller()
    assert_safe_rejection_log(caplog, caught, "unknown")
    assert "sensitive_dummy_caller" not in caplog.text


@pytest.mark.parametrize("field", [[], {}, True, None, "sensitive-dummy-field"])
def test_diagnostic_field_is_type_checked_and_allowlisted_before_logging(monkeypatch, caplog, field):
    # A corrupted or instrumented caller frame must never cause an unhashable
    # field error or send arbitrary locals to the diagnostic logger.
    import inspect

    caller = SimpleNamespace(f_code=SimpleNamespace(co_name="validate_semantics"), f_lineno=88,
                             f_globals={"__name__": "backend.app.ai.semantic_dialogue"}, f_locals={"field": field})
    monkeypatch.setattr(inspect, "currentframe", lambda: SimpleNamespace(f_back=caller))
    with caplog.at_level(logging.WARNING, logger=adapter.__name__), pytest.raises(AIError) as caught:
        adapter.OpenAICompatibleProvider._invalid()
    assert caught.value.code == "INVALID_LLM_RESPONSE"
    records = [record for record in caplog.records if record.name == adapter.__name__]
    assert len(records) == 1
    assert records[0].getMessage() == "LLM validation rejected stage=validate_semantics line=88 field=none"
    assert "sensitive-dummy" not in caplog.text


def test_same_named_external_caller_is_still_an_unknown_diagnostic_stage(caplog):
    def validate_semantics():
        field = "surgery"
        adapter.OpenAICompatibleProvider._invalid()

    with caplog.at_level(logging.WARNING, logger=adapter.__name__), pytest.raises(AIError) as caught:
        validate_semantics()
    assert_safe_rejection_log(caplog, caught, "unknown")


def test_caller_without_module_cannot_bypass_diagnostic_stage_allowlist(monkeypatch, caplog):
    import inspect

    caller = SimpleNamespace(f_code=SimpleNamespace(co_name="sensitive-dummy-caller"), f_lineno=88,
                             f_globals={}, f_locals={"field": "surgery"})
    monkeypatch.setattr(inspect, "currentframe", lambda: SimpleNamespace(f_back=caller))
    with caplog.at_level(logging.WARNING, logger=adapter.__name__), pytest.raises(AIError):
        adapter.OpenAICompatibleProvider._invalid()
    records = [record for record in caplog.records if record.name == adapter.__name__]
    assert len(records) == 1
    assert records[0].getMessage() == "LLM validation rejected stage=unknown line=0 field=none"


def test_unavailable_frame_keeps_safe_error_and_unknown_diagnostic(monkeypatch, caplog):
    import inspect

    monkeypatch.setattr(inspect, "currentframe", lambda: None)
    with caplog.at_level(logging.WARNING, logger=adapter.__name__), pytest.raises(AIError) as caught:
        adapter.OpenAICompatibleProvider._invalid()
    assert caught.value.code == "INVALID_LLM_RESPONSE"
    assert_safe_rejection_log(caplog, caught, "unknown")


@pytest.mark.parametrize("requested_model", [MODEL, "openrouter/free"])
def test_openrouter_document_query_is_redacted_without_sending_case_history_or_files(requested_model):
    from backend.app.ai.dialogue_privacy import redact_text

    query = ("姓名：王小明，身分證 A123456789，聯絡0912-345-678，ｔｅｓｔ－ｕｓｅｒ＠ｅｘａｍｐｌｅ．ｔｅｓｔ，"
             "密鑰＝ｓｋ－ｏｒ－ｖ１－ｏｆｆｌｉｎｅｑｕｅｒｙｃａｎａｒｙｔｏｋｅｎ；保險金申請書有哪些欄位與簽名需要確認？")
    case = {**copy.deepcopy(CASE), "claim_type_id": "outpatient",
            "private_raw_document": "private-document-canary",
            "messages": [{"role": "user", "content": "private-history-canary"}],
            "documents": [{"id": "application", "filename": "private-filename-canary.pdf",
                           "ocr": "private-ocr-canary", "analysis": {"field": "private-analysis-canary"}}]}
    before = copy.deepcopy(case)
    observed = {}

    def handler(request):
        body = json.loads(request.content)
        content = json.loads(body["messages"][1]["content"])
        assert set(content) == {"query", "evidence"}
        assert content["query"] == redact_text(query)
        assert content["query"].endswith("保險金申請書有哪些欄位與簽名需要確認？")
        assert all(set(item) == {"id", "title", "text"} for item in content["evidence"])
        for canary in ("王小明", "A123456789", "0912-345-678", "test-user@example.test",
                       "sk-or-v1-offlinequerycanarytoken", "synthetic-paid-case", "offline-paid-synthetic-key",
                       "private-history-canary", "private-document-canary", "private-filename-canary",
                       "private-ocr-canary", "private-analysis-canary"):
            assert canary not in request.content.decode()
        observed["selected"] = next(item for item in content["evidence"] if item["id"] == "application-precheck")
        return httpx.Response(200, json=envelope({"evidence_ids": [observed["selected"]["id"]]},
            model=CANONICAL_MODEL if requested_model == MODEL else "synthetic/concrete:free",
            cost=0.0004 if requested_model == MODEL else 0))

    provider = adapter.OpenAICompatibleProvider(settings(model=requested_model), transport=httpx.MockTransport(handler))
    answer = asyncio.run(provider.respond(case, query))
    selected = observed["selected"]
    assert answer["message"].startswith("直接回答：申請書請檢查")
    assert all(field in answer["message"] for field in (
        "姓名", "保單號碼", "身分證字號", "聯絡方式", "申請項目", "付款方式", "稅務聲明選項", "申請人簽名與日期"))
    assert "適用條件：" in answer["message"] and "法律真實性" in answer["message"]
    assert "來源 [1]：保險金申請書（第 1 頁）" in answer["message"]
    canonical = next(chunk for chunk in provider.retriever.chunks if chunk["knowledge_id"] == selected["id"])
    assert answer["source_references"] == provider.retriever.references([canonical])
    assert answer["proposed_case_updates"] == {} and case == before


def test_openrouter_document_query_uses_the_shared_4000_character_input_boundary():
    from backend.app.ai.dialogue_privacy import redact_text

    prefix = "保險金申請書有哪些欄位與簽名需要確認？密鑰＝ｓｋ－ｏｒ－ｖ１－ｏｆｆｌｉｎｅｑｕｅｒｙｃａｎａｒｙｔｏｋｅｎ；"
    query = prefix + "字" * (4000 - len(prefix))

    def handler(request):
        content = json.loads(json.loads(request.content)["messages"][1]["content"])
        assert set(content) == {"query", "evidence"}
        assert content["query"] == redact_text(query)
        assert len(content["query"]) <= 4000
        assert "sk-or-v1-" not in content["query"]
        return httpx.Response(200, json=completion(request))

    assert respond_with_query(handler, query)["source_references"]


def test_overlong_openrouter_document_query_is_rejected_before_transport():
    prefix = "保險金申請書有哪些欄位與簽名需要確認？"
    query = prefix + "字" * (4001 - len(prefix))

    def handler(request):
        pytest.fail("An overlong current query must not reach the model")

    with pytest.raises(ValueError):
        respond_with_query(handler, query)


def respond_with_query(handler, query):
    provider = adapter.OpenAICompatibleProvider(settings(), transport=httpx.MockTransport(handler))
    return asyncio.run(provider.respond(copy.deepcopy(CASE), query))


def test_generic_document_profile_still_sends_only_its_original_task_and_evidence():
    def handler(request):
        content = json.loads(json.loads(request.content)["messages"][1]["content"])
        assert set(content) == {"task", "evidence"}
        item = content["evidence"][0]
        assert set(item) == {"evidence_id", "title", "text", "source_references"}
        return httpx.Response(200, json=envelope({"explanations": [{"evidence_id": item["evidence_id"], "text": item["text"]}],
            "source_references": item["source_references"], "proposed_case_updates": {}}))

    assert respond_with(handler, config=settings(model="generic-model", base_url="https://example.test/v1"))["source_references"]
