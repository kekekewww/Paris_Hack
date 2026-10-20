"""Deterministic in-memory conversation job lifecycle tests; no model calls."""

import asyncio
import gc
import importlib
import weakref
from uuid import UUID

import pytest

from backend.app.errors import ApiError


def manager_module():
    try:
        return importlib.import_module("backend.app.message_jobs")
    except ImportError as error:
        pytest.fail(f"MessageJobManager is not implemented: {error}")


def run(scenario):
    asyncio.run(scenario())


def assert_missing(manager, case_id, owner, job_id):
    with pytest.raises(ApiError) as caught:
        manager.get(case_id, owner, job_id)
    assert caught.value.code == "MESSAGE_JOB_NOT_FOUND"
    assert caught.value.status == 404


def test_submit_returns_pending_immediately_and_runs_operation_once():
    async def scenario():
        manager = manager_module().MessageJobManager()
        release = asyncio.Event()
        entered = asyncio.Event()
        calls = 0

        async def operation():
            nonlocal calls
            calls += 1
            entered.set()
            await release.wait()
            return {"response": {"message": "合成測試回覆"}}

        submitted = manager.submit("case-a", "owner-a", operation)
        assert submitted["status"] == "pending"
        assert UUID(submitted["id"]).version == 4
        assert calls == 0
        assert manager.get("case-a", "owner-a", submitted["id"]) == submitted
        assert manager.has_active("case-a", "owner-a") is True
        await entered.wait()
        release.set()
        await asyncio.sleep(0)
        assert manager.get("case-a", "owner-a", submitted["id"]) == {
            "id": submitted["id"], "status": "succeeded",
            "result": {"response": {"message": "合成測試回覆"}},
        }
        assert manager.has_active("case-a", "owner-a") is False
        assert calls == 1
        await manager.shutdown()

    run(scenario)


def test_success_result_and_returned_snapshot_do_not_share_mutable_data():
    async def scenario():
        manager = manager_module().MessageJobManager()
        result = {"nested": {"value": "original"}}

        async def operation():
            return result

        submitted = manager.submit("case-a", "owner-a", operation)
        await asyncio.sleep(0)
        snapshot = manager.get("case-a", "owner-a", submitted["id"])
        result["nested"]["value"] = "operation-mutated"
        snapshot["result"]["nested"]["value"] = "client-mutated"
        assert manager.get("case-a", "owner-a", submitted["id"])["result"] == {"nested": {"value": "original"}}
        await manager.shutdown()

    run(scenario)


def test_api_error_keeps_public_error_envelope():
    async def scenario():
        manager = manager_module().MessageJobManager()

        async def operation():
            raise ApiError("LLM_RATE_LIMITED", "免費服務目前忙碌，請稍後重試。", 429)

        submitted = manager.submit("case-a", "owner-a", operation)
        await asyncio.sleep(0)
        assert manager.get("case-a", "owner-a", submitted["id"]) == {
            "id": submitted["id"], "status": "failed",
            "error": {"code": "LLM_RATE_LIMITED", "message": "免費服務目前忙碌，請稍後重試。", "status": 429},
        }
        await manager.shutdown()

    run(scenario)


def test_unknown_error_returns_generic_503_without_leaking_details(caplog, capsys):
    async def scenario():
        manager = manager_module().MessageJobManager()

        async def operation():
            raise RuntimeError("SYNTHETIC-PRIVATE-PROMPT-AND-COOKIE")

        submitted = manager.submit("case-a", "synthetic-cookie", operation)
        await asyncio.sleep(0)
        response = manager.get("case-a", "synthetic-cookie", submitted["id"])
        assert response["status"] == "failed"
        assert response["error"]["status"] == 503
        assert "SYNTHETIC-PRIVATE" not in str(response)
        await manager.shutdown()

    run(scenario)
    assert "SYNTHETIC-PRIVATE" not in caplog.text
    captured = capsys.readouterr()
    assert "SYNTHETIC-PRIVATE" not in captured.out + captured.err


def test_operation_cancellation_produces_failed_job():
    async def scenario():
        manager = manager_module().MessageJobManager()

        async def operation():
            raise asyncio.CancelledError()

        submitted = manager.submit("case-a", "owner-a", operation)
        await asyncio.sleep(0)
        response = manager.get("case-a", "owner-a", submitted["id"])
        assert response["status"] == "failed"
        assert response["error"]["code"] == "MESSAGE_JOB_CANCELLED"
        assert response["error"]["status"] == 409
        await manager.shutdown()

    run(scenario)


