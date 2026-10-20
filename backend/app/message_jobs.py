"""Bounded, short-lived conversation jobs for one application event loop.

Only owner hashes and job metadata are retained alongside terminal API results.
The operation closure lives in its asyncio Task while execution is pending;
request bodies, prompts, owner cookies and exception details are never logged.
"""

import asyncio
from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import hmac
import math
import time
from typing import Any
from uuid import uuid4

from .errors import ApiError


@dataclass
class _Job:
    id: str
    case_id: str
    owner_hash: str
    created_at: float
    status: str = "pending"
    finished_at: float | None = None
    task: asyncio.Task | None = None
    result: dict | None = None
    error: dict | None = None


class MessageJobManager:
    def __init__(self, max_active=16, max_retained=128, ttl_seconds=900):
        if (
            type(max_active) is not int or max_active <= 0
            or type(max_retained) is not int or max_retained <= 0
            or type(ttl_seconds) not in (int, float)
            or not math.isfinite(ttl_seconds) or ttl_seconds <= 0
        ):
            raise ValueError("Job capacities and retention must be positive")
        self.max_active = max_active
        self.max_retained = max_retained
        self.ttl_seconds = ttl_seconds
        self._records: dict[str, _Job] = {}
        # Expired records are not queryable, but their Tasks still occupy an
        # execution slot until cancellation has actually finished.
        self._tasks: dict[str, _Job] = {}
        self._cancelling_cases: set[tuple[str, str]] = set()
        self._closed = False

    @staticmethod
    def _owner_hash(owner: str) -> str:
        return sha256(owner.encode("utf-8")).hexdigest()

    @staticmethod
    def _matches(job: _Job, case_id: str, owner_hash: str) -> bool:
        return job.case_id == case_id and hmac.compare_digest(job.owner_hash, owner_hash)

    @staticmethod
    def _generic_error() -> dict:
        return {
            "code": "MESSAGE_JOB_FAILED",
            "message": "對話工作暫時無法完成，請稍後重試。",
            "status": 503,
        }

    @staticmethod
    def _snapshot(job: _Job) -> dict:
        snapshot: dict[str, Any] = {"id": job.id, "status": job.status}
        if job.status == "succeeded":
            snapshot["result"] = deepcopy(job.result)
        elif job.status == "failed":
            snapshot["error"] = deepcopy(job.error)
        return snapshot

    def _finish(self, job_id: str, task: asyncio.Task) -> None:
        job = self._tasks.get(job_id)
        if job is None or job.task is not task:
            return
        self._tasks.pop(job_id, None)
        job.task = None
        result = None
        error = None
        try:
            result = task.result()
            if not isinstance(result, dict):
                raise TypeError("Conversation job result must be a dictionary")
            result = deepcopy(result)
        except asyncio.CancelledError:
            error = {
                "code": "MESSAGE_JOB_CANCELLED",
                "message": "對話工作已取消，請重新操作。",
                "status": 409,
            }
        except ApiError as failure:
            error = {"code": failure.code, "message": failure.message, "status": failure.status}
        except Exception:
            # Consume the exception without logging its traceback or message.
            error = self._generic_error()

        now = time.monotonic()
        if self._records.get(job_id) is not job:
            return
        if now - job.created_at >= self.ttl_seconds:
            # Work which was already pending past its deadline must not gain
            # a new retention period merely because it eventually completed.
            self._records.pop(job_id, None)
            return
        job.finished_at = now
        if error is not None:
            job.status = "failed"
            job.error = error
        else:
            job.status = "succeeded"
            job.result = result

    def cleanup(self) -> None:
        for job in list(self._tasks.values()):
            if job.task is not None and job.task.done():
                self._finish(job.id, job.task)
        now = time.monotonic()
        for job in list(self._records.values()):
            reference = job.finished_at if job.finished_at is not None else job.created_at
            if now - reference >= self.ttl_seconds:
                self._records.pop(job.id, None)
                if job.task is not None and not job.task.done():
                    job.task.cancel()

    def _has_active(self, case_id: str, owner_hash: str) -> bool:
        if (case_id, owner_hash) in self._cancelling_cases:
            return True
        return any(
            self._matches(job, case_id, owner_hash)
            and job.task is not None and not job.task.done()
            for job in self._tasks.values()
        )

    def has_active(self, case_id: str, owner: str) -> bool:
        self.cleanup()
        return self._has_active(case_id, self._owner_hash(owner))

    def submit(
        self, case_id: str, owner: str, operation: Callable[[], Awaitable[dict]]
    ) -> dict:
        self.cleanup()
        if self._closed:
            raise ApiError("MESSAGE_JOB_UNAVAILABLE", "對話服務正在關閉，請稍後重試。", 503)
        owner_hash = self._owner_hash(owner)
        if self._has_active(case_id, owner_hash):
            raise ApiError("MESSAGE_JOB_ACTIVE", "此案件已有對話正在處理，請稍候。", 409)
        active = sum(job.task is not None and not job.task.done() for job in self._tasks.values())
        if active >= self.max_active:
            raise ApiError("MESSAGE_JOB_LIMIT", "對話服務目前忙碌，請稍後重試。", 429)
        while len(self._records) >= self.max_retained:
            finished = [job for job in self._records.values() if job.finished_at is not None]
            if not finished:
                raise ApiError("MESSAGE_JOB_LIMIT", "對話服務目前忙碌，請稍後重試。", 429)
            oldest = min(finished, key=lambda job: job.finished_at)
            self._records.pop(oldest.id, None)

        # Validate there is a running loop before creating a coroutine so a
        # rejected submit cannot leave an unawaited operation behind.
        asyncio.get_running_loop()
        job = _Job(str(uuid4()), case_id, owner_hash, time.monotonic())

        async def execute() -> dict:
            return await operation()

        task = asyncio.create_task(execute())
        job.task = task
        self._records[job.id] = job
        self._tasks[job.id] = job
        task.add_done_callback(lambda finished, job_id=job.id: self._finish(job_id, finished))
        return self._snapshot(job)

    def get(self, case_id: str, owner: str, job_id: str) -> dict:
        self.cleanup()
        job = self._records.get(job_id)
        if job is None or not self._matches(job, case_id, self._owner_hash(owner)):
            raise ApiError("MESSAGE_JOB_NOT_FOUND", "查無對話工作，或工作已過期。", 404)
        return self._snapshot(job)

    async def wait_result(self, case_id: str, owner: str, job_id: str) -> dict:
        """Wait for an existing job without submitting or rerunning its work."""
        snapshot = self.get(case_id, owner, job_id)
        if snapshot["status"] == "pending":
            task = self._records[job_id].task
            if task is not None:
                try:
                    # Worker cancellation is a completed gather result, while
                    # cancellation of this shield can only come from its caller.
                    # This also consumes worker failures; _finish retains their
                    # public envelope and removes any private exception details.
                    await asyncio.shield(asyncio.gather(task, return_exceptions=True))
                except asyncio.CancelledError:
                    task.cancel()
                    raise
            self.cleanup()
            snapshot = self.get(case_id, owner, job_id)
        if snapshot["status"] == "succeeded":
            return deepcopy(snapshot["result"])
        failure = snapshot["error"]
        raise ApiError(failure["code"], failure["message"], failure["status"])

    async def cancel_case(self, case_id: str, owner: str) -> None:
        self.cleanup()
        owner_hash = self._owner_hash(owner)
        key = (case_id, owner_hash)
        self._cancelling_cases.add(key)
        try:
            for job in list(self._records.values()):
                if self._matches(job, case_id, owner_hash):
                    self._records.pop(job.id, None)
            tasks = [
                job.task for job in self._tasks.values()
                if self._matches(job, case_id, owner_hash) and job.task is not None
            ]
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            self.cleanup()
        finally:
            self._cancelling_cases.discard(key)

    async def shutdown(self) -> None:
        self._closed = True
        self._records.clear()
        tasks = [job.task for job in self._tasks.values() if job.task is not None]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.cleanup()
        self._tasks.clear()
        self._cancelling_cases.clear()
