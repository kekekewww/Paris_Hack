"""Request-scoped demo keys; only constructed keys and offline HTTP are used."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
import sqlite3
import threading
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.ai import openai_compatible as adapter
from backend.app.main import create_app


KEY_A = "sk-or-v1-" + "a1" * 32
KEY_B = "sk-or-v1-" + "b2" * 32
SERVER_KEY = "sk-or-v1-" + "c3" * 32
QUESTION = "手術證明是否需要另附？"


@pytest.fixture
def configured(tmp_path, monkeypatch):
    values = {"CASE_DB_PATH": str(tmp_path / "runtime.sqlite3"), "RATE_LIMIT_REQUESTS": "1000",
              "RUNTIME_LLM_KEYS": "true", "LLM_PROVIDER": "grounded_rules", "LLM_API_KEY": SERVER_KEY,
              "LLM_MODEL": "unapproved/model", "LLM_BASE_URL": "https://unapproved.example/v1",
              "LLM_TIMEOUT_SECONDS": "1"}
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    adapter.verification_snapshot(None)
    calls = []

    async def handle(self, request):
        calls.append({"authorization": request.headers.get("authorization"), "url": str(request.url),
                      "body": json.loads(request.content)})
        evidence = json.loads(calls[-1]["body"]["messages"][1]["content"])["evidence"]
        return httpx.Response(200, request=request, json={"model": "deepseek/deepseek-v4.1-flash-20261017",
            "usage": {"cost": 0.001, "prompt_tokens": 240, "completion_tokens": 140, "total_tokens": 380},
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"evidence_ids": [evidence[0]["id"]]})}}]})

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", handle)
    app = create_app()
    with TestClient(app) as client:
        yield app, client, calls
    adapter.verification_snapshot(None)


def create_case(client):
    response = client.post("/api/v1/cases", json={"entry_path": "direct", "claim_type_id": "inpatient"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def finished(client, case_id, job_id):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/cases/{case_id}/message-jobs/{job_id}")
        assert response.status_code == 200, response.text
        if response.json()["status"] != "pending":
            return response.json()
        time.sleep(0.005)
    pytest.fail("Controlled runtime-key job did not finish")


def test_health_requires_its_own_key_without_falling_back_to_server(configured):
    _, client, calls = configured
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["llm_provider"] == "openai_compatible"
    assert response.json()["llm_configured"] is False
    assert response.json()["llm_verified"] is False
    response = client.get("/api/v1/health", headers={"X-OpenRouter-Key": KEY_A})
    assert response.json()["llm_configured"] is True
    assert response.json()["llm_verified"] is False
    assert calls == []
    assert client.get("/api/v1/health").json()["llm_configured"] is False


@pytest.mark.parametrize("endpoint", ["messages", "message-jobs"])
def test_missing_key_blocks_conversation_before_creating_work(configured, endpoint):
    app, client, calls = configured
    case_id = create_case(client)
    response = client.post(f"/api/v1/cases/{case_id}/{endpoint}", json={"message": QUESTION})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "KEY_REQUIRED"
    assert calls == []
    assert not app.state.message_jobs._records
    assert client.get(f"/api/v1/cases/{case_id}").json()["messages"] == []


@pytest.mark.parametrize("key", ["", "Bearer " + KEY_A, "sk-or-v1-" + "A" * 64,
                                "sk-or-v1-" + "a" * 63, KEY_A + " ", "sk-proj-" + "a" * 64,
                                KEY_A + "," + KEY_B])
def test_invalid_key_is_rejected_without_echo(configured, key):
    _, client, calls = configured
    response = client.get("/api/v1/health", headers={"X-OpenRouter-Key": key})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "KEY_INVALID"
    if key:
        assert key not in response.text
    assert KEY_A not in response.text and KEY_B not in response.text
    assert calls == []


def test_duplicate_headers_are_not_collapsed_or_accepted(configured):
    _, client, calls = configured
    response = client.get("/api/v1/health", headers=[("X-OpenRouter-Key", KEY_A), ("x-openrouter-key", KEY_B)])
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "KEY_INVALID"
    assert KEY_A not in response.text and KEY_B not in response.text
    assert calls == []


@pytest.mark.parametrize("endpoint", ["messages", "message-jobs"])
def test_runtime_key_reaches_real_adapter_without_persistence_or_environment_changes(configured, endpoint):
    app, client, calls = configured
    case_id = create_case(client)
    before = dict(os.environ)
    response = client.post(f"/api/v1/cases/{case_id}/{endpoint}", json={"message": QUESTION}, headers={"X-OpenRouter-Key": KEY_A})
    assert response.status_code == (200 if endpoint == "messages" else 202), response.text
    result = response.json() if endpoint == "messages" else finished(client, case_id, response.json()["id"])["result"]
    assert result["response"]["provider"] == "openai_compatible"
    assert result["response"]["is_simulated"] is False
    assert calls[0]["authorization"] == "Bearer " + KEY_A
    assert calls[0]["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert calls[0]["body"]["model"] == "deepseek/deepseek-v4.1-flash-1017"
    assert calls[0]["body"]["provider"] == {"max_price": {"prompt": 0.3, "completion": 1.2, "request": 0, "image": 0},
                                            "require_parameters": True, "allow_fallbacks": False, "only": ["deepseek"]}
    assert set(os.environ) == set(before)
    assert not [name for name, value in before.items() if os.environ.get(name) != value]
    for key in (KEY_A, KEY_B, SERVER_KEY):
        assert key not in json.dumps(calls[0]["body"])
        assert key not in json.dumps(result)
        with sqlite3.connect(app.state.store.path) as connection:
            assert key not in connection.execute("SELECT payload FROM cases").fetchone()[0]
    assert all(job.task is None for job in app.state.message_jobs._records.values())
    assert client.get("/api/v1/health", headers={"X-OpenRouter-Key": KEY_A}).json()["llm_verified"] is False
    assert adapter._verified_metadata is None and adapter._verification_fingerprint is None


def test_parallel_keys_do_not_cross_requests_or_background_jobs(configured, monkeypatch):
    _, client, calls = configured
    first, second = create_case(client), create_case(client)
    original = httpx.AsyncHTTPTransport.handle_async_request
    both_started = threading.Event()
    seen = []

    async def concurrent(self, request):
        seen.append(request.headers["authorization"])
        if len(seen) == 2:
            both_started.set()
        while not both_started.is_set():
            await asyncio.sleep(0.002)
        return await original(self, request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", concurrent)
    before = dict(os.environ)
    with ThreadPoolExecutor(max_workers=2) as pool:
        sync = pool.submit(client.post, f"/api/v1/cases/{first}/messages", json={"message": QUESTION}, headers={"X-OpenRouter-Key": KEY_A})
        background = pool.submit(client.post, f"/api/v1/cases/{second}/message-jobs", json={"message": QUESTION}, headers={"X-OpenRouter-Key": KEY_B})
        accepted = background.result(timeout=3)
        assert accepted.status_code == 202
        assert sync.result(timeout=3).status_code == 200
    assert finished(client, second, accepted.json()["id"])["status"] == "succeeded"
    assert sorted(call["authorization"] for call in calls) == sorted(["Bearer " + KEY_A, "Bearer " + KEY_B])
    assert set(os.environ) == set(before)
    assert not [name for name, value in before.items() if os.environ.get(name) != value]


def test_public_library_rules_and_case_crud_work_without_key(configured):
    import fitz

    _, client, calls = configured
    for path in ("claim-types", "library", "faq", "sources/cardif-claims"):
        assert client.get("/api/v1/" + path).status_code == 200
    case_id = create_case(client)
    assert client.get(f"/api/v1/cases/{case_id}/checklist").status_code == 200
    assert client.patch(f"/api/v1/cases/{case_id}", json={"conditions": {"surgery": "no"}}).status_code == 200
    with fitz.open() as document:
        document.new_page().insert_text((40, 40), "Synthetic insurance claim application. Name: Demo. Policy: TEST123")
        data = document.tobytes()
    response = client.post(f"/api/v1/cases/{case_id}/documents/application/analyze",
        files={"file": ("synthetic.pdf", data, "application/pdf")})
    assert response.status_code == 200, response.text
    analyzed = next(item for item in response.json()["documents"] if item["id"] == "application")["analysis"]
    assert analyzed["is_simulated"] is False and analyzed["provider"] != "mock"
    assert client.delete(f"/api/v1/cases/{case_id}").status_code == 200
    assert calls == []


def test_default_mode_preserves_environment_provider(configured, monkeypatch):
    _, client, calls = configured
    monkeypatch.delenv("RUNTIME_LLM_KEYS")
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_MODEL", "deepseek/deepseek-v4.1-flash-1017")
    monkeypatch.setenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "300")
    case_id = create_case(client)
    response = client.post(f"/api/v1/cases/{case_id}/messages", json={"message": QUESTION}, headers={"X-OpenRouter-Key": KEY_A})
    assert response.status_code == 200, response.text
    assert calls[0]["authorization"] == "Bearer " + SERVER_KEY
    assert client.get("/api/v1/health").json()["llm_verified"] is True


def test_runtime_health_and_success_preserve_existing_server_verification(configured, monkeypatch):
    _, client, _ = configured
    monkeypatch.setenv("RUNTIME_LLM_KEYS", "false")
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_MODEL", "deepseek/deepseek-v4.1-flash-1017")
    monkeypatch.setenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    case_id = create_case(client)
    assert client.post(f"/api/v1/cases/{case_id}/messages", json={"message": QUESTION}).status_code == 200
    original = (adapter._verification_fingerprint, adapter._verification_epoch, adapter._verified_metadata)
    assert original[2] is not None
    monkeypatch.setenv("RUNTIME_LLM_KEYS", "true")
    for headers in ({}, {"X-OpenRouter-Key": KEY_A}, {"X-OpenRouter-Key": KEY_B}):
        assert client.get("/api/v1/health", headers=headers).json()["llm_verified"] is False
    assert client.post(f"/api/v1/cases/{case_id}/messages", json={"message": QUESTION}, headers={"X-OpenRouter-Key": KEY_A}).status_code == 200
    assert (adapter._verification_fingerprint, adapter._verification_epoch, adapter._verified_metadata) == original
    monkeypatch.setenv("RUNTIME_LLM_KEYS", "false")
    assert client.get("/api/v1/health").json()["llm_verified"] is True


@pytest.mark.parametrize("failure", [False, True])
def test_finished_job_and_callback_contexts_release_runtime_settings(configured, monkeypatch, failure):
    from backend.app import runtime_keys

    app, client, _ = configured
    observations = []
    original = app.state.message_jobs._finish

    def finish(job_id, task):
        observations.append((runtime_keys.current_runtime_settings(), task.get_context().get(runtime_keys._settings)))
        original(job_id, task)

    monkeypatch.setattr(app.state.message_jobs, "_finish", finish)
    if failure:
        async def fail(self, request):
            return httpx.Response(429, request=request)
        monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", fail)
    case_id = create_case(client)
    response = client.post(f"/api/v1/cases/{case_id}/message-jobs", json={"message": QUESTION}, headers={"X-OpenRouter-Key": KEY_A})
    assert response.status_code == 202
    result = finished(client, case_id, response.json()["id"])
    assert result["status"] == ("failed" if failure else "succeeded")
    assert observations and all(current is None and task_settings is None for current, task_settings in observations)
    assert all(job.task is None for job in app.state.message_jobs._records.values())
    assert runtime_keys.current_runtime_settings() is None
    assert KEY_A not in json.dumps(result)


def test_delete_case_cancels_runtime_call_and_releases_key_context(configured, monkeypatch):
    from backend.app import runtime_keys

    app, client, _ = configured
    started, cancelled = threading.Event(), threading.Event()
    cleared = []
    original_finish = app.state.message_jobs._finish

    async def pending(self, request):
        assert request.headers["authorization"] == "Bearer " + KEY_A
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    def finish(job_id, task):
        cleared.append(task.get_context().get(runtime_keys._settings))
        original_finish(job_id, task)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", pending)
    monkeypatch.setattr(app.state.message_jobs, "_finish", finish)
    case_id = create_case(client)
    response = client.post(f"/api/v1/cases/{case_id}/message-jobs", json={"message": QUESTION}, headers={"X-OpenRouter-Key": KEY_A})
    assert response.status_code == 202
    assert started.wait(1)
    assert client.delete(f"/api/v1/cases/{case_id}").status_code == 200
    assert cancelled.wait(1)
    assert cleared and all(value is None for value in cleared)
    assert not app.state.message_jobs._records and not app.state.message_jobs._tasks
    assert client.get(f"/api/v1/cases/{case_id}").status_code == 404
    with sqlite3.connect(app.state.store.path) as connection:
        assert connection.execute("SELECT count(*) FROM cases").fetchone()[0] == 0


def test_allowed_origin_can_preflight_runtime_key_header(configured):
    _, client, calls = configured
    response = client.options("/api/v1/health", headers={"Origin": "http://127.0.0.1:8000",
        "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "X-OpenRouter-Key"})
    assert response.status_code == 200
    assert "x-openrouter-key" in response.headers["access-control-allow-headers"].lower()
    assert calls == []
