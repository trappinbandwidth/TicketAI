"""WP-06 driver journey orchestration over shared TIP OS services."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.platform.document_service import DocumentService
from app.platform.documents import DocumentStatus, SafeFallbackScanner
from app.platform.intelligence import Evidence, Recommendation, Signal
from app.platform.intelligence_service import IntelligenceService, stable_hash
from app.platform.record_service import DriverCloudService
from app.platform.records import CanonicalRecordCreate, SourceProvenance
from app.platform.workflow_service import WorkflowService
from app.platform.workflows import WorkflowType


def _field_map(run) -> dict:
    return {
        field.field_name: field.corrected_value if field.corrected_value is not None else field.value
        for field in run.fields
    }


def _parse_date(value: str | None):
    if not value:
        return None
    for pattern in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


class DriverResolveService:
    def __init__(self, db):
        self.db = db
        self.documents = DocumentService(db, SafeFallbackScanner())
        self.records = DriverCloudService(db)
        self.workflows = WorkflowService(db)
        self.intelligence = IntelligenceService(db)

    def finalize_verified_extraction(self, actor_id: str, run_id: str):
        run = self.documents.get_extraction(actor_id, run_id)
        asset = self.documents.get_document(actor_id, run.document_id)
        if run.status != "verified" or asset.status != DocumentStatus.VERIFIED:
            raise RuntimeError("Driver must verify extracted facts before finalization.")

        existing = list(
            self.db.collection("canonical_records").where(
                "source_legacy_ref", "==", f"document_extraction_runs/{run.id}"
            ).stream()
        )
        if existing:
            record = self.records.get_record((existing[0].to_dict() or {})["id"])
            workflows = self.workflows.list_for_subject(actor_id)
            workflow = next(item for item in workflows if item.resource_id == record.id)
            return {"record": record, "workflow": workflow, "created": False}

        fields = _field_map(run)
        file_type = fields.get("file_type") or asset.classification or "Ticket"
        is_inspection = "inspection" in str(file_type).lower()
        occurred = _parse_date(
            fields.get("Inspection_Date__c") if is_inspection else fields.get("Date_of_Ticket__c")
        )
        record = self.records.create_record(
            actor_id,
            actor_id,
            CanonicalRecordCreate(
                category="inspection" if is_inspection else "violation",
                record_type="roadside_inspection" if is_inspection else "traffic_citation",
                title=(
                    fields.get("Violation_Description__c")
                    or fields.get("Citation_Number__c")
                    or asset.filename
                ),
                status="verified",
                occurred_at=occurred,
                raw={"document_id": asset.id, "extraction_run_id": run.id},
                normalized=fields,
                derived={},
                provenance=SourceProvenance(
                    source_type="verified_document_extraction",
                    source_name="Driver-verified document",
                    source_record_id=run.id,
                    acquired_at=asset.created_at,
                    method="derived",
                ),
                source_legacy_ref=f"document_extraction_runs/{run.id}",
            ),
        )
        workflow, _ = self.workflows.create(
            actor_id,
            WorkflowType.DATAQS if is_inspection else WorkflowType.TICKET,
            actor_id,
            record.category.value,
            record.id,
        )
        if is_inspection:
            workflow = self.workflows.transition(actor_id, workflow.id, "evidence_collection")
        else:
            workflow = self.workflows.transition(actor_id, workflow.id, "extraction_review")
            workflow = self.workflows.transition(actor_id, workflow.id, "intelligence_ready")

        court_date = _parse_date(fields.get("Court_Date__c"))
        facts = {
            "court_date": court_date.isoformat() if court_date else None,
            "record_id": record.id,
        }
        evaluation = self.intelligence.evaluate_rule(
            "court-deadline-urgency",
            "v1",
            facts,
            lambda item: (
                ("review", "No verified court deadline is available.")
                if not item["court_date"]
                else ("deadline_present", "A driver-verified court deadline is available.")
            ),
        )
        self.intelligence.record_run(
            purpose="driver_intake_finalization",
            provider=run.model_provider,
            model=run.model_name,
            prompt_version=run.prompt_version,
            input_hash=run.input_sha256,
            output_hash=stable_hash(fields),
            rule_evaluation_ids=[evaluation.id],
        )
        if court_date:
            source = Evidence(
                source_type="canonical_record",
                source_id=record.id,
                field="Court_Date__c",
                quote=fields.get("Court_Date__c"),
                retrieved_at=asset.created_at,
                source_version=record.schema_version,
                confidence=1.0,
            )
            signal = Signal(
                id=f"sig_{uuid.uuid4().hex}",
                signal_type="court_deadline",
                subject_principal_id=actor_id,
                resource_type="workflow",
                resource_id=workflow.id,
                severity="high",
                confidence=1.0,
                source_freshness_at=asset.created_at,
                explanation="A driver-verified court date requires timely review.",
                impact_dimensions=["legal", "cdl"],
                evidence=[source],
            )
            self.intelligence.create_signal(signal)
            recommendation = Recommendation(
                id=f"grec_{uuid.uuid4().hex}",
                recommendation_type="attorney_review",
                subject_principal_id=actor_id,
                resource_type="workflow",
                resource_id=workflow.id,
                action="Review attorney assistance options",
                rationale="A verified court deadline is present.",
                alternatives=["Contact the court for procedural information", "Continue gathering records"],
                risks=["Waiting may reduce available options"],
                evidence=[source],
                confidence=0.9,
                required_approver_role="driver",
            )
            self.intelligence.create_recommendation(recommendation)
        return {"record": record, "workflow": workflow, "created": True}
