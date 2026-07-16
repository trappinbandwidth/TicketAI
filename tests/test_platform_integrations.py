import pytest

from app.platform.integrations import (
    ConnectorRequest,
    FmcsaQCMobileConnector,
    IntegrationService,
    ManualSourceRecord,
    ReconciliationRequest,
)
from tests.test_platform_identity import FakeDb


def request():
    return ConnectorRequest(
        connector_id="fmcsa_qc_mobile",
        tenant_id="org_carrier",
        resource_type="carrier",
        external_id="44110",
    )


def test_fmcsa_adapter_requires_secret_and_normalizes_dot_without_leaking_key():
    with pytest.raises(RuntimeError, match="FMCSA_WEB_KEY"):
        FmcsaQCMobileConnector(web_key="").fetch(request())

    seen = {}
    connector = FmcsaQCMobileConnector(
        web_key="secret-key",
        transport=lambda url, timeout: seen.update(url=url, timeout=timeout) or {"content": {"carrier": {}}},
    )
    connector.fetch(request())
    assert "/carriers/44110?" in seen["url"]
    assert seen["timeout"] == 8.0


def test_sync_is_idempotent_at_source_record_and_updates_health():
    db = FakeDb()
    connector = FmcsaQCMobileConnector(
        web_key="secret",
        transport=lambda *_: {"content": {"carrier": {"dotNumber": "44110"}}},
    )
    service = IntegrationService(db, {"fmcsa_qc_mobile": connector})

    first_job, first_source = service.run(request(), "prn_admin")
    second_job, second_source = service.run(request(), "prn_admin")

    assert first_job["status"] == "succeeded"
    assert first_job["source_record_created"] is True
    assert second_job["source_record_created"] is False
    assert first_source["id"] == second_source["id"]
    health = next(iter(db.collection("integration_health").rows.values()))
    assert health["status"] == "healthy"


def test_failure_is_observable_and_offers_manual_fallback():
    db = FakeDb()
    connector = FmcsaQCMobileConnector(
        web_key="secret",
        attempts=1,
        transport=lambda *_: (_ for _ in ()).throw(TimeoutError("upstream timeout")),
    )
    service = IntegrationService(db, {"fmcsa_qc_mobile": connector})

    with pytest.raises(RuntimeError, match="bounded retries"):
        service.run(request(), "prn_admin")

    job = next(iter(db.collection("sync_jobs").rows.values()))
    assert job["status"] == "failed"
    assert job["fallback"] == "manual_upload"
    assert next(iter(db.collection("integration_health").rows.values()))["status"] == "degraded"


def test_manual_fallback_keeps_provenance_and_reconciliation_flags_conflicts():
    db = FakeDb()
    service = IntegrationService(db, {})
    base = dict(
        connector_id="fmcsa_qc_mobile",
        tenant_id="org_carrier",
        resource_type="carrier",
        external_id="44110",
        source_reference="FMCSA screenshot SUP-100",
        reason="Provider unavailable",
    )
    _, source = service.submit_manual(
        ManualSourceRecord(**base, payload={"status": "active"}), "prn_admin"
    )
    service.submit_manual(
        ManualSourceRecord(**base, payload={"status": "inactive"}), "prn_admin"
    )

    assert source["provenance"]["provider"] == "manual"
    report = service.reconcile(ReconciliationRequest(
        connector_id="fmcsa_qc_mobile", tenant_id="org_carrier"
    ))
    assert report["status"] == "needs_review"
    assert report["conflict_count"] == 1
