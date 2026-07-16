import pytest

from app.platform.partner_api import (
    PartnerApiService,
    PartnerClientCreate,
    PartnerEventCreate,
    WebhookSubscriptionCreate,
)
from tests.test_platform_identity import FakeDb


def setup_partner():
    db = FakeDb()
    service = PartnerApiService(db)
    credentials = service.create_client(PartnerClientCreate(
        tenant_id="org_1", name="Safety Partner",
        scopes=["records:read", "events:subscribe"], environment="staging",
    ), "prn_admin")
    return db, service, credentials


def test_partner_secret_is_returned_once_hashed_at_rest_and_scope_checked():
    db, service, credentials = setup_partner()
    client = credentials["client"]
    stored = db.collection("partner_api_clients").rows[client["id"]]
    assert credentials["client_secret"] not in str(stored)
    assert "secret_hash" not in client
    context = service.authenticate(client["id"], credentials["client_secret"], "records:read")
    assert context["tenant_id"] == "org_1"
    with pytest.raises(PermissionError):
        service.authenticate(client["id"], credentials["client_secret"], "ledger:write")


def test_events_are_versioned_tenant_scoped_and_queued_for_matching_subscriptions():
    db, service, credentials = setup_partner()
    client_id = credentials["client"]["id"]
    service.create_subscription(WebhookSubscriptionCreate(
        client_id=client_id, tenant_id="org_1", url="https://partner.example.test/hooks",
        event_types=["case.updated"], secret_ref="projects/p/secrets/partner-hook",
    ), "prn_admin")
    event, deliveries = service.publish(PartnerEventCreate(
        tenant_id="org_1", event_type="case.updated", aggregate_type="case",
        aggregate_id="case_1", data={"status": "accepted"},
    ))
    assert event["schema_version"] == "1.0"
    assert len(deliveries) == 1

    prepared = service.prepare_delivery(deliveries[0]["id"], lambda _: "webhook-secret")
    assert prepared["headers"]["X-RigResolve-Signature"].startswith("v1=")
    assert b"webhook-secret" not in prepared["body"]


def test_webhook_delivery_retries_then_dead_letters():
    _, service, credentials = setup_partner()
    subscription = service.create_subscription(WebhookSubscriptionCreate(
        client_id=credentials["client"]["id"], tenant_id="org_1",
        url="https://partner.example.test/hooks", event_types=["signal.created"],
        secret_ref="projects/p/secrets/hook",
    ), "prn_admin")
    _, deliveries = service.publish(PartnerEventCreate(
        tenant_id="org_1", event_type="signal.created", aggregate_type="signal",
        aggregate_id="sig_1", data={},
    ))
    delivery_id = deliveries[0]["id"]
    result = None
    for _ in range(8):
        result = service.record_delivery_result(delivery_id, False, 503, "unavailable")
    assert result["status"] == "dead_letter"
    assert result["attempt_count"] == 8
