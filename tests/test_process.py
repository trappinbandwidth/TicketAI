"""
Basic smoke tests — run with: pytest tests/
Golden-file tests (real tickets) go in tests/golden/ once S3 access is set up.
"""
import os
import uuid
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("USE_MOCK", "true")
os.environ.setdefault("API_KEY", "cdl-local-dev")

from app.main import app  # noqa: E402 — app.main loads .env with override=True,
# which can clobber API_KEY/USE_MOCK above with whatever real values are in the
# local .env file. Force them back so tests are deterministic regardless of
# local .env contents (and never make live Anthropic API calls).
os.environ["API_KEY"] = "cdl-local-dev"
os.environ["USE_MOCK"] = "true"

client = TestClient(app)
HEADERS = {"x-api-key": "cdl-local-dev"}


def _driver_headers(operation_id=None):
    return {
        "authorization": "Bearer driver-token",
        "x-operation-id": operation_id or str(uuid.uuid4()),
    }


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


def test_tip_os_identity_routes_are_dark_launched_by_default(monkeypatch):
    monkeypatch.setenv("TIP_OS_IDENTITY_ENABLED", "false")

    r = client.post("/api/v1/platform/identity/bootstrap")

    assert r.status_code == 404
    assert r.json()["detail"] == "TIP OS identity APIs are not enabled."


def test_auth_required():
    r = client.post("/api/v1/process", files={"files": ("t.pdf", b"x", "application/pdf")})
    assert r.status_code == 401


def test_driver_upload_rejects_non_driver_token(monkeypatch):
    monkeypatch.setattr(
        "app.routes.process.verify_firebase_token",
        lambda _header: {"uid": "carrier_1", "role": "carrier"},
    )

    r = client.post(
        "/api/v1/process",
        files={"files": ("t.pdf", b"x", "application/pdf")},
        headers={"authorization": "Bearer carrier-token"},
    )

    assert r.status_code == 403
    assert r.json()["detail"] == "Required role missing."


def test_driver_upload_rejects_form_identity_mismatch(monkeypatch):
    monkeypatch.setattr(
        "app.routes.process.verify_firebase_token",
        lambda _header: {"uid": "driver_1", "role": "driver"},
    )

    r = client.post(
        "/api/v1/process",
        files={"files": ("t.pdf", b"x", "application/pdf")},
        data={"driver_id": "driver_2"},
        headers={"authorization": "Bearer driver-token"},
    )

    assert r.status_code == 403
    assert r.json()["detail"] == "Driver upload identity does not match the signed-in account."


def test_driver_upload_derives_driver_id_from_token(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        "app.routes.process.verify_firebase_token",
        lambda _header: {"uid": "driver_1", "role": "driver"},
    )
    monkeypatch.setattr(
        "app.routes.process.verify_enrollment",
        lambda driver_id: seen.setdefault(
            "enrollment",
            {
                "driver_id": driver_id,
                "enrolled": True,
                "status": "active",
                "message": "ok",
            },
        ),
    )

    r = client.post(
        "/api/v1/process",
        files={"files": ("t.docx", b"x", "application/octet-stream")},
        headers=_driver_headers(),
    )

    assert r.status_code == 415
    assert seen["enrollment"]["driver_id"] == "driver_1"


def test_driver_upload_cannot_select_existing_ticket_or_related_account(monkeypatch):
    monkeypatch.setattr(
        "app.routes.process.verify_firebase_token",
        lambda _header: {"uid": "driver_1", "role": "driver"},
    )

    ticket = client.post(
        "/api/v1/process",
        files={"files": ("t.pdf", b"x", "application/pdf")},
        data={"ticket_id": "ticket_owned_by_someone_else"},
        headers=_driver_headers(),
    )
    related = client.post(
        "/api/v1/process",
        files={"files": ("t.pdf", b"x", "application/pdf")},
        data={"carrier_id": "carrier_1"},
        headers=_driver_headers(),
    )

    assert ticket.status_code == 400
    assert ticket.json()["detail"] == "Driver uploads cannot select an existing ticket."
    assert related.status_code == 400
    assert related.json()["detail"] == "Driver uploads cannot select related account identities."


