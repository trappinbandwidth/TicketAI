"""Feature-flagged Anthropic/OpenAI document provider dispatch."""
from __future__ import annotations

import os


def _run_provider(provider: str, *args, **kwargs):
    if provider == "anthropic":
        from app.services.claude_client import process_document as run
    elif provider == "openai":
        from app.services.openai_document_client import process_document_openai as run
    else:
        raise ValueError(f"Unsupported DOCUMENT_AI_PROVIDER: {provider}")
    return run(*args, **kwargs)


def process_document(*args, **kwargs):
    provider = os.getenv("DOCUMENT_AI_PROVIDER", "anthropic").strip().lower()
    if provider not in {"anthropic", "openai"}:
        raise ValueError(f"Unsupported DOCUMENT_AI_PROVIDER: {provider}")
    fallback = os.getenv("DOCUMENT_AI_FALLBACK_PROVIDER", "").strip().lower()
    fallback_enabled = os.getenv("DOCUMENT_AI_FALLBACK_ENABLED", "false").lower() == "true"
    if fallback and fallback not in {"anthropic", "openai"}:
        raise ValueError(f"Unsupported DOCUMENT_AI_FALLBACK_PROVIDER: {fallback}")
    try:
        result, is_mock, usage = _run_provider(provider, *args, **kwargs)
    except Exception:
        if not fallback_enabled or not fallback or fallback == provider:
            raise
        result, is_mock, usage = _run_provider(fallback, *args, **kwargs)
        usage = {
            **(usage or {}),
            "fallback_from": provider,
            "fallback_reason": "primary_provider_technical_failure",
            "human_review_required": True,
        }
        provider = fallback
    if usage is not None:
        usage = {**usage, "provider": provider}
    return result, is_mock, usage
