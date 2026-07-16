"""Idempotent WP-01 profile-link backfill and reconciliation planning."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from typing import Iterable, Optional

from app.platform.models import Principal
from app.platform.service import mask_email, mask_phone, principal_id_for_uid


MIGRATION_VERSION = "tip-os-wp01-v1"
ROLE_COLLECTIONS = {
    "driver": "drivers",
    "attorney": "attorneys",
    "carrier": "carriers",
}


@dataclass(frozen=True)
class ProfileRecord:
    collection: str
    document_id: str
    data: dict


@dataclass(frozen=True)
class BackfillAction:
    collection: str
    document_id: str
    role: str
    principal_id: str
    outcome: str
    reason: str

    def safe_dict(self) -> dict:
        data = asdict(self)
        data["profile_ref"] = hashlib.sha256(
            f"{self.collection}:{self.document_id}".encode("utf-8")
        ).hexdigest()[:20]
        del data["document_id"]
        return data


@dataclass
class BackfillReport:
    scanned: int = 0
    create: int = 0
    link: int = 0
    unchanged: int = 0
    conflict: int = 0
    invalid: int = 0
    actions: list[BackfillAction] = None

    def __post_init__(self):
        if self.actions is None:
            self.actions = []

    def safe_dict(self) -> dict:
        return {
            "migration_version": MIGRATION_VERSION,
            "scanned": self.scanned,
            "create": self.create,
            "link": self.link,
            "unchanged": self.unchanged,
            "conflict": self.conflict,
            "invalid": self.invalid,
            "actions": [action.safe_dict() for action in self.actions],
        }


def _role_for_collection(collection: str) -> Optional[str]:
    for role, name in ROLE_COLLECTIONS.items():
        if name == collection:
            return role
    return None


def plan_profile_backfill(
    profiles: Iterable[ProfileRecord],
    existing_principals: dict[str, dict],
) -> BackfillReport:
    """Plan without mutation and without emitting profile PII in the report."""
    report = BackfillReport()
    seen_uids: dict[str, tuple[str, str]] = {}

    for profile in profiles:
        report.scanned += 1
        role = _role_for_collection(profile.collection)
        if role is None or not profile.document_id:
            report.invalid += 1
            report.actions.append(BackfillAction(
                profile.collection, profile.document_id or "missing", role or "unknown", "", "invalid",
                "unsupported_collection_or_missing_document_id",
            ))
            continue

        uid = profile.document_id
        principal_id = principal_id_for_uid(uid)
        current_link = profile.data.get("principal_id")
        prior = seen_uids.get(uid)
        if prior and prior != (profile.collection, profile.document_id):
            report.conflict += 1
            report.actions.append(BackfillAction(
                profile.collection, profile.document_id, role, principal_id, "conflict", "uid_reused_across_role_profiles",
            ))
            continue
        seen_uids[uid] = (profile.collection, profile.document_id)

        if current_link and current_link != principal_id:
            report.conflict += 1
            report.actions.append(BackfillAction(
                profile.collection, profile.document_id, role, principal_id, "conflict", "profile_link_mismatch",
            ))
            continue

        existing = existing_principals.get(principal_id)
        if existing and existing.get("firebase_uid") != uid:
            report.conflict += 1
            report.actions.append(BackfillAction(
                profile.collection, profile.document_id, role, principal_id, "conflict", "principal_uid_mismatch",
            ))
            continue

        if existing and current_link == principal_id:
            report.unchanged += 1
            report.actions.append(BackfillAction(
                profile.collection, profile.document_id, role, principal_id, "unchanged", "already_linked",
            ))
        elif existing:
            report.link += 1
            report.actions.append(BackfillAction(
                profile.collection, profile.document_id, role, principal_id, "link", "principal_exists",
            ))
        else:
            report.create += 1
            report.actions.append(BackfillAction(
                profile.collection, profile.document_id, role, principal_id, "create", "principal_missing",
            ))

    return report


def principal_from_profile(action: BackfillAction, profile_data: dict) -> Principal:
    """Build only the minimum canonical projection; raw identifiers are not copied."""
    return Principal(
        id=action.principal_id,
        firebase_uid=action.document_id,
        display_name=profile_data.get("name") or profile_data.get("full_name") or profile_data.get("company_name"),
        email_masked=mask_email(profile_data.get("email")),
        phone_masked=mask_phone(profile_data.get("phone") or profile_data.get("phone_number")),
        role_profile_refs={action.role: action.document_id},
    )


def apply_profile_backfill(db, report: BackfillReport, profile_lookup: dict[tuple[str, str], dict]) -> dict:
    """Apply only non-conflicting planned actions; safe to rerun."""
    applied = 0
    skipped = 0
    for action in report.actions:
        if action.outcome not in {"create", "link"}:
            skipped += 1
            continue
        profile_data = profile_lookup[(action.collection, action.document_id)]
        if action.outcome == "create":
            principal = principal_from_profile(action, profile_data)
            db.collection("principals").document(action.principal_id).set(principal.model_dump(mode="json"))
        db.collection(action.collection).document(action.document_id).set({
            "principal_id": action.principal_id,
            "migration_version": MIGRATION_VERSION,
            "migration_previous_principal_id": profile_data.get("principal_id"),
        }, merge=True)
        applied += 1
    return {"applied": applied, "skipped": skipped, "migration_version": MIGRATION_VERSION}


def write_migration_run(db, report: BackfillReport, apply_result: dict, actor: str = "cli") -> str:
    """Write a PII-minimized apply audit with rollback metadata location."""
    import uuid
    from app.platform.models import utc_now

    run_id = f"migration_{uuid.uuid4().hex}"
    db.collection("migration_runs").document(run_id).set({
        "id": run_id,
        "migration_version": MIGRATION_VERSION,
        "actor": actor,
        "mode": "apply",
        "counts": {
            "scanned": report.scanned,
            "create": report.create,
            "link": report.link,
            "unchanged": report.unchanged,
            "conflict": report.conflict,
            "invalid": report.invalid,
            "applied": apply_result.get("applied", 0),
            "skipped": apply_result.get("skipped", 0),
        },
        "rollback": {
            "profile_field": "migration_previous_principal_id",
            "version_field": "migration_version",
            "automatic_rollback": False,
        },
        "created_at": utc_now().isoformat(),
    })
    return run_id
