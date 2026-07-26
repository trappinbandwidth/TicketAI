#!/usr/bin/env python3
"""Seed one reversible Driver ↔ Carrier ↔ Attorney TIP Score journey locally.

Emulator-only and idempotent. The same Ada Lovelace identity appears in:
Driver (`+15125550101`), Big Rig Freight Carrier (`safety@bigrig.local`), and
Dana Whitfield Attorney (`anchor@firm.local`).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

if not os.getenv("FIRESTORE_EMULATOR_HOST"):
    sys.exit("Refusing to seed: FIRESTORE_EMULATOR_HOST is not set (emulator only).")

# Run from anywhere while importing the selected Engine worktree.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import firebase_admin
from firebase_admin import auth as fb_auth, firestore

from app.platform.models import (
    ConsentGrant,
    DriverCarrierRelationship,
    Membership,
    MembershipStatus,
    Organization,
    OrganizationType,
    Principal,
    RelationshipStatus,
)
from app.platform.service import (
    membership_id_for_principal,
    organization_id_for_profile,
    principal_id_for_uid,
    relationship_id_for_parties,
)
from app.services.firebase_service import _emulator_credential
from app.services.tip_score import (
    ComponentInput,
    ConfidenceInput,
    ScoreCalculationInput,
    TipComponent,
    TipScoreCalculator,
    TipScoreStatus,
)


PROJECT = os.getenv("FIREBASE_PROJECT_ID", "rigresolve-local")
if not firebase_admin._apps:
    firebase_admin.initialize_app(_emulator_credential(), {"projectId": PROJECT})
db = firestore.client()
now = datetime.now(timezone.utc)

driver_uid = "drv_lovelace"
carrier_uid = "car_bigrig"
attorney_uid = "att_anchor"
driver_id = principal_id_for_uid(driver_uid)
carrier_id = principal_id_for_uid(carrier_uid)
attorney_id = principal_id_for_uid(attorney_uid)
organization_id = organization_id_for_profile("carrier", carrier_uid)
relationship_id = relationship_id_for_parties(organization_id, driver_id)

# Seeded email users are pre-verified so the local journey starts at the
# authenticated portal rather than an external email-link step.
fb_auth.update_user(carrier_uid, email_verified=True)
fb_auth.update_user(attorney_uid, email_verified=True)


def put(collection: str, document_id: str, model) -> None:
    db.collection(collection).document(document_id).set(
        model.model_dump(mode="json"), merge=True
    )


for uid, principal_id, role, name in (
    (driver_uid, driver_id, "driver", "Ada Lovelace"),
    (carrier_uid, carrier_id, "carrier", "Big Rig Freight Co"),
    (attorney_uid, attorney_id, "attorney", "Dana Whitfield"),
):
    put(
        "principals",
        principal_id,
        Principal(
            id=principal_id,
            firebase_uid=uid,
            display_name=name,
            role_profile_refs={role: uid},
        ),
    )

put(
    "organizations",
    organization_id,
    Organization(
        id=organization_id,
        type=OrganizationType.CARRIER,
        legal_name="Big Rig Freight Co",
        display_name="Big Rig Freight Co",
        external_identifiers={"usdot": "1234567"},
        verification_status="verified",
        tenant_status="active",
        created_by=carrier_id,
    ),
)
membership_id = membership_id_for_principal(organization_id, carrier_id)
put(
    "organization_memberships",
    membership_id,
    Membership(
        id=membership_id,
        organization_id=organization_id,
        principal_id=carrier_id,
        role="carrier_admin",
        status=MembershipStatus.ACTIVE,
        effective_at=now,
        created_by=carrier_id,
    ),
)
put(
    "driver_carrier_relationships",
    relationship_id,
    DriverCarrierRelationship(
        id=relationship_id,
        driver_principal_id=driver_id,
        carrier_organization_id=organization_id,
        relationship_type="employee",
        status=RelationshipStatus.ACTIVE,
        invited_by_principal_id=carrier_id,
        responded_at=now,
    ),
)
consent_id = f"cns_tip_journey_{driver_uid}"
put(
    "consent_grants",
    consent_id,
    ConsentGrant(
        id=consent_id,
        grantor_principal_id=driver_id,
        subject_principal_id=driver_id,
        recipient_organization_id=organization_id,
        purpose="safety_compliance",
        record_categories=["profile", "credential", "employment", "inspection"],
        actions=["read"],
        disclosure_version="carrier-safety-pilot-v1",
        related_resource_type="driver_carrier_relationship",
        related_resource_id=relationship_id,
    ),
)

score_input = ScoreCalculationInput(
    driver_id=driver_id,
    components={
        TipComponent.UNSAFE_DRIVING: ComponentInput(
            risk=0.30, event_count=1, verified_event_count=1,
            top_factors=["One recent verified speeding event"],
        ),
        TipComponent.CRASH: ComponentInput(
            risk=0.10, top_factors=["No preventable crash pattern observed"],
        ),
        TipComponent.HOURS_OF_SERVICE: ComponentInput(
            risk=0.40, event_count=1, verified_event_count=1,
            top_factors=["Hours-of-service record needs review"],
        ),
        TipComponent.DRIVER_FITNESS: ComponentInput(
            risk=0.20, top_factors=["Credentials verified and current"],
        ),
        TipComponent.SUBSTANCE_ALCOHOL: ComponentInput(
            risk=0.00, top_factors=["No score-affecting verified event"],
        ),
        TipComponent.SAFETY_MANAGEMENT: ComponentInput(
            risk=0.25, verified_event_count=2,
            top_factors=["Verified clean operating period"],
        ),
    },
    confidence=ConfidenceInput(
        source_completeness=0.85,
        identity_match_quality=1.0,
        record_freshness=0.90,
        credential_verification=1.0,
        exposure_sufficiency=0.75,
    ),
    status=TipScoreStatus.OFFICIAL,
    data_as_of=now,
    verified_history_months=24,
    verified_inspections=2,
    evidence_ids=["evt_speeding_verified", "evt_hos_verified"],
    calculation_reason="local cross-portal journey seed",
)
snapshot = TipScoreCalculator().calculate(score_input, calculated_at=now)
put("tip_score_snapshots", snapshot.id, snapshot)
put("tip_score_current", driver_id, snapshot)

db.collection("drivers").document(driver_uid).set(
    {"principal_id": driver_id, "carrier_id": carrier_uid}, merge=True
)
db.collection("carriers").document(carrier_uid).set(
    {"organization_id": organization_id, "principal_id": carrier_id}, merge=True
)
db.collection("attorneys").document(attorney_uid).set(
    {"principal_id": attorney_id, "verification_status": "verified"}, merge=True
)
db.collection("tickets").document("TX-2026-441").set(
    {
        "assigned_attorney_id": attorney_uid,
        "driver_id": driver_uid,
        "driver_full_name": "Ada Lovelace",
        "tip_score_consent_on_file": True,
        "attorney_status": "Accepted",
    },
    merge=True,
)

print("Seeded shared TIP Score journey:")
print(f"  Driver: Ada Lovelace / +15125550101 / principal {driver_id}")
print("  Carrier: Big Rig Freight Co / safety@bigrig.local")
print("  Attorney: Dana Whitfield / anchor@firm.local")
print(f"  TIP Score: {snapshot.score} {snapshot.tier.value} / {snapshot.confidence_percent}% confidence")