def test_non_dictionary_result_is_a_generic_failure():
    async def scenario():
        manager = manager_module().MessageJobManager()

        async def operation():
            return "not-the-result-contract"

        submitted = manager.submit("case-a", "owner-a", operation)
        await asyncio.sleep(0)
        response = manager.get("case-a", "owner-a", submitted["id"])
        assert response["status"] == "failed"
        assert response["error"]["status"] == 503
        assert "not-the-result-contract" not in str(response)
        await manager.shutdown()

    run(scenario)


def test_jobs_are_isolated_by_owner_and_case():
    async def scenario():
        manager = manager_module().MessageJobManager()
        release = asyncio.Event()

        async def operation():
            await release.wait()
            return {}

        submitted = manager.submit("case-a", "owner-a", operation)
        assert_missing(manager, "case-a", "owner-b", submitted["id"])
        assert_missing(manager, "case-b", "owner-a", submitted["id"])
        assert_missing(manager, "case-a", "owner-a", "unknown-job")
        assert manager.has_active("case-a", "owner-b") is False
        assert manager.has_active("case-b", "owner-a") is False
        await manager.cancel_case("case-a", "owner-b")
        assert manager.has_active("case-a", "owner-a") is True
        await manager.shutdown()

    run(scenario)


def test_same_case_rejects_duplicate_active_job_then_accepts_after_completion():
    async def scenario():
        manager = manager_module().MessageJobManager()
        release = asyncio.Event()

        async def operation():
            await release.wait()
            return {}

        first = manager.submit("case-a", "owner-a", operation)
        with pytest.raises(ApiError) as caught:
            manager.submit("case-a", "owner-a", operation)
        assert caught.value.code == "MESSAGE_JOB_ACTIVE"
        assert caught.value.status == 409
        release.set()
        await asyncio.sleep(0)
        assert manager.get("case-a", "owner-a", first["id"])["status"] == "succeeded"
        second = manager.submit("case-a", "owner-a", operation)
        assert second["id"] != first["id"]
        await manager.shutdown()

    run(scenario)


def test_global_active_limit_rejects_unrelated_cases():
    async def scenario():
        manager = manager_module().MessageJobManager(max_active=2)
        release = asyncio.Event()

        async def operation():
            await release.wait()
            return {}

        manager.submit("case-a", "owner-a", operation)
        manager.submit("case-b", "owner-b", operation)
        with pytest.raises(ApiError) as caught:
            manager.submit("case-c", "owner-c", operation)
        assert caught.value.code == "MESSAGE_JOB_LIMIT"
        assert caught.value.status == 429
        await manager.shutdown()

    run(scenario)


def test_retained_limit_evicts_oldest_finished_job_before_active_job(monkeypatch):
    async def scenario():
        module = manager_module()
        now = 1000.0
        monkeypatch.setattr(module.time, "monotonic", lambda: now)
        manager = module.MessageJobManager(max_active=3, max_retained=2)
        release = asyncio.Event()

        async def complete():
            return {"done": True}

        async def pending():
            await release.wait()
            return {}

        first = manager.submit("case-a", "owner-a", complete)
        await asyncio.sleep(0)
        manager.get("case-a", "owner-a", first["id"])
        now += 1
        active = manager.submit("case-b", "owner-b", pending)
        now += 1
        third = manager.submit("case-c", "owner-c", complete)
        assert_missing(manager, "case-a", "owner-a", first["id"])
        assert manager.get("case-b", "owner-b", active["id"])["status"] == "pending"
        assert manager.get("case-c", "owner-c", third["id"])["status"] == "pending"
        await manager.shutdown()

    run(scenario)


def test_retained_limit_cannot_evict_active_work():
    async def scenario():
        manager = manager_module().MessageJobManager(max_active=5, max_retained=1)
        release = asyncio.Event()

        async def operation():
            await release.wait()
            return {}

        first = manager.submit("case-a", "owner-a", operation)
        with pytest.raises(ApiError) as caught:
            manager.submit("case-b", "owner-b", operation)
        assert caught.value.code == "MESSAGE_JOB_LIMIT"
        assert caught.value.status == 429
        assert manager.get("case-a", "owner-a", first["id"])["status"] == "pending"
        await manager.shutdown()

    run(scenario)