def test_driver_upload_replay_is_rejected(monkeypatch):
    from app.services.upload_idempotency import clear_mock_claims

    clear_mock_claims()
    monkeypatch.setattr(
        "app.routes.process.verify_firebase_token",
        lambda _header: {"uid": "driver_1", "role": "driver"},
    )
    monkeypatch.setattr(
        "app.routes.process.verify_enrollment",
        lambda driver_id: {
            "driver_id": driver_id,
            "enrolled": True,
            "status": "active",
            "message": "ok",
        },
    )
    operation_id = str(uuid.uuid4())
    request = {
        "files": {"files": ("t.docx", b"x", "application/octet-stream")},
        "headers": _driver_headers(operation_id),
    }

    first = client.post("/api/v1/process", **request)
    replay = client.post("/api/v1/process", **request)

    assert first.status_code == 415
    assert replay.status_code == 409
    assert replay.json()["detail"] == "Driver upload operation already accepted."


def test_trusted_manual_upload_retains_service_auth():
    r = client.post(
        "/api/v1/process",
        files={"files": ("t.docx", b"x", "application/octet-stream")},
        data={"source": "manual"},
        headers=HEADERS,
    )

    assert r.status_code == 415


def test_unsupported_file_type():
    r = client.post(
        "/api/v1/process",
        files={"files": ("t.docx", b"x", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"source": "manual"},
        headers=HEADERS,
    )
    assert r.status_code == 415


def test_mock_response_shape():
    """Confirm mock returns the full expected JSON schema."""
    r = client.post(
        "/api/v1/process",
        files={"files": ("ticket.pdf", _blank_pdf(), "application/pdf")},
        data={"source": "manual"},
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
        files={"files": ("ticket.pdf", _blank_pdf(), "application/pdf")},
        data={"source": "manual"},
        headers=HEADERS,
    )
    body = r.json()
    assert "pass_status" in body
    assert body["pass_status"] in ("green", "yellow", "red", "unknown")
    assert isinstance(body["low_confidence_fields"], list)


def test_mock_cdl_point_impact():
    """charlotte_ray CDL point impact must be present on green/yellow paths."""
    r = client.post(
        "/api/v1/process",
        files={"files": ("ticket.pdf", _blank_pdf(), "application/pdf")},
        data={"source": "manual"},
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
    """Bolin must cap confidence when a date field doesn't match MM/DD/YYYY."""
    from agents.bolin import _calibrate_scores

    fields = {
        "Date_of_Ticket__c": {"value": "2025-06-01", "confidence_score": 0.95, "ai_reason": "test"},
        "Court_Date__c": {"value": "06/30/2025", "confidence_score": 0.90, "ai_reason": "test"},
    }
    calibrated = _calibrate_scores(fields)
    assert calibrated["Date_of_Ticket__c"] <= 0.50, "Bad date format should be capped"
    assert calibrated["Court_Date__c"] == 0.90, "Valid date should be unchanged"


def test_referee_calibration_rejects_unknown_category():
    """Bolin must cap confidence on a violation category not in the picklist."""
    from agents.bolin import _calibrate_scores

    fields = {
        "Violation_Category__c": {"value": "Made Up Violation", "confidence_score": 0.88, "ai_reason": "test"},
    }
    calibrated = _calibrate_scores(fields)
    assert calibrated["Violation_Category__c"] <= 0.40


def test_charlotte_ray_csa_category_no_unknown():
    """CSA category for all defined violations must not return 'Unknown'."""
    from agents.charlotte_ray import CDL_POINT_MAP

    for category, impact in CDL_POINT_MAP.items():
        assert "csa_category" in impact, f"Missing csa_category key for: {category}"
        assert impact["csa_category"] != "Unknown", f"Unknown CSA category for: {category}"
