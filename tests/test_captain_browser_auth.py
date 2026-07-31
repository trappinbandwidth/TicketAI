"""Captain browser routes must use a staff identity, never a shipped key."""
from fastapi.testclient import TestClient

from app.main import app
from app.routes import pricing, queue


client = TestClient(app)


def test_queue_accepts_staff_bearer_without_service_key(monkeypatch):
    monkeypatch.setattr(
        queue,
        "verify_firebase_token",
        lambda _header: {"uid": "reviewer_1", "role": "reviewer"},
    )
    monkeypatch.setattr(queue, "get_item", lambda _item_id: None)

    response = client.get(
        "/api/v1/queue/missing",
        headers={"authorization": "Bearer staff-token"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Queue item not found."


def test_queue_rejects_non_staff_even_when_service_key_is_also_present(monkeypatch):
    monkeypatch.setattr(
        queue,
        "verify_firebase_token",
        lambda _header: {"uid": "carrier_1", "role": "carrier"},
    )

    response = client.get(
        "/api/v1/queue/missing",
        headers={
            "authorization": "Bearer carrier-token",
            "x-api-key": "cdl-local-dev",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Staff role required."


def test_queue_approval_derives_reviewer_from_staff_token(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        queue,
        "verify_firebase_token",
        lambda _header: {"uid": "reviewer_1", "role": "reviewer"},
    )
    monkeypatch.setattr(queue, "get_item", lambda _item_id: {"id": "scan_1"})
    monkeypatch.setattr(
        queue,
        "approve_item",
        lambda item_id, fields, reviewer_id: captured.update(
            item_id=item_id,
            fields=fields,
            reviewer_id=reviewer_id,
        ),
    )

    response = client.put(
        "/api/v1/queue/scan_1/approve",
        headers={"authorization": "Bearer staff-token"},
        json={"edited_fields": {"Ticket_State__c": "TX"}, "reviewer_id": "spoofed"},
    )

    assert response.status_code == 200
    assert captured == {
        "item_id": "scan_1",
        "fields": {"Ticket_State__c": "TX"},
        "reviewer_id": "reviewer_1",
    }


def test_pricing_accepts_staff_bearer_without_service_key(monkeypatch):
    monkeypatch.setattr(
        pricing,
        "verify_firebase_token",
        lambda _header: {"uid": "staff_1", "role": "staff"},
    )

    response = client.get(
        "/api/v1/price-estimate",
        params={"state": "Texas", "violation": "Speeding (15+)"},
        headers={"authorization": "Bearer staff-token"},
    )

    assert response.status_code == 200