def test_finished_ttl_starts_when_operation_finishes(monkeypatch):
    async def scenario():
        module = manager_module()
        now = 1000.0
        monkeypatch.setattr(module.time, "monotonic", lambda: now)
        manager = module.MessageJobManager(ttl_seconds=900)
        release = asyncio.Event()

        async def operation():
            await release.wait()
            return {}

        submitted = manager.submit("case-a", "owner-a", operation)
        await asyncio.sleep(0)
        now += 800
        release.set()
        await asyncio.sleep(0)
        assert manager.get("case-a", "owner-a", submitted["id"])["status"] == "succeeded"
        now += 899
        assert manager.get("case-a", "owner-a", submitted["id"])["status"] == "succeeded"
        now += 1
        manager.cleanup()
        assert_missing(manager, "case-a", "owner-a", submitted["id"])
        await manager.shutdown()

    run(scenario)


def test_pending_ttl_cancels_and_drops_expired_job(monkeypatch):
    async def scenario():
        module = manager_module()
        now = 1000.0
        monkeypatch.setattr(module.time, "monotonic", lambda: now)
        manager = module.MessageJobManager(ttl_seconds=10)
        entered = asyncio.Event()
        cancelled = asyncio.Event()

        async def operation():
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        submitted = manager.submit("case-a", "owner-a", operation)
        await entered.wait()
        now += 10
        manager.cleanup()
        assert_missing(manager, "case-a", "owner-a", submitted["id"])
        await cancelled.wait()
        await manager.shutdown()

    run(scenario)


def test_cancel_case_waits_for_cleanup_removes_results_and_prevents_resurrection():
    async def scenario():
        manager = manager_module().MessageJobManager()
        entered = asyncio.Event()
        cancelling = asyncio.Event()
        release_cleanup = asyncio.Event()

        async def operation():
            entered.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelling.set()
                await release_cleanup.wait()
                return {"late": "must-not-return"}

        submitted = manager.submit("case-a", "owner-a", operation)
        await entered.wait()
        cancel = asyncio.create_task(manager.cancel_case("case-a", "owner-a"))
        await cancelling.wait()
        assert cancel.done() is False
        assert_missing(manager, "case-a", "owner-a", submitted["id"])
        with pytest.raises(ApiError) as caught:
            manager.submit("case-a", "owner-a", operation)
        assert caught.value.code == "MESSAGE_JOB_ACTIVE"
        release_cleanup.set()
        await cancel
        assert_missing(manager, "case-a", "owner-a", submitted["id"])
        assert manager.has_active("case-a", "owner-a") is False
        await manager.shutdown()

    run(scenario)


def test_cancel_before_task_starts_does_not_call_operation():
    async def scenario():
        manager = manager_module().MessageJobManager()
        calls = 0

        async def operation():
            nonlocal calls
            calls += 1
            return {}

        submitted = manager.submit("case-a", "owner-a", operation)
        await manager.cancel_case("case-a", "owner-a")
        assert calls == 0
        assert_missing(manager, "case-a", "owner-a", submitted["id"])
        await manager.shutdown()

    run(scenario)


def test_cancel_case_removes_old_finished_records_but_keeps_other_cases():
    async def scenario():
        manager = manager_module().MessageJobManager()

        async def complete():
            return {}

        first = manager.submit("case-a", "owner-a", complete)
        unrelated = manager.submit("case-b", "owner-b", complete)
        await asyncio.sleep(0)
        manager.get("case-a", "owner-a", first["id"])
        second = manager.submit("case-a", "owner-a", complete)
        await manager.cancel_case("case-a", "owner-a")
        assert_missing(manager, "case-a", "owner-a", first["id"])
        assert_missing(manager, "case-a", "owner-a", second["id"])
        assert manager.get("case-b", "owner-b", unrelated["id"])["status"] == "succeeded"
        await manager.shutdown()

    run(scenario)


def test_shutdown_cancels_all_tasks_clears_jobs_and_rejects_new_work():
    async def scenario():
        manager = manager_module().MessageJobManager()
        cancelled = []

        async def operation():
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(True)

        first = manager.submit("case-a", "owner-a", operation)
        second = manager.submit("case-b", "owner-b", operation)
        await asyncio.sleep(0)
        await manager.shutdown()
        assert len(cancelled) == 2
        assert_missing(manager, "case-a", "owner-a", first["id"])
        assert_missing(manager, "case-b", "owner-b", second["id"])
        assert manager.has_active("case-a", "owner-a") is False
        with pytest.raises(ApiError) as caught:
            manager.submit("case-c", "owner-c", operation)
        assert caught.value.status == 503
        await manager.shutdown()

    run(scenario)


