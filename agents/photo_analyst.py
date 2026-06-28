"""
Photo Analyst — analyzes photographs submitted with CDL driver cases.

Handles: vehicle damage, accident scenes, injury/person photos, repair docs,
road/environment, equipment damage.

Short-circuits the full ticket-extraction pipeline — photos bypass lone_ranger,
referee, book_worm, research_ron, and team_quest entirely.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "photo_v1.md"

_EMPTY_FIELD = {"value": "", "confidence_score": 0.0, "ai_reason": "Not applicable to photo."}

_MOCK_RESULT: dict = {
    "file_type": "Photo",
    "photo_type": "Other",
    "file_name": "mock_photo.jpg",
    "document_text_format": "photo",
    "file_type_analysis": {"confidence_score": 0.0, "ai_reason": "Mock mode active."},
    "other_document_types": [],
    "Photo_Type__c":       {"value": "Other", "confidence_score": 0.0, "ai_reason": "Mock mode."},
    "Photo_Summary__c":    {"value": "Photo received — mock mode, no analysis performed.", "confidence_score": 0.0, "ai_reason": "Mock mode."},
    "Damage_Assessment__c": {"value": "", "confidence_score": 0.0, "ai_reason": "Mock mode."},
    "Attorney_Notes__c":   {"value": "", "confidence_score": 0.0, "ai_reason": "Mock mode."},
}

# Photo types the model may return — used only for logging
_KNOWN_PHOTO_TYPES = {
    "Vehicle Damage", "Accident Scene", "Person/Injury", "Equipment Damage",
    "Road/Environment", "Driver Documentation", "Repair Documentation", "Other",
}


def analyze_photo(images_b64: list[str], filename: str) -> dict:
    """
    Run Claude vision analysis on a photograph.

    Args:
        images_b64: list of base64-encoded image strings (one per page/angle)
        filename: original filename, included in the prompt for context

    Returns:
        Dict conforming to DocumentResult photo fields + file_type metadata.
        Always succeeds — falls back to a safe placeholder on any error.
    """
    use_mock = os.getenv("USE_MOCK", "true").lower() == "true"
    api_key  = os.getenv("ANTHROPIC_API_KEY", "")

    if use_mock or not api_key:
        logger.warning("[photo_analyst] MOCK file=%s", filename)
        result = dict(_MOCK_RESULT)
        result["file_name"] = filename
        return result

    try:
        import anthropic

        prompt_text = PROMPT_PATH.read_text()

        # Build multimodal content: images first, then text prompt with filename context
        content: list[dict] = []
        for b64 in images_b64[:6]:  # cap at 6 images per submission
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
            })
        content.append({
            "type": "text",
            "text": f"Filename: {filename}\n\n{prompt_text}",
        })

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1200,
            temperature=0.2,
            messages=[{"role": "user", "content": content}],
        )

        raw = response.content[0].text.strip()
        # Strip markdown code fences if model wraps in ```json ... ```
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)
        result["file_name"] = filename

        photo_type = result.get("photo_type", "Unknown")
        if photo_type not in _KNOWN_PHOTO_TYPES:
            logger.warning("[photo_analyst] unexpected photo_type=%r file=%s", photo_type, filename)

        logger.warning("[photo_analyst] OK file=%s type=%s conf=%.2f",
                       filename, photo_type,
                       result.get("file_type_analysis", {}).get("confidence_score", 0.0))
        return result

    except Exception as exc:
        logger.error("[photo_analyst] FAILED file=%s error=%s", filename, exc, exc_info=True)
        fallback = dict(_MOCK_RESULT)
        fallback["file_name"] = filename
        fallback["file_type_analysis"] = {
            "confidence_score": 0.0,
            "ai_reason": f"Analysis failed: {exc}. Manual review required.",
        }
        fallback["Photo_Summary__c"]["value"] = (
            "Photo analysis failed — attorney should review the original image directly."
        )
        return fallback
