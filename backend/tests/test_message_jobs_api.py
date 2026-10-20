"""離線控制 provider 等待；驗證背景工作真正的 API 與持久化邊界。"""
import asyncio
import copy
from concurrent.futures import ThreadPoolExecutor
import threading
import time
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from backend.app.errors import ApiError
from backend.app.main import create_app


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("CASE_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "1000")
    monkeypatch.setenv("LLM_PROVIDER", "grounded_rules")
    return create_app()


@pytest.fixture
def client(app):
    with TestClient(app) as result:
        yield result


def create_case(client):
    response = client.post("/api/v1/cases", json={"entry_path": "guided"})
    assert response.status_code == 201
    return response.json()["id"]


def submit(client, case_id, **updates):
    response = client.post(f"/api/v1/cases/{case_id}/message-jobs", json={"message": "我住院三天，沒有手術", **updates})
    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload == {"id": payload["id"], "status": "pending"}
    assert UUID(payload["id"]).version == 4
    return payload["id"]


def finished(client, case_id, job_id):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/cases/{case_id}/message-jobs/{job_id}")
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload["status"] != "pending":
            return payload
        time.sleep(0.005)
    pytest.fail("Background job did not finish after controlled provider release")


@pytest.fixture
def slow_provider(monkeypatch):
    from backend.app.ai import conversation

    original = conversation.respond
    started = threading.Event()
    release = threading.Event()
    cancelled = threading.Event()
    calls = []

    async def controlled_reply(case, message, document_id=None):
        calls.append(case["id"])
        started.set()
        try:
            while not release.is_set():
                await asyncio.sleep(0.005)
            return await original(case, message, document_id)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    monkeypatch.setattr(conversation, "respond", controlled_reply)
    yield {"started": started, "release": release, "cancelled": cancelled, "calls": calls}
    release.set()


def test_job_returns_pending_without_waiting_and_persists_exactly_once(app, client, slow_provider, monkeypatch):
    case_id = create_case(client)
    writes = []
    original_save = app.state.store.save

    def save(item, owner):
        writes.append(item["id"])
        return original_save(item, owner)

    monkeypatch.setattr(app.state.store, "save", save)
    job_id = submit(client, case_id)
    assert slow_provider["started"].wait(1)
    pending = client.get(f"/api/v1/cases/{case_id}/message-jobs/{job_id}")
    assert pending.json() == {"id": job_id, "status": "pending"}
    assert client.get(f"/api/v1/cases/{case_id}").json()["messages"] == []
    slow_provider["release"].set()
    completed = finished(client, case_id, job_id)
    assert completed["status"] == "succeeded"
    assert set(completed) == {"id", "status", "result"}
    assert completed["result"]["case"]["id"] == case_id
    assert completed["result"]["response"]["provider"] == "grounded_rules"
    assert completed["result"]["response"]["is_simulated"] is False
    assert len(completed["result"]["case"]["messages"]) == 2
    for _ in range(3):
        assert client.get(f"/api/v1/cases/{case_id}/message-jobs/{job_id}").json() == completed
    assert writes == [case_id]
    assert slow_provider["calls"] == [case_id]


def test_active_job_rejects_duplicate_and_synchronous_paid_attempts(client, slow_provider):
    case_id = create_case(client)
    job_id = submit(client, case_id)
    assert slow_provider["started"].wait(1)
    for endpoint in ("message-jobs", "messages"):
        response = client.post(f"/api/v1/cases/{case_id}/{endpoint}", json={"message": "再次送出"})
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "MESSAGE_JOB_ACTIVE"
    assert slow_provider["calls"] == [case_id]
    slow_provider["release"].set()
    assert finished(client, case_id, job_id)["status"] == "succeeded"
    second_id = submit(client, case_id)
    assert second_id != job_id
    assert finished(client, case_id, second_id)["status"] == "succeeded"
    assert len(client.get(f"/api/v1/cases/{case_id}").json()["messages"]) == 4


def test_sync_endpoint_cannot_bypass_global_background_capacity(app, client, monkeypatch):
    from backend.app.ai import conversation

    original = conversation.respond
    first_case_id = create_case(client)
    second_case_id = create_case(client)
    release = threading.Event()
    calls = []
    app.state.message_jobs.max_active = 1

    async def controlled_reply(case, *args):
        calls.append(case["id"])
        if case["id"] == first_case_id:
            while not release.is_set():
                await asyncio.sleep(0.005)
        return await original(case, *args)

    monkeypatch.setattr(conversation, "respond", controlled_reply)
    try:
        first_job = submit(client, first_case_id)
        for endpoint in ("messages", "message-jobs"):
            response = client.post(f"/api/v1/cases/{second_case_id}/{endpoint}", json={"message": "我住院了"})
            assert response.status_code == 429
            assert response.json()["error"]["code"] == "MESSAGE_JOB_LIMIT"
        assert calls == [first_case_id]
    finally:
        release.set()
    assert finished(client, first_case_id, first_job)["status"] == "succeeded"
    assert client.post(f"/api/v1/cases/{second_case_id}/messages", json={"message": "我住院了"}).status_code == 200


def test_active_synchronous_message_reserves_same_job_and_global_limits(app, client, slow_provider):
    case_id = create_case(client)
    other_case_id = create_case(client)
    app.state.message_jobs.max_active = 1
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(client.post, f"/api/v1/cases/{case_id}/messages", json={"message": "我住院了"})
        try:
            assert slow_provider["started"].wait(1)
            duplicate = client.post(f"/api/v1/cases/{case_id}/message-jobs", json={"message": "再次送出"})
            assert duplicate.status_code == 409
            assert duplicate.json()["error"]["code"] == "MESSAGE_JOB_ACTIVE"
            over_capacity = client.post(f"/api/v1/cases/{other_case_id}/message-jobs", json={"message": "另一案件"})
            assert over_capacity.status_code == 429
            assert over_capacity.json()["error"]["code"] == "MESSAGE_JOB_LIMIT"
            assert slow_provider["calls"] == [case_id]
        finally:
            slow_provider["release"].set()
        assert future.result(timeout=3).status_code == 200


def test_jobs_are_owner_and_case_isolated(app, client, slow_provider):
    case_id = create_case(client)
    other_case_id = create_case(client)
    job_id = submit(client, case_id)
    # 第二個 HTTP client 共用既有 server lifespan，不重啟整個 app。
    other = TestClient(app)
    try:
        response = other.get(f"/api/v1/cases/{case_id}/message-jobs/{job_id}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "CASE_NOT_FOUND"
    finally:
        other.close()
    response = client.get(f"/api/v1/cases/{other_case_id}/message-jobs/{job_id}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "MESSAGE_JOB_NOT_FOUND"
    slow_provider["release"].set()


@pytest.mark.parametrize("provider_error,code", [(ApiError("LLM_RATE_LIMITED", "服務目前忙碌。", 503), "LLM_RATE_LIMITED"), (RuntimeError("SENSITIVE_PRIVATE_PROMPT"), "PROVIDER_UNAVAILABLE")])
def test_failed_job_returns_safe_original_error_without_persisting(client, monkeypatch, caplog, provider_error, code):
    from backend.app.ai import conversation

    async def fail(*args):
        raise provider_error

    monkeypatch.setattr(conversation, "respond", fail)
    case_id = create_case(client)
    job_id = submit(client, case_id)
    result = finished(client, case_id, job_id)
    assert result["status"] == "failed"
    assert set(result) == {"id", "status", "error"}
    assert result["error"]["code"] == code
    assert result["error"]["status"] == 503
    assert "SENSITIVE_PRIVATE_PROMPT" not in repr(result) + caplog.text
    assert client.get(f"/api/v1/cases/{case_id}").json()["messages"] == []


@pytest.mark.parametrize("endpoint", ["messages", "message-jobs"])
@pytest.mark.parametrize("invalid", ["simulated", "source"])
def test_sync_and_jobs_share_response_and_source_validation(client, monkeypatch, endpoint, invalid):
    from backend.app.ai import conversation

    original = conversation.respond

    async def invalid_response(*args):
        response = copy.deepcopy(await original(*args))
        if invalid == "simulated":
            response["is_simulated"] = True
        else:
            response["source_references"][0]["official_url"] = "https://life.cardif.com.tw/invented"
        return response

    monkeypatch.setattr(conversation, "respond", invalid_response)
    case_id = create_case(client)
    response = client.post(f"/api/v1/cases/{case_id}/{endpoint}", json={"message": "我住院了"})
    if endpoint == "messages":
        assert response.status_code == 503
        error = response.json()["error"]
    else:
        assert response.status_code == 202
        result = finished(client, case_id, response.json()["id"])
        assert result["status"] == "failed"
        error = result["error"]
    assert error["code"] == "INVALID_PROVIDER_RESPONSE"
    assert client.get(f"/api/v1/cases/{case_id}").json()["messages"] == []


def test_case_deletion_cancels_pending_job_and_cannot_resurrect_case(client, slow_provider):
    case_id = create_case(client)
    job_id = submit(client, case_id)
    assert slow_provider["started"].wait(1)
    response = client.delete(f"/api/v1/cases/{case_id}")
    assert response.status_code == 200
    assert slow_provider["cancelled"].wait(1)
    slow_provider["release"].set()
    assert client.get(f"/api/v1/cases/{case_id}").status_code == 404
    assert client.get(f"/api/v1/cases/{case_id}/message-jobs/{job_id}").status_code == 404


def test_pending_job_merges_result_into_latest_case_without_reverting_edits(client, slow_provider):
    case_id = create_case(client)
    assert client.patch(f"/api/v1/cases/{case_id}", json={"claim_type_id": "inpatient"}).status_code == 200
    job_id = submit(client, case_id)
    changed = client.patch(f"/api/v1/cases/{case_id}/documents/application", json={"status": "uploaded"})
    assert changed.status_code == 200
    slow_provider["release"].set()
    completed = finished(client, case_id, job_id)
    assert completed["status"] == "succeeded"
    assert completed["result"]["case"]["documents"][0]["status"] == "uploaded"
    assert completed["result"]["case"]["claim_type_id"] == "inpatient"


@pytest.mark.parametrize("updates", [{"claim_type_id": "outpatient"}, {"conditions": {"surgery": "yes"}}, {"conditions": {"payment_method": "other"}}])
def test_changed_claim_context_rejects_stale_model_reply_without_overwriting_case(client, slow_provider, updates):
    case_id = create_case(client)
    job_id = submit(client, case_id)
    assert client.patch(f"/api/v1/cases/{case_id}", json=updates).status_code == 200
    slow_provider["release"].set()
    completed = finished(client, case_id, job_id)
    assert completed["status"] == "failed"
    assert completed["error"]["code"] == "MESSAGE_CASE_CHANGED"
    assert completed["error"]["status"] == 409
    latest = client.get(f"/api/v1/cases/{case_id}").json()
    assert latest["messages"] == []
    if "claim_type_id" in updates:
        assert latest["claim_type_id"] == updates["claim_type_id"]
    else:
        for field, value in updates["conditions"].items():
            assert latest["conditions"][field] == value


@pytest.mark.parametrize("endpoint", ["messages", "message-jobs"])
def test_conversation_budget_accepts_virtual_180_second_provider_past_old_limit(client, monkeypatch, endpoint):
    from backend.app import main
    from backend.app.ai import conversation

    original_respond = conversation.respond
    original_wait_for = asyncio.wait_for
    budgets = []

    async def virtual_slow_reply(*args):
        return await original_respond(*args)

    async def virtual_wait_for(awaitable, timeout):
        if getattr(getattr(awaitable, "cr_code", None), "co_name", "") == "virtual_slow_reply":
            budgets.append(timeout)
            # Virtual provider latency is 180 seconds; no real model or wall-clock wait.
            if timeout < 180:
                awaitable.close()
                raise TimeoutError
        return await original_wait_for(awaitable, timeout)

    monkeypatch.setattr(conversation, "respond", virtual_slow_reply)
    monkeypatch.setattr(main.asyncio, "wait_for", virtual_wait_for)
    case_id = create_case(client)
    response = client.post(f"/api/v1/cases/{case_id}/{endpoint}", json={"message": "我住院了"})
    if endpoint == "messages":
        assert response.status_code == 200
        result = response.json()
    else:
        assert response.status_code == 202
        job = finished(client, case_id, response.json()["id"])
        assert job["status"] == "succeeded"
        result = job["result"]
    assert budgets == [310]
    assert len(result["case"]["messages"]) == 2


@pytest.mark.parametrize("endpoint", ["messages", "message-jobs"])
def test_total_conversation_deadline_is_bounded_without_persisting_partial_result(client, monkeypatch, endpoint):
    from backend.app import main

    original_wait_for = asyncio.wait_for
    budgets = []

    async def exhausted_total_budget(awaitable, timeout):
        if getattr(getattr(awaitable, "cr_code", None), "co_name", "") == "complete_message":
            budgets.append(timeout)
            awaitable.close()
            raise TimeoutError
        return await original_wait_for(awaitable, timeout)

    monkeypatch.setattr(main.asyncio, "wait_for", exhausted_total_budget)
    case_id = create_case(client)
    response = client.post(f"/api/v1/cases/{case_id}/{endpoint}", json={"message": "我住院了"})
    if endpoint == "messages":
        assert response.status_code == 503
        error = response.json()["error"]
    else:
        assert response.status_code == 202
        result = finished(client, case_id, response.json()["id"])
        assert result["status"] == "failed"
        error = result["error"]
    assert error["code"] == "PROVIDER_UNAVAILABLE"
    assert budgets == [310]
    assert client.get(f"/api/v1/cases/{case_id}").json()["messages"] == []


def test_shutdown_cancels_background_provider(app, slow_provider):
    with TestClient(app) as client:
        case_id = create_case(client)
        submit(client, case_id)
        assert slow_provider["started"].wait(1)
    assert slow_provider["cancelled"].wait(1)


def test_job_submission_uses_existing_message_and_document_validation(client):
    case_id = create_case(client)
    response = client.post(f"/api/v1/cases/{case_id}/message-jobs", json={"message": " "})
    assert response.status_code == 422
    response = client.post(f"/api/v1/cases/{case_id}/message-jobs", json={"message": "問題", "document_id": "invented"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"