def test_pending_work_cannot_revive_by_finishing_after_its_ttl(monkeypatch):
    async def scenario():
        module = manager_module()
        now = 1000.0
        monkeypatch.setattr(module.time, "monotonic", lambda: now)
        manager = module.MessageJobManager(ttl_seconds=10)
        release = asyncio.Event()

        async def operation():
            await release.wait()
            return {"late": True}

        submitted = manager.submit("case-a", "owner-a", operation)
        await asyncio.sleep(0)
        now += 11
        release.set()
        await asyncio.sleep(0)
        assert_missing(manager, "case-a", "owner-a", submitted["id"])
        assert manager.has_active("case-a", "owner-a") is False
        await manager.shutdown()

    run(scenario)


def test_expired_task_keeps_active_slot_until_cancellation_really_finishes(monkeypatch):
    async def scenario():
        module = manager_module()
        now = 1000.0
        monkeypatch.setattr(module.time, "monotonic", lambda: now)
        manager = module.MessageJobManager(max_active=1, ttl_seconds=10)
        cancelling = asyncio.Event()
        release_cleanup = asyncio.Event()

        async def operation():
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelling.set()
                await release_cleanup.wait()
                return {"late": True}

        submitted = manager.submit("case-a", "owner-a", operation)
        await asyncio.sleep(0)
        now += 10
        manager.cleanup()
        await cancelling.wait()
        assert_missing(manager, "case-a", "owner-a", submitted["id"])
        assert manager.has_active("case-a", "owner-a") is True
        with pytest.raises(ApiError) as duplicate:
            manager.submit("case-a", "owner-a", operation)
        assert duplicate.value.code == "MESSAGE_JOB_ACTIVE"
        with pytest.raises(ApiError) as global_limit:
            manager.submit("case-b", "owner-b", operation)
        assert global_limit.value.code == "MESSAGE_JOB_LIMIT"
        release_cleanup.set()
        await asyncio.sleep(0)
        assert manager.has_active("case-a", "owner-a") is False
        assert_missing(manager, "case-a", "owner-a", submitted["id"])
        await manager.shutdown()

    run(scenario)


def test_default_active_limit_is_sixteen():
    async def scenario():
        manager = manager_module().MessageJobManager()

        async def pending():
            await asyncio.Event().wait()
            return {}

        for index in range(16):
            assert manager.submit(f"case-{index}", "owner-a", pending)["status"] == "pending"
        with pytest.raises(ApiError) as caught:
            manager.submit("case-seventeen", "owner-a", pending)
        assert caught.value.code == "MESSAGE_JOB_LIMIT"
        assert caught.value.status == 429
        await manager.shutdown()

    run(scenario)


def test_default_retained_limit_evicts_oldest_when_one_hundred_twenty_ninth_arrives():
    async def scenario():
        manager = manager_module().MessageJobManager()
        submitted = []

        async def complete():
            return {}

        for index in range(129):
            job = manager.submit(f"case-{index}", "owner-a", complete)
            submitted.append(job)
            await asyncio.sleep(0)
            assert manager.get(f"case-{index}", "owner-a", job["id"])["status"] == "succeeded"
        assert_missing(manager, "case-0", "owner-a", submitted[0]["id"])
        assert manager.get("case-1", "owner-a", submitted[1]["id"])["status"] == "succeeded"
        assert manager.get("case-128", "owner-a", submitted[128]["id"])["status"] == "succeeded"
        await manager.shutdown()

    run(scenario)


def test_eviction_orders_by_finish_time_when_creation_order_differs(monkeypatch):
    async def scenario():
        module = manager_module()
        now = 1000.0
        monkeypatch.setattr(module.time, "monotonic", lambda: now)
        manager = module.MessageJobManager(max_retained=2)
        release = asyncio.Event()

        async def slow():
            await release.wait()
            return {}

        async def complete():
            return {}

        slow_job = manager.submit("case-slow", "owner-a", slow)
        now += 1
        quick_job = manager.submit("case-quick", "owner-a", complete)
        await asyncio.sleep(0)
        assert manager.get("case-quick", "owner-a", quick_job["id"])["status"] == "succeeded"
        now += 1
        release.set()
        await asyncio.sleep(0)
        assert manager.get("case-slow", "owner-a", slow_job["id"])["status"] == "succeeded"
        manager.submit("case-third", "owner-a", complete)
        assert_missing(manager, "case-quick", "owner-a", quick_job["id"])
        assert manager.get("case-slow", "owner-a", slow_job["id"])["status"] == "succeeded"
        await manager.shutdown()

    run(scenario)


