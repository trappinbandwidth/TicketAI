from datetime import datetime, timezone

import pytest

from app.platform.intelligence import Evidence, Signal
from app.platform.intelligence_service import IntelligenceService
from app.platform.models import (
    ConsentGrant,
    DriverCarrierRelationship,
    Membership,
    MembershipStatus,
    RelationshipStatus,
    utc_now,
)
from app.platform.record_service import DriverCloudService
from app.platform.records import CanonicalRecordCreate, SourceProvenance
from app.platform.workflow_service import WorkflowService
from app.platform.workflows import WorkflowTaskCreate, WorkflowType
from app.services.carrier_resolve import CarrierResolveService
from tests.test_platform_identity import FakeDb


def setup_access(db):
    membership = Membership(
        id="mem_1", organization_id="org_carrier", principal_id="prn_safety",
        role="safety_manager", status=MembershipStatus.ACTIVE,
        effective_at=utc_now(), created_by="prn_admin",
    )
    relationship = DriverCarrierRelationship(
        id="rel_51e5478ad3bc163b3549facbfc9f2a03",
        driver_principal_id="prn_driver", carrier_organization_id="org_carrier",
        relationship_type="employee", status=RelationshipStatus.ACTIVE,
        invited_by_principal_id="prn_safety",
    )
    # Use the production stable relationship identifier.
    from app.platform.service import relationship_id_for_parties
    relationship.id = relationship_id_for_parties("org_carrier", "prn_driver")
    consent = ConsentGrant(
        id="cns_1", grantor_principal_id="prn_driver",
        subject_principal_id="prn_driver", recipient_organization_id="org_carrier",
        purpose="safety_compliance",
        record_categories=["profile", "credential", "employment", "inspection"],
        actions=["read"], disclosure_version="safety-v1",
    )
    db.collection("organization_memberships").document(membership.id).set(membership.model_dump(mode="json"))
    db.collection("driver_carrier_relationships").document(relationship.id).set(relationship.model_dump(mode="json"))
    db.collection("consent_grants").document(consent.id).set(consent.model_dump(mode="json"))


def test_carrier_summary_requires_membership_relationship_and_consent():
    db = FakeDb()
    with pytest.raises(PermissionError, match="membership"):
        CarrierResolveService(db).driver_summary("prn_safety", "org_carrier", "prn_driver")


def test_carrier_summary_excludes_legal_records_workflows_and_signals():
    db = FakeDb()
    setup_access(db)
    records = DriverCloudService(db)
    provenance = SourceProvenance(
        source_type="driver", source_name="Driver", method="manual",
        acquired_at=datetime.now(timezone.utc),
    )
    records.create_record(
        "prn_driver", "prn_driver",
        CanonicalRecordCreate(
            category="credential", record_type="cdl", title="CDL",
            normalized={"expires": "2026-08-01"}, provenance=provenance,
        ),
    )
    records.create_record(
        "prn_driver", "prn_driver",
        CanonicalRecordCreate(
            category="case", record_type="legal_case", title="Privileged case",
            normalized={"attorney_note": "private"}, provenance=provenance,
            sharing_scope="legal_team",
        ),
    )
    workflows = WorkflowService(db)
    credential, _ = workflows.create(
        "prn_driver", WorkflowType.CREDENTIAL, "prn_driver", "credential", "cred_1"
    )
    legal_case, _ = workflows.create(
        "prn_driver", WorkflowType.CASE, "prn_driver", "case", "case_1"
    )
    workflows.create_task(
        "prn_safety", credential.id, WorkflowTaskCreate(title="Upload renewed CDL")
    )
    evidence = Evidence(
        source_type="canonical_record", source_id="cred_1",
        retrieved_at=datetime.now(timezone.utc), confidence=1,
    )
    intelligence = IntelligenceService(db)
    intelligence.create_signal(Signal(
        id="sig_safety", signal_type="credential_expiry", subject_principal_id="prn_driver",
        resource_type="credential", resource_id="cred_1", severity="high", confidence=1,
        source_freshness_at=datetime.now(timezone.utc), explanation="CDL expiring",
        impact_dimensions=["safety", "credential"], evidence=[evidence],
    ))
    intelligence.create_signal(Signal(
        id="sig_legal", signal_type="defense_strategy", subject_principal_id="prn_driver",
        resource_type="case", resource_id="case_1", severity="medium", confidence=.8,
        source_freshness_at=datetime.now(timezone.utc), explanation="Privileged legal issue",
        impact_dimensions=["legal"], evidence=[evidence],
    ))

    summary = CarrierResolveService(db).driver_summary(
        "prn_safety", "org_carrier", "prn_driver"
    )

    assert [item.category.value for item in summary["records"]] == ["credential"]
    assert [item.id for item in summary["workflows"]] == [credential.id]
    assert [item.title for item in summary["tasks"]] == ["Upload renewed CDL"]
    assert [item.id for item in summary["signals"]] == ["sig_safety"]
    assert legal_case.id not in {item.id for item in summary["workflows"]}
