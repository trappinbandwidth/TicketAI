"""OpenAI Responses API adapter for governed multimodal document extraction."""
from __future__ import annotations

import json
import os
import urllib.request

from app.services.claude_client import MOCK_RESPONSE, _load_prompt


def _output_text(response: dict) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    parts = []
    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                parts.append(content["text"])
    if not parts:
        raise ValueError("OpenAI response did not contain output text.")
    return "".join(parts)


def process_document_openai(
    images_b64: list[str],
    ocr_text: str,
    driver_name: str | None = None,
    prompt_version: str = "v1",
    temperature: float = 1.0,
) -> tuple[dict, bool, dict | None]:
    use_mock = os.getenv("USE_MOCK", "true").lower() == "true"
    api_key = os.getenv("OPENAI_API_KEY", "")
    if use_mock or not api_key:
        return MOCK_RESPONSE, True, None

    model = os.getenv("OPENAI_DOCUMENT_MODEL", "gpt-5.6-luna")
    content: list[dict] = []
    for image in images_b64:
        mime = "image/jpeg" if image.startswith("/9j/") else "image/png"
        content.append({
            "type": "input_image",
            "image_url": f"data:{mime};base64,{image}",
            "detail": "high",
        })
    prompt = "Analyze this document and return only the requested JSON."
    if ocr_text:
        prompt += f"\n\nOCR Text:\n{ocr_text}"
    if driver_name:
        prompt += f"\n\nDriver Name for file_name field: {driver_name}"
    content.append({"type": "input_text", "text": prompt})
    payload = {
        "model": model,
        "instructions": _load_prompt(prompt_version),
        "input": [{"role": "user", "content": content}],
        "text": {"format": {"type": "json_object"}},
        "store": False,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=180) as result:
        response = json.loads(result.read())
    parsed = json.loads(_output_text(response))
    usage = response.get("usage") or {}
    return parsed, False, {
        "provider": "openai",
        "model": model,
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "response_id": response.get("id"),
    }