def test_job_metadata_hashes_cookie_and_releases_operation_closure_after_finish():
    class SyntheticInput:
        prompt = "SYNTHETIC-PRIVATE-RAW-PROMPT"

    async def scenario():
        manager = manager_module().MessageJobManager()
        release = asyncio.Event()

        def make_operation(private_input):
            async def operation():
                assert private_input.prompt
                await release.wait()
                return {"public": True}
            return operation

        private_input = SyntheticInput()
        reference = weakref.ref(private_input)
        operation = make_operation(private_input)
        submitted = manager.submit("case-a", "SYNTHETIC-PRIVATE-OWNER-COOKIE", operation)
        del private_input, operation
        assert reference() is not None
        assert "SYNTHETIC-PRIVATE-OWNER-COOKIE" not in repr(vars(manager))
        assert "SYNTHETIC-PRIVATE-RAW-PROMPT" not in repr(vars(manager))
        release.set()
        await asyncio.sleep(0)
        assert manager.get("case-a", "SYNTHETIC-PRIVATE-OWNER-COOKIE", submitted["id"])["status"] == "succeeded"
        await asyncio.sleep(0)
        gc.collect()
        assert reference() is None
        await manager.shutdown()

    run(scenario)


def test_wait_result_returns_independent_results_without_rerunning_operation():
    async def scenario():
        manager = manager_module().MessageJobManager()
        release = asyncio.Event()
        calls = 0

        async def operation():
            nonlocal calls
            calls += 1
            await release.wait()
            return {"response": {"message": "合成測試"}}

        submitted = manager.submit("case-a", "owner-a", operation)
        first = asyncio.create_task(manager.wait_result("case-a", "owner-a", submitted["id"]))
        second = asyncio.create_task(manager.wait_result("case-a", "owner-a", submitted["id"]))
        await asyncio.sleep(0)
        assert first.done() is False
        release.set()
        one, two = await asyncio.gather(first, second)
        one["response"]["message"] = "mutated"
        assert two == {"response": {"message": "合成測試"}}
        assert await manager.wait_result("case-a", "owner-a", submitted["id"]) == two
        assert calls == 1
        await manager.shutdown()

    run(scenario)


@pytest.mark.parametrize("case_id,owner", [("case-a", "wrong-owner"), ("wrong-case", "owner-a")])
def test_wait_result_checks_owner_and_case_before_awaiting(case_id, owner):
    async def scenario():
        manager = manager_module().MessageJobManager()

        async def operation():
            await asyncio.Event().wait()
            return {}

        submitted = manager.submit("case-a", "owner-a", operation)
        with pytest.raises(ApiError) as caught:
            await manager.wait_result(case_id, owner, submitted["id"])
        assert caught.value.code == "MESSAGE_JOB_NOT_FOUND"
        assert caught.value.status == 404
        assert manager.has_active("case-a", "owner-a") is True
        await manager.shutdown()

    run(scenario)


def test_wait_result_raises_original_api_error_for_pending_and_finished_job():
    async def scenario():
        manager = manager_module().MessageJobManager()

        async def operation():
            raise ApiError("LLM_RATE_LIMITED", "免費服務忙碌。", 429)

        submitted = manager.submit("case-a", "owner-a", operation)
        for _ in range(2):
            with pytest.raises(ApiError) as caught:
                await manager.wait_result("case-a", "owner-a", submitted["id"])
            assert caught.value.code == "LLM_RATE_LIMITED"
            assert caught.value.message == "免費服務忙碌。"
            assert caught.value.status == 429
        await manager.shutdown()

    run(scenario)


def test_wait_result_masks_unknown_worker_failure(caplog, capsys):
    async def scenario():
        manager = manager_module().MessageJobManager()

        async def operation():
            raise RuntimeError("SYNTHETIC-PRIVATE-WAIT-FAILURE")

        submitted = manager.submit("case-a", "owner-a", operation)
        with pytest.raises(ApiError) as caught:
            await manager.wait_result("case-a", "owner-a", submitted["id"])
        assert caught.value.code == "MESSAGE_JOB_FAILED"
        assert caught.value.status == 503
        assert "SYNTHETIC-PRIVATE" not in caught.value.message
        await manager.shutdown()

    run(scenario)
    assert "SYNTHETIC-PRIVATE" not in caplog.text
    captured = capsys.readouterr()
    assert "SYNTHETIC-PRIVATE" not in captured.out + captured.err


