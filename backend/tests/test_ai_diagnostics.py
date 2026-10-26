"""Safe helper diagnostics: actual validation rejects, never raw model logs."""
import copy
import logging
import re
from types import SimpleNamespace

import pytest

from backend.app.ai import openai_compatible as adapter
from backend.app.ai import semantic_dialogue as semantic
from backend.app.ai.providers import AIError
from backend.app.ai.retrieval import OfficialRetriever


SAFE_ADDITIONAL_FIELDS = [
    "cause", "surgery", "receipt_type", "payment_method",
    "insured_relation", "diagnosis_name", "surgery_name", "surgery_date", "visit_dates",
    "visit_dates.admission", "visit_dates.discharge", "visit_dates.visit", "visit_dates.discharge_pending",
    "policy_products", "deferred_fields",
]


def assert_safe_log(caplog, error, stage, field=None):
    records = [record for record in caplog.records if record.name == adapter.__name__]
    assert len(records) == 1
    record = records[0]
    match = re.fullmatch(r"LLM validation rejected stage=(\w+) line=(\d+) field=([\w.]+)", record.getMessage())
    assert match and match[1] == stage
    line = 0
    trace = error.__traceback__
    while trace:
        if trace.tb_frame.f_code.co_name == stage:
            line = trace.tb_lineno
        trace = trace.tb_next
    assert int(match[2]) == line and (line > 0 if stage != "unknown" else line == 0)
    if field is not None:
        assert match[3] == field
    assert record.exc_info is None and record.stack_info is None
    assert "sensitive-dummy" not in caplog.text and "肺切除" not in caplog.text


@pytest.mark.parametrize("field", SAFE_ADDITIONAL_FIELDS)
def test_additional_validation_logs_actual_helper_line_and_only_safe_field_enum(caplog, field):
    generated = {"details": {field: {"value": "sensitive-dummy-value", "turn": 1, "quote": "sensitive-dummy-quote"}}}
    content = {"dialogue": [{"turn": 1, "role": "user", "content": "sensitive-dummy-user-medical-message"}]}
    with caplog.at_level(logging.WARNING, logger=adapter.__name__), pytest.raises(AIError) as caught:
        semantic._extract_additional(generated, content, adapter.OpenAICompatibleProvider._invalid)
    assert caught.value.code == "INVALID_LLM_RESPONSE" and caught.value.status == 503
    assert_safe_log(caplog, caught.value, "_extract_additional", field)


def test_workflow_validation_logs_actual_helper_without_medical_details(caplog):
    case = {"claim_type_id": None, "conditions": {"cause": "unknown", "surgery": "unknown"}, "details": {},
            "messages": [], "revision": 0, "dialogue_state": {"facts": {}, "pending_question": None, "deferred_fields": []}}
    content = semantic.request_content(copy.deepcopy(case), "我做肺切除手術，sensitive-dummy-medical-details")
    values = {field: "unknown" for field in semantic.FACTS}
    generated = {"facts": {field: {"value": "unknown", "turn": None, "quote": ""} for field in semantic.FACTS},
                 "details": {"surgery_name": {"value": "肺切除手術", "turn": content["dialogue"][-1]["turn"], "quote": "我做肺切除手術"}}}
    with caplog.at_level(logging.WARNING, logger=adapter.__name__), pytest.raises(AIError) as caught:
        semantic._workflow_answer(generated, values, content, OfficialRetriever(), adapter.OpenAICompatibleProvider._invalid)
    assert caught.value.code == "INVALID_LLM_RESPONSE"
    assert_safe_log(caplog, caught.value, "_workflow_answer", "surgery")


@pytest.mark.parametrize("field", [[], {}, True, None, "sensitive-dummy-field", "visit_dates.sensitive-dummy-field"])
@pytest.mark.parametrize("stage", ["_extract_additional", "_workflow_answer"])
def test_new_helper_diagnostics_reject_arbitrary_field_values(monkeypatch, caplog, field, stage):
    import inspect

    caller = SimpleNamespace(f_code=SimpleNamespace(co_name=stage), f_lineno=88,
                             f_globals={"__name__": semantic.__name__}, f_locals={"field": field, "quote": "sensitive-dummy-quote"})
    monkeypatch.setattr(inspect, "currentframe", lambda: SimpleNamespace(f_back=caller))
    with caplog.at_level(logging.WARNING, logger=adapter.__name__), pytest.raises(AIError):
        adapter.OpenAICompatibleProvider._invalid()
    records = [record for record in caplog.records if record.name == adapter.__name__]
    assert len(records) == 1
    assert records[0].getMessage() == f"LLM validation rejected stage={stage} line=88 field=none"
    assert records[0].exc_info is None and records[0].stack_info is None
    assert "sensitive-dummy" not in caplog.text


@pytest.mark.parametrize("stage", ["_extract_additional", "_workflow_answer"])
def test_same_named_external_helper_cannot_enter_diagnostic_allowlist(monkeypatch, caplog, stage):
    import inspect

    caller = SimpleNamespace(f_code=SimpleNamespace(co_name=stage), f_lineno=88,
                             f_globals={"__name__": "sensitive-dummy-other-module"}, f_locals={"field": "surgery"})
    monkeypatch.setattr(inspect, "currentframe", lambda: SimpleNamespace(f_back=caller))
    with caplog.at_level(logging.WARNING, logger=adapter.__name__), pytest.raises(AIError):
        adapter.OpenAICompatibleProvider._invalid()
    records = [record for record in caplog.records if record.name == adapter.__name__]
    assert len(records) == 1
    assert records[0].getMessage() == "LLM validation rejected stage=unknown line=0 field=none"
    assert "sensitive-dummy" not in caplog.text
