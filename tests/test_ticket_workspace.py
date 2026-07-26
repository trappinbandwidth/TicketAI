from fastapi import HTTPException
import pytest

from app.routes import ticket_workspace


def test_workspace_requires_staff_before_database_access(monkeypatch):
    def deny(_authorization):
        raise HTTPException(status_code=401, detail="Missing bearer token.")

    monkeypatch.setattr(ticket_workspace, "require_staff", deny)
    monkeypatch.setattr(
        ticket_workspace,
        "get_db",
        lambda: pytest.fail("database must not be accessed before authentication"),
    )

    with pytest.raises(HTTPException) as error:
        ticket_workspace.get_ticket_workspace("ticket-1")

    assert error.value.status_code == 401


def test_guidance_keeps_driver_tip_score_separate_from_carrier_csa():
    guidance = ticket_workspace._recommendations({"missing_fields": ["court_date"]})

    assert "TIP Score and FMCSA CSA are separate systems" in guidance["disclaimer"]
    assert guidance["driver"][0] == "Complete missing ticket evidence: court_date."
    assert any("DataQs" in item for item in guidance["carrier"])


def test_work_item_contract_rejects_unverified_status_and_blank_text():
    with pytest.raises(ValueError):
        ticket_workspace.WorkItemBody(
            kind="court_contact",
            text="",
            audience="internal",
            status="called_and_confirmed",
        )


def test_manual_phone_contact_never_claims_in_app_delivery():
    class NoWrites:
        def collection(self, _name):
            pytest.fail("manual phone logging must not create a delivery record")

    delivery = ticket_workspace._notify(
        NoWrites(),
        "ticket-1",
        {"assigned_attorney_id": "attorney-1"},
        {"uid": "staff-1"},
        "item-1",
        ticket_workspace.WorkItemBody(
            kind="communication",
            text="Left voicemail with the firm.",
            audience="attorney",
            status="attempted",
            channel="phone",
        ),
    )

    assert delivery == "manual_contact_recorded"