@pytest.mark.parametrize("action", ["cancel_case", "shutdown"])
def test_wait_result_returns_404_when_case_deletion_or_shutdown_cancels_worker(action):
    async def scenario():
        manager = manager_module().MessageJobManager()
        entered = asyncio.Event()

        async def operation():
            entered.set()
            await asyncio.Event().wait()
            return {}

        submitted = manager.submit("case-a", "owner-a", operation)
        await entered.wait()
        waiter = asyncio.create_task(manager.wait_result("case-a", "owner-a", submitted["id"]))
        await asyncio.sleep(0)
        if action == "cancel_case":
            await manager.cancel_case("case-a", "owner-a")
        else:
            await manager.shutdown()
        with pytest.raises(ApiError) as caught:
            await waiter
        assert caught.value.code == "MESSAGE_JOB_NOT_FOUND"
        assert caught.value.status == 404
        await manager.shutdown()

    run(scenario)


def test_wait_result_propagates_caller_cancellation_and_cancels_worker():
    async def scenario():
        manager = manager_module().MessageJobManager()
        entered = asyncio.Event()
        cancelled = asyncio.Event()

        async def operation():
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        submitted = manager.submit("case-a", "owner-a", operation)
        await entered.wait()
        waiter = asyncio.create_task(manager.wait_result("case-a", "owner-a", submitted["id"]))
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        await cancelled.wait()
        snapshot = manager.get("case-a", "owner-a", submitted["id"])
        assert snapshot["status"] == "failed"
        assert snapshot["error"]["code"] == "MESSAGE_JOB_CANCELLED"
        assert snapshot["error"]["status"] == 409
        assert manager.has_active("case-a", "owner-a") is False
        await manager.shutdown()

    run(scenario)


def test_wait_result_worker_self_cancellation_is_public_409():
    async def scenario():
        manager = manager_module().MessageJobManager()

        async def operation():
            raise asyncio.CancelledError()

        submitted = manager.submit("case-a", "owner-a", operation)
        with pytest.raises(ApiError) as caught:
            await manager.wait_result("case-a", "owner-a", submitted["id"])
        assert caught.value.code == "MESSAGE_JOB_CANCELLED"
        assert caught.value.status == 409
        await manager.shutdown()

    run(scenario)


def test_wait_result_does_not_confuse_old_caller_cancellation_with_worker_cancellation():
    async def scenario():
        manager = manager_module().MessageJobManager()
        caller = asyncio.current_task()
        caller.cancel()
        try:
            await asyncio.sleep(0)
        except asyncio.CancelledError:
            pass
        assert caller.cancelling() > 0

        async def operation():
            raise asyncio.CancelledError()

        submitted = manager.submit("case-a", "owner-a", operation)
        with pytest.raises(ApiError) as caught:
            await manager.wait_result("case-a", "owner-a", submitted["id"])
        assert caught.value.code == "MESSAGE_JOB_CANCELLED"
        assert caught.value.status == 409
        await manager.shutdown()

    run(scenario)


def test_wait_result_keeps_worker_in_shared_active_limit():
    async def scenario():
        manager = manager_module().MessageJobManager(max_active=1)
        release = asyncio.Event()

        async def operation():
            await release.wait()
            return {"done": True}

        submitted = manager.submit("case-a", "owner-a", operation)
        waiter = asyncio.create_task(manager.wait_result("case-a", "owner-a", submitted["id"]))
        await asyncio.sleep(0)
        with pytest.raises(ApiError) as caught:
            manager.submit("case-b", "owner-b", operation)
        assert caught.value.code == "MESSAGE_JOB_LIMIT"
        assert caught.value.status == 429
        release.set()
        assert await waiter == {"done": True}
        assert manager.submit("case-b", "owner-b", operation)["status"] == "pending"
        await manager.shutdown()

    run(scenario)


@pytest.mark.parametrize("options", [
    {"max_active": 0}, {"max_active": -1},
    {"max_retained": 0}, {"max_retained": -1},
    {"ttl_seconds": 0}, {"ttl_seconds": -1},
    {"ttl_seconds": float("nan")}, {"ttl_seconds": float("inf")},
    {"max_active": 1.5}, {"max_retained": 1.5},
])
def test_capacity_and_retention_must_be_positive(options):
    with pytest.raises(ValueError):
        manager_module().MessageJobManager(**options)
