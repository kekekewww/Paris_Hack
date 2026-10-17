"""Stateless conversation orchestration; the API owns case/message persistence."""
from __future__ import annotations

import os

from .providers import AIError, GroundedRulesProvider, UnavailableLLMProvider, validate_assistant_response
from .openai_compatible import OpenAICompatibleProvider, OpenAICompatibleSettings
from .retrieval import OfficialRetriever


def provider_status() -> dict:
    mode = os.getenv("LLM_PROVIDER", "grounded_rules").strip().lower()
    if mode in ("", "grounded_rules"):
        return {"llm_provider": "grounded_rules", "llm_configured": False, "llm_verified": False}
    if mode == "openai_compatible":
        try:
            OpenAICompatibleSettings.from_environment()
            configured = True
        except AIError:
            configured = False
        # Configuration is not evidence that a real model request was verified.
        return {"llm_provider": mode, "llm_configured": configured, "llm_verified": False}
    return {"llm_provider": "unconfigured_llm", "llm_configured": False, "llm_verified": False}


async def respond(case: dict, message: str, document_id: str | None = None) -> dict:
    if not isinstance(message, str) or not message.strip() or len(message) > 4000:
        raise AIError("VALIDATION_ERROR", "請輸入 1 至 4000 字的問題。")
    if document_id is not None and not any(item.get("id") == document_id for item in case.get("documents", [])):
        raise AIError("DOCUMENT_NOT_FOUND", "找不到這份案件文件。", 404)
    retriever = OfficialRetriever()
    mode = provider_status()["llm_provider"]
    if mode == "grounded_rules":
        provider = GroundedRulesProvider(retriever)
    elif mode == "openai_compatible":
        provider = OpenAICompatibleProvider(OpenAICompatibleSettings.from_environment(), retriever)
    else:
        provider = UnavailableLLMProvider()
    payload = await provider.respond(case, message.strip(), document_id)
    return validate_assistant_response(payload, retriever)
