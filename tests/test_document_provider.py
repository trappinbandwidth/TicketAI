import json

import pytest

from app.services.document_provider import process_document
from app.services.openai_document_client import _output_text, process_document_openai


def test_provider_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("DOCUMENT_AI_PROVIDER", "unknown")
    with pytest.raises(ValueError, match="Unsupported"):
        process_document([], "")


def test_openai_output_text_parses_responses_shape():
    assert _output_text({
        "output": [{"content": [{"type": "output_text", "text": "{\"ok\":true}"}]}]
    }) == "{\"ok\":true}"


def test_openai_adapter_sends_images_and_disables_storage(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self):
            return json.dumps({
                "id": "resp_test",
                "output_text": json.dumps({"file_type": "Ticket"}),
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }).encode()

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data)
        return Response()

    monkeypatch.setenv("USE_MOCK", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    monkeypatch.setenv("OPENAI_DOCUMENT_MODEL", "configured-model")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("app.services.openai_document_client._load_prompt", lambda _: "Return JSON")

    result, is_mock, usage = process_document_openai(["iVBORabc"], "OCR", prompt_version="v2")

    assert result["file_type"] == "Ticket"
    assert is_mock is False
    assert captured["payload"]["store"] is False
    assert captured["payload"]["model"] == "configured-model"
    assert captured["payload"]["input"][0]["content"][0]["type"] == "input_image"
    assert usage["response_id"] == "resp_test"
