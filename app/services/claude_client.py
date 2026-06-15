import json
import logging
import os
import re
import time
from pathlib import Path

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent.parent.parent / "prompts"

MOCK_RESPONSE = {
    "file_type": "Ticket",
    "other_document_types": [],
    "file_type_analysis": {
        "confidence_score": 1.0,
        "ai_reason": "MOCK — drop ANTHROPIC_API_KEY in .env and set USE_MOCK=false to get real results."
    },
    "file_name": "Mock_Driver_TK",
    "document_text_format": "digital",
    "Date_of_Ticket__c": {"value": "01/01/2025", "confidence_score": 0.0, "ai_reason": "Mock value."},
    "Violation_Description__c": {"value": "MOCK VIOLATION", "confidence_score": 0.0, "ai_reason": "Mock value."},
    "Violation_Category__c": {"value": "Speeding (15+)", "confidence_score": 0.0, "ai_reason": "Mock value."},
    "Court_Date__c": {"value": "02/01/2025", "confidence_score": 0.0, "ai_reason": "Mock value."},
    "Accident__c": {"value": "No", "confidence_score": 0.0, "ai_reason": "Mock value."},
    "Drivers_License_Type__c": {"value": "CDL", "confidence_score": 0.0, "ai_reason": "Mock value."},
    "Ticket_Court__c": {"value": "Mock County Court", "confidence_score": 0.0, "ai_reason": "Mock value."},
    "Court_Phone_Number__c": {"value": "(000) 000-0000", "confidence_score": 0.0, "ai_reason": "Mock value."},
    "Ticket_City__c": {"value": "Mockville", "confidence_score": 0.0, "ai_reason": "Mock value."},
    "Ticket_County__c": {"value": "Mock County", "confidence_score": 0.0, "ai_reason": "Mock value."},
    "Ticket_State__c": {"value": "Kansas", "confidence_score": 0.0, "ai_reason": "Mock value."},
    "Insp_Report_Num__c": {"value": "", "confidence_score": 0.0, "ai_reason": "Mock value."},
    "Citation_Number__c": {"value": "MOCK-12345", "confidence_score": 0.0, "ai_reason": "Mock value."},
}


def _load_prompt(version: str) -> str:
    path = PROMPT_DIR / f"{version}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text()


def process_document(
    images_b64: list[str],
    ocr_text: str,
    driver_name: str | None = None,
    prompt_version: str = "v1",
    temperature: float = 1.0,
) -> tuple[dict, bool]:
    """
    Returns (parsed_json, is_mock).
    Uses mock when USE_MOCK=true or ANTHROPIC_API_KEY is missing.
    """
    use_mock = os.getenv("USE_MOCK", "true").lower() == "true"
    api_key = os.getenv("ANTHROPIC_API_KEY", "")

    logger.warning("process_document: use_mock=%s api_key_set=%s key_prefix=%s", use_mock, bool(api_key), api_key[:12] if api_key else "NONE")

    if use_mock or not api_key:
        return MOCK_RESPONSE, True

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    system_prompt = _load_prompt(prompt_version)

    # Build multimodal content — image(s) first, then OCR text
    content: list[dict] = []
    for img_b64 in images_b64:
        # Detect MIME from base64 header: JPEG starts /9j/ → "\xff\xd8", PNG starts iVBOR
        mime = "image/jpeg" if img_b64.startswith("/9j/") else "image/png"
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": mime, "data": img_b64},
        })

    user_text = "Please analyze this document and return the JSON as instructed."
    if ocr_text:
        user_text += f"\n\nOCR Text:\n{ocr_text}"
    if driver_name:
        user_text += f"\n\nDriver Name for file_name field: {driver_name}"

    content.append({"type": "text", "text": user_text})

    create_kwargs: dict = dict(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=system_prompt,
        messages=[{"role": "user", "content": content}],
    )
    # temperature is only settable when using extended thinking is off; Claude's
    # default is 1.0.  Values above 1.0 are not allowed.
    if temperature != 1.0:
        create_kwargs["temperature"] = max(0.0, min(temperature, 1.0))

    # Retry up to 3 times on rate-limit (429). Waits 65s on first hit to clear
    # the 1-minute token window, then backs off further on repeat failures.
    import anthropic as _anthropic
    _RETRY_DELAYS = [65, 90, 120]
    for attempt, delay in enumerate(_RETRY_DELAYS):
        try:
            message = client.messages.create(**create_kwargs)
            break
        except _anthropic.RateLimitError:
            if attempt == len(_RETRY_DELAYS) - 1:
                raise
            logger.warning("process_document: rate limit hit (attempt %d/%d) — waiting %ds",
                           attempt + 1, len(_RETRY_DELAYS), delay)
            time.sleep(delay)

    logger.warning("Claude stop_reason=%s content_blocks=%d", message.stop_reason, len(message.content))
    block = message.content[0] if message.content else None
    if block is None or not hasattr(block, "text"):
        raise ValueError(f"Claude returned no text block. stop_reason={message.stop_reason} blocks={message.content!r}")
    raw = block.text.strip()
    logger.warning("Claude raw response length=%d first200=%r", len(raw), raw[:200])
    if not raw:
        raise ValueError(f"Claude returned empty text. stop_reason={message.stop_reason}")
    # Strip markdown code fences if present (handles ```json ... ``` or ``` ... ```)
    raw = re.sub(r"^```[a-z]*\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()
    try:
        return json.loads(raw), False
    except json.JSONDecodeError:
        # Claude returned prose + JSON (chain-of-thought leak). Extract the first { ... } block.
        logger.warning("Top-level JSON parse failed — attempting to extract embedded JSON. raw[:300]=%r", raw[:300])
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group()), False
            except json.JSONDecodeError:
                pass
        logger.warning("JSON extraction fallback also failed. raw=%r", raw[:500])
        raise
