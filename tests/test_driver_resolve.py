from app.platform.document_service import DocumentService
from app.platform.documents import ExtractionField, ScanResult
from app.services.driver_resolve import DriverResolveService
from tests.test_platform_identity import FakeDb


class CleanScanner:
    def scan(self, content):
        return ScanResult.CLEAN


def verified_run(db):
    documents = DocumentService(db, CleanScanner())
    asset = documents.ingest(
        "prn_driver", "ticket.pdf", "application/pdf", b"%PDF verified"
    )
    run = documents.start_extraction(
        "prn_driver",
        asset.id,
        [
            ExtractionField(
                field_name="Citation_Number__c", value="ABC123", confidence=.9
            ),
            ExtractionField(
                field_name="Violation_Description__c", value="Speeding", confidence=.8
            ),
            ExtractionField(
                field_name="Date_of_Ticket__c", value="07/01/2026", confidence=.9
            ),
            ExtractionField(
                field_name="Court_Date__c", value="08/01/2026", confidence=.9
            ),
        ],
        classifier_version="v1",
        extractor_version="v2",
        model_provider="anthropic",
        model_name="configured-claude",
        prompt_version="v2",
    )
    return documents.verify_extraction("prn_driver", run.id, {})


def test_verified_ticket_finalizes_into_records_workflow_rules_and_reviewable_intelligence():
    db = FakeDb()
    run = verified_run(db)

    result = DriverResolveService(db).finalize_verified_extraction("prn_driver", run.id)

    assert result["created"] is True
    assert result["record"].category.value == "violation"
    assert result["record"].normalized["Citation_Number__c"] == "ABC123"
    assert result["workflow"].current_state == "intelligence_ready"
    assert len(db.collection("rule_evaluations").rows) == 1
    assert len(db.collection("intelligence_runs").rows) == 1
    assert len(db.collection("signals").rows) == 1
    recommendation = next(iter(db.collection("governed_recommendations").rows.values()))
    assert recommendation["status"] == "pending_review"


def test_unverified_extraction_cannot_finalize():
    db = FakeDb()
    documents = DocumentService(db, CleanScanner())
    asset = documents.ingest("prn_driver", "ticket.pdf", "application/pdf", b"%PDF pending")
    run = documents.start_extraction(
        "prn_driver", asset.id, [],
        classifier_version="v1", extractor_version="v2",
        model_provider="openai", model_name="configured-openai", prompt_version="v2",
    )

    try:
        DriverResolveService(db).finalize_verified_extraction("prn_driver", run.id)
        assert False, "finalization should have failed"
    except RuntimeError as exc:
        assert "must verify" in str(exc)


def test_finalization_is_idempotent():
    db = FakeDb()
    run = verified_run(db)
    service = DriverResolveService(db)

    first = service.finalize_verified_extraction("prn_driver", run.id)
    second = service.finalize_verified_extraction("prn_driver", run.id)

    assert first["record"].id == second["record"].id
    assert second["created"] is False
    assert len(db.collection("canonical_records").rows) == 1
