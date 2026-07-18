import pytest

from app.platform.document_service import DocumentService
from app.platform.documents import (
    DocumentStatus,
    ExtractionField,
    SafeFallbackScanner,
    ScanResult,
    validate_upload,
)
from app.services.document_worker import run_document_job
from tests.test_platform_identity import FakeDb


class CleanScanner:
    def scan(self, content):
        return ScanResult.CLEAN


def test_magic_bytes_filename_checksum_and_duplicate_detection():
    service = DocumentService(FakeDb(), CleanScanner())
    content = b"%PDF-1.7 safe"

    first = service.ingest("prn_driver", "../../ticket?.pdf", "application/pdf", content)
    second = service.ingest("prn_driver", "copy.pdf", "application/pdf", content)

    assert first.filename == "ticket_.pdf"
    assert first.status == DocumentStatus.READY
    assert second.duplicate_of == first.id
    assert first.sha256 == second.sha256


def test_scanner_unavailable_never_releases_document_and_eicar_is_unsafe():
    service = DocumentService(FakeDb(), SafeFallbackScanner())

    pending = service.ingest("prn_driver", "ticket.pdf", "application/pdf", b"%PDF safe")
    unsafe = service.ingest(
        "prn_driver",
        "bad.pdf",
        "application/pdf",
        b"%PDF EICAR-STANDARD-ANTIVIRUS-TEST-FILE",
    )

    assert pending.status == DocumentStatus.SCAN_PENDING
    assert unsafe.status == DocumentStatus.UNSAFE


def test_spoofed_or_oversize_content_is_rejected():
    with pytest.raises(ValueError, match="does not match"):
        validate_upload("fake.pdf", "application/pdf", b"not a pdf")
    with pytest.raises(ValueError, match="20 MB"):
        validate_upload("large.pdf", "application/pdf", b"%PDF" + b"x" * (20 * 1024 * 1024))


def test_extraction_requires_clean_owner_and_human_verification():
    db = FakeDb()
    service = DocumentService(db, CleanScanner())
    asset = service.ingest("prn_driver", "ticket.pdf", "application/pdf", b"%PDF safe")
    field = ExtractionField(
        field_name="citation_number",
        value="ABC12B",
        confidence=0.72,
        page=1,
        bounding_box={"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.04},
        raw_evidence="Citation ABC123",
    )

    with pytest.raises(PermissionError):
        service.start_extraction(
            "prn_other", asset.id, [field], classifier_version="v1", extractor_version="v2",
            model_provider="anthropic", model_name="claude", prompt_version="v2",
        )
    run = service.start_extraction(
        "prn_driver", asset.id, [field], classifier_version="v1", extractor_version="v2",
        model_provider="anthropic", model_name="claude", prompt_version="v2",
    )
    verified = service.verify_extraction(
        "prn_driver", run.id, {"citation_number": "ABC123"}
    )

    assert verified.fields[0].corrected_value == "ABC123"
    assert verified.fields[0].verified is True
    assert db.collection("document_assets").rows[asset.id]["status"] == "verified"


def test_async_extraction_queue_is_owner_scoped_and_idempotent():
    db = FakeDb()
    service = DocumentService(db, CleanScanner())
    asset = service.ingest("prn_driver", "ticket.pdf", "application/pdf", b"%PDF queue")

    first, created = service.enqueue_extraction("prn_driver", asset.id)
    second, created_again = service.enqueue_extraction("prn_driver", asset.id)

    assert created is True
    assert created_again is False
    assert first.id == second.id
    assert service.get_job("prn_driver", first.id).status == "queued"
    with pytest.raises(PermissionError):
        service.get_job("prn_other", first.id)


def test_worker_advances_job_to_human_review(monkeypatch):
    db = FakeDb()
    service = DocumentService(db, CleanScanner())
    asset = service.ingest(
        "prn_driver",
        "ticket.png",
        "image/png",
        b"\x89PNG\r\n\x1a\nsafe",
        storage_path="gs://bucket/path",
    )
    job, _ = service.enqueue_extraction("prn_driver", asset.id)
    monkeypatch.setattr("app.services.document_worker._download", lambda _: b"image")
    monkeypatch.setattr(
        "app.services.document_worker.image_file_to_base64",
        lambda *_: (["iVBOR"], "Citation ABC123"),
    )
    monkeypatch.setattr(
        "app.services.document_worker.process_document",
        lambda **_: (
            {
                "Citation_Number__c": {
                    "value": "ABC123",
                    "confidence_score": 0.91,
                    "raw_evidence": "Citation ABC123",
                }
            },
            False,
            {"provider": "openai", "model": "configured-model"},
        ),
    )

    result = run_document_job(db, job.id)

    assert result["job"].status == "review_required"
    assert result["extraction_run"].fields[0].value == "ABC123"
    assert result["extraction_run"].model_provider == "openai"
