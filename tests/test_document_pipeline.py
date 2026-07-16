import pytest

from app.platform.document_service import DocumentService
from app.platform.documents import (
    DocumentStatus,
    ExtractionField,
    SafeFallbackScanner,
    ScanResult,
    validate_upload,
)
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
