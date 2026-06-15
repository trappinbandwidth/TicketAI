"""
Basic smoke tests — run with: pytest tests/
Golden-file tests (real tickets) go in tests/golden/ once S3 access is set up.
"""
import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("USE_MOCK", "true")
os.environ.setdefault("API_KEY", "cdl-local-dev")

from app.main import app

client = TestClient(app)
HEADERS = {"x-api-key": "cdl-local-dev"}


def _blank_pdf() -> bytes:
    import fitz
    doc = fitz.open()
    doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_auth_required():
    r = client.post("/api/v1/process", files={"file": ("t.pdf", b"x", "application/pdf")})
    assert r.status_code == 401


def test_unsupported_file_type():
    r = client.post(
        "/api/v1/process",
        files={"file": ("t.docx", b"x", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers=HEADERS,
    )
    assert r.status_code == 415


def test_mock_response_shape():
    """Confirm mock returns the full expected JSON schema."""
    r = client.post(
        "/api/v1/process",
        files={"file": ("ticket.pdf", _blank_pdf(), "application/pdf")},
        headers=HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["mock"] is True
    result = body["result"]

    required_fields = [
        "file_type", "other_document_types", "file_type_analysis",
        "file_name", "document_text_format",
        "Date_of_Ticket__c", "Violation_Description__c", "Violation_Category__c",
        "Court_Date__c", "Accident__c", "Drivers_License_Type__c",
        "Ticket_Court__c", "Court_Phone_Number__c",
        "Ticket_City__c", "Ticket_County__c", "Ticket_State__c",
        "Insp_Report_Num__c", "Citation_Number__c",
    ]
    for field in required_fields:
        assert field in result, f"Missing field: {field}"


def test_mock_pass_status_present():
    """Pass status and orchestration fields must always be in the response."""
    r = client.post(
        "/api/v1/process",
        files={"file": ("ticket.pdf", _blank_pdf(), "application/pdf")},
        headers=HEADERS,
    )
    body = r.json()
    assert "pass_status" in body
    assert body["pass_status"] in ("green", "yellow", "red", "unknown")
    assert isinstance(body["low_confidence_fields"], list)


def test_mock_cdl_point_impact():
    """book_worm CDL point impact must be present on green/yellow paths."""
    r = client.post(
        "/api/v1/process",
        files={"file": ("ticket.pdf", _blank_pdf(), "application/pdf")},
        headers=HEADERS,
    )
    body = r.json()
    # Mock extraction uses confidence 0.0 on all fields → RED path → no cdl_point_impact
    # This confirms red-path routing works (cdl_point_impact is None on red)
    if body["pass_status"] == "red":
        assert body["cdl_point_impact"] is None
    else:
        assert body["cdl_point_impact"] is not None


def test_referee_calibration_rejects_bad_date_format():
    """Referee must cap confidence when a date field doesn't match MM/DD/YYYY."""
    from agents.referee import _calibrate_scores

    fields = {
        "Date_of_Ticket__c": {"value": "2025-06-01", "confidence_score": 0.95, "ai_reason": "test"},
        "Court_Date__c": {"value": "06/30/2025", "confidence_score": 0.90, "ai_reason": "test"},
    }
    calibrated = _calibrate_scores(fields)
    assert calibrated["Date_of_Ticket__c"] <= 0.50, "Bad date format should be capped"
    assert calibrated["Court_Date__c"] == 0.90, "Valid date should be unchanged"


def test_referee_calibration_rejects_unknown_category():
    """Referee must cap confidence on a violation category not in the picklist."""
    from agents.referee import _calibrate_scores

    fields = {
        "Violation_Category__c": {"value": "Made Up Violation", "confidence_score": 0.88, "ai_reason": "test"},
    }
    calibrated = _calibrate_scores(fields)
    assert calibrated["Violation_Category__c"] <= 0.40


def test_book_worm_csa_category_no_unknown():
    """CSA category for all defined violations must not return 'Unknown'."""
    from agents.book_worm import CDL_POINT_MAP

    for category, impact in CDL_POINT_MAP.items():
        assert "csa_category" in impact, f"Missing csa_category key for: {category}"
        assert impact["csa_category"] != "Unknown", f"Unknown CSA category for: {category}"
