from app.platform.record_migration import (
    LegacyTicket,
    normalize_legacy_datetime,
    plan_ticket_projections,
    record_id_for_ticket,
)


def test_ticket_projection_is_stable_and_separates_fact_layers():
    ticket = LegacyTicket("ticket-1", {
        "driver_id": "driver-1",
        "citation_number": "ABC123",
        "violation_description": "Speeding",
        "ticket_state": "MO",
        "price_low": 250,
        "pass_status": "GREEN",
        "created_at": "2026-07-01T12:00:00Z",
    })

    first = plan_ticket_projections([ticket], {})[0]
    second = plan_ticket_projections([ticket], {})[0]

    assert first.record_id == second.record_id == record_id_for_ticket("ticket-1")
    assert first.body.raw["driver_id"] == "driver-1"
    assert first.body.normalized["citation_number"] == "ABC123"
    assert first.body.derived["price_low"] == 250
    assert first.body.provenance.method == "migration"


def test_projection_reports_invalid_conflict_and_unchanged():
    missing_driver = LegacyTicket("missing", {"citation_number": "1"})
    valid = LegacyTicket("valid", {"driver_id": "driver-1", "created_at": "2026-07-01T12:00:00Z"})
    valid_id = record_id_for_ticket("valid")

    invalid = plan_ticket_projections([missing_driver], {})[0]
    conflict = plan_ticket_projections(
        [valid], {valid_id: {"source_legacy_ref": "tickets/someone-else"}}
    )[0]
    unchanged = plan_ticket_projections(
        [valid], {valid_id: {"source_legacy_ref": "tickets/valid"}}
    )[0]

    assert invalid.outcome == "invalid"
    assert conflict.outcome == "conflict"
    assert unchanged.outcome == "unchanged"


def test_legacy_dates_normalize_without_changing_raw_value():
    ticket = LegacyTicket("dated", {
        "driver_id": "driver-1",
        "date_of_ticket": "01/01/2025",
        "created_at": "not-a-date",
    })

    projection = plan_ticket_projections([ticket], {})[0]

    assert projection.body.occurred_at.isoformat() == "2025-01-01T00:00:00+00:00"
    assert projection.body.raw["date_of_ticket"] == "01/01/2025"
    assert normalize_legacy_datetime("unknown") is None
