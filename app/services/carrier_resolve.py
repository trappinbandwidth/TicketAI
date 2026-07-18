"""WP-08 consent-limited Carrier and Safety projections."""
from __future__ import annotations

from app.platform.intelligence_service import IntelligenceService
from app.platform.models import ConsentStatus, MembershipStatus, RelationshipStatus
from app.platform.record_service import DriverCloudService
from app.platform.service import PlatformService, relationship_id_for_parties
from app.platform.workflow_service import WorkflowService


SAFETY_RECORD_CATEGORIES = {"profile", "credential", "employment", "inspection"}
SAFETY_WORKFLOW_TYPES = {"credential", "dataqs"}
SAFETY_IMPACTS = {"safety", "compliance", "credential", "employment"}


class CarrierResolveService:
    def __init__(self, db):
        self.db = db
        self.platform = PlatformService(db)
        self.records = DriverCloudService(db)
        self.workflows = WorkflowService(db)
        self.intelligence = IntelligenceService(db)

    def _authorize(self, actor_id: str, organization_id: str, driver_id: str):
        membership = next(
            (
                item for item in self.platform.list_memberships(actor_id)
                if item.organization_id == organization_id
                and item.status == MembershipStatus.ACTIVE
            ),
            None,
        )
        if membership is None:
            raise PermissionError("Active carrier organization membership required.")
        relationship_id = relationship_id_for_parties(organization_id, driver_id)
        snapshot = self.db.collection("driver_carrier_relationships").document(
            relationship_id
        ).get()
        if not getattr(snapshot, "exists", False):
            raise PermissionError("Active driver relationship required.")
        relationship = snapshot.to_dict() or {}
        if relationship.get("status") != RelationshipStatus.ACTIVE.value:
            raise PermissionError("Active driver relationship required.")
        consent = next(
            (
                item for item in self.platform.list_consents(driver_id)
                if item.recipient_organization_id == organization_id
                and item.status == ConsentStatus.ACTIVE
                and item.purpose == "safety_compliance"
            ),
            None,
        )
        if consent is None:
            raise PermissionError("Active driver safety consent required.")
        return membership, consent

    def driver_summary(self, actor_id: str, organization_id: str, driver_id: str):
        _, consent = self._authorize(actor_id, organization_id, driver_id)
        allowed_categories = SAFETY_RECORD_CATEGORIES & set(consent.record_categories)
        records = [
            item for item in self.records.list_records(driver_id)
            if item.category.value in allowed_categories
            and item.sharing_scope.value in {"consented", "private"}
        ]
        workflows = [
            item for item in self.workflows.list_for_subject(driver_id)
            if item.workflow_type.value in SAFETY_WORKFLOW_TYPES
        ]
        tasks = [
            task
            for workflow in workflows
            for task in self.workflows.list_tasks(workflow.id)
        ]
        signals = [
            item for item in self.intelligence.list_signals(driver_id)
            if set(item.impact_dimensions) & SAFETY_IMPACTS
        ]
        return {
            "driver_principal_id": driver_id,
            "consent_id": consent.id,
            "records": records,
            "workflows": workflows,
            "tasks": tasks,
            "signals": signals,
        }
