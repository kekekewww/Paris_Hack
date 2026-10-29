"""Optional, request-scoped demo credentials; never persist or log their value."""
from contextlib import contextmanager
from contextvars import ContextVar
import os
import re

from .errors import ApiError


_settings = ContextVar("runtime_llm_settings", default=None)
_KEY = re.compile(rb"sk-or-v1-[a-f0-9]{64}")
_MESSAGE_PATH = re.compile(r"/api/v1/cases/[^/]+/(?:messages|message-jobs)")


def runtime_llm_keys_enabled() -> bool:
    return os.getenv("RUNTIME_LLM_KEYS", "false").strip().lower() == "true"


def current_runtime_settings():
    return _settings.get()


@contextmanager
def runtime_llm_request(scope):
    """Accept keys only on health and message creation, never in URLs or bodies."""
    settings = None
    if runtime_llm_keys_enabled():
        path, method = scope.get("path", ""), scope.get("method", "")
        health = method == "GET" and path == "/api/v1/health"
        message = method == "POST" and _MESSAGE_PATH.fullmatch(path)
        if health or message:
            values = [value for name, value in scope.get("headers", []) if name.lower() == b"x-openrouter-key"]
            if values and (len(values) != 1 or _KEY.fullmatch(values[0]) is None):
                raise ApiError("KEY_INVALID", "示範用 OpenRouter 金鑰格式不正確，請重新設定。", 422)
            if message and not values:
                raise ApiError("KEY_REQUIRED", "請先設定本次示範用的 OpenRouter 金鑰，再使用 AI 對話。", 401)
            if values:
                from .ai.openai_compatible import OpenAICompatibleSettings, OPENROUTER_BASE_URL, OPENROUTER_PAID_MODEL

                settings = OpenAICompatibleSettings(api_key=values[0].decode("ascii"), model=OPENROUTER_PAID_MODEL,
                    base_url=OPENROUTER_BASE_URL, timeout_seconds=300, request_scoped=True)
    token = _settings.set(settings)
    try:
        yield
    finally:
        _settings.reset(token)


@contextmanager
def detached_runtime_operation(operation):
    """Create jobs/callbacks without a credential-bearing inherited context.

    The operation binds its immutable settings only while executing. Clearing
    the closure and context releases credential references on success, failure
    and cancellation; terminal job records contain only sanitized API results.
    """
    settings = current_runtime_settings()
    token = _settings.set(None)

    async def execute():
        nonlocal settings
        _settings.set(settings)
        settings = None
        try:
            return await operation()
        finally:
            _settings.set(None)

    try:
        yield execute
    finally:
        _settings.reset(token)
