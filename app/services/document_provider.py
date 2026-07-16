"""Feature-flagged Anthropic/OpenAI document provider dispatch."""
from __future__ import annotations

import os


def process_document(*args, **kwargs):
    provider = os.getenv("DOCUMENT_AI_PROVIDER", "anthropic").strip().lower()
    if provider == "anthropic":
        from app.services.claude_client import process_document as run
    elif provider == "openai":
        from app.services.openai_document_client import process_document_openai as run
    else:
        raise ValueError(f"Unsupported DOCUMENT_AI_PROVIDER: {provider}")
    result, is_mock, usage = run(*args, **kwargs)
    if usage is not None:
        usage = {**usage, "provider": provider}
    return result, is_mock, usage
