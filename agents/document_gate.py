"""
Document Gate — fast pre-classifier before lone_ranger.

Sends the first image to claude-haiku with a two-sentence prompt.
Cost: ~100 tokens ≈ $0.00004 vs $0.15–0.29 for a full lone_ranger run on a photo.

Returns doc_type in state:
  "photo"    → photo_analyst path  (photo_v1.md prompt, cheap analysis)
  "document" → lone_ranger path    (v2.md extraction, full pipeline)
  "unknown"  → escalate_red        (no Claude spend, flag for human)
"""
from __future__ import annotations
import logging
import os

from app.services.queue_store import log_agent_event
from orchestrator.state import PassStatus, TicketState

logger = logging.getLogger(__name__)
AGENT_NAME = "document_gate"

_GATE_PROMPT = (
    "Look at this image. Classify it as exactly one of three types:\n"
    "- 'photo': a photograph of a scene, vehicle, person, accident, damage, "
    "road, or environment — NOT a document\n"
    "- 'document': a legal or government document with structured text fields "
    "(citation, ticket, inspection report, crash report, CDL license, motor "
    "vehicle record, civil penalty notice, or similar form)\n"
    "- 'unknown': anything else — blank page, illegible scan, personal photo "
    "ID used as a document, unrelated paperwork\n\n"
    "Reply with ONLY the single word: photo, document, or unknown. No explanation."
)


def document_gate(state: TicketState) -> dict:
    """LangGraph node — cheap image pre-classifier."""
    filename = state.get("filename", "unknown")
    scan_id  = state.get("scan_id", "")
    images   = state.get("images_b64", [])

    use_mock = os.getenv("USE_MOCK", "true").lower() == "true"
    api_key  = os.getenv("ANTHROPIC_API_KEY", "")

    if use_mock or not api_key:
        logger.warning("[document_gate] MOCK → defaulting to 'document' file=%s", filename)
        log_agent_event(scan_id, AGENT_NAME, "mock", {"doc_type": "document"})
        return {"doc_type": "document"}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        img_b64 = images[0]
        mime = "image/jpeg" if img_b64.startswith("/9j/") else "image/png"

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": mime, "data": img_b64},
                    },
                    {"type": "text", "text": _GATE_PROMPT},
                ],
            }],
        )

        raw = message.content[0].text.strip().lower()
        # Take first word in case model adds punctuation
        doc_type = raw.split()[0].rstrip(".,;:")
        if doc_type not in ("photo", "document", "unknown"):
            logger.warning("[document_gate] unexpected response=%r → defaulting to document", raw)
            doc_type = "document"

        logger.warning(
            "[document_gate] classified=%r file=%s tokens_in=%d out=%d",
            doc_type, filename,
            message.usage.input_tokens, message.usage.output_tokens,
        )
        log_agent_event(scan_id, AGENT_NAME, "ok", {"doc_type": doc_type})
        return {"doc_type": doc_type}

    except Exception as exc:
        # Safe fallback: let lone_ranger handle it — never block a submission
        logger.error("[document_gate] FAILED file=%s error=%s — defaulting to document", filename, exc)
        log_agent_event(scan_id, AGENT_NAME, "error", {"error": str(exc), "doc_type": "document"})
        return {"doc_type": "document"}
