"""Pure planning helpers for WP-02 legacy ticket projections."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from app.platform.models import utc_now
from app.platform.records import CanonicalRecordCreate, SourceProvenance
from app.platform.service import principal_id_for_uid


MIGRATION_VERSION = "tip-os-wp02-v1"


@dataclass(frozen=True)
class LegacyTicket:
    document_id: str
    data: dict


@dataclass(frozen=True)
class RecordProjection:
    record_id: str
    legacy_ticket_id: str
    subject_principal_id: str
    outcome: str
    body: CanonicalRecordCreate | None
    reason: str

    def safe_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "legacy_ref": hashlib.sha256(self.legacy_ticket_id.encode()).hexdigest()[:20],
            "outcome": self.outcome,
            "reason": self.reason,
        }


def record_id_for_ticket(ticket_id: str) -> str:
    digest = hashlib.sha256(f"ticket:{ticket_id}".encode()).hexdigest()[:32]
    return f"rec_{digest}"


def normalize_legacy_datetime(value) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    cleaned = value.strip()
    try:
        parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    for pattern in ("%m/%d/%Y", "%m/%d/%Y %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def project_ticket(ticket: LegacyTicket, existing: dict | None = None) -> RecordProjection:
    data = ticket.data
    record_id = record_id_for_ticket(ticket.document_id)
    driver_id = data.get("driver_id") or data.get("DriverId")
    if not driver_id:
        return RecordProjection(record_id, ticket.document_id, "", "invalid", None, "missing_driver_id")
    subject_id = principal_id_for_uid(str(driver_id))
    if existing:
        if existing.get("source_legacy_ref") != f"tickets/{ticket.document_id}":
            return RecordProjection(
                record_id, ticket.document_id, subject_id, "conflict", None, "stable_id_legacy_ref_mismatch"
            )
        return RecordProjection(record_id, ticket.document_id, subject_id, "unchanged", None, "already_projected")

    occurred_at = normalize_legacy_datetime(data.get("date_of_ticket") or data.get("created_at"))
    acquired_at = normalize_legacy_datetime(
        data.get("created_at") or data.get("last_modified_date")
    ) or utc_now()
    normalized = {
        "citation_number": data.get("citation_number"),
        "violation_category": data.get("violation_category"),
        "violation_description": data.get("violation_description"),
        "state": data.get("ticket_state"),
        "county": data.get("ticket_county"),
        "city": data.get("ticket_city"),
        "court_date": data.get("court_date"),
        "case_status": data.get("attorney_status"),
    }
    normalized = {key: value for key, value in normalized.items() if value not in (None, "")}
    body = CanonicalRecordCreate(
        category="violation",
        record_type="traffic_citation",
        title=data.get("violation_description") or data.get("violation_category") or "Traffic citation",
        status="verified" if data.get("pass_status") == "GREEN" else "unverified",
        occurred_at=occurred_at,
        raw=dict(data),
        normalized=normalized,
        derived={
            key: value
            for key, value in {
                "price_low": data.get("price_low"),
                "price_high": data.get("price_high"),
                "pass_status": data.get("pass_status"),
            }.items()
            if value not in (None, "")
        },
        provenance=SourceProvenance(
            source_type="legacy_ticket",
            source_name="Rig Resolve ticket system",
            source_record_id=ticket.document_id,
            method="migration",
            acquired_at=acquired_at,
        ),
        sharing_scope="private",
        source_legacy_ref=f"tickets/{ticket.document_id}",
    )
    return RecordProjection(record_id, ticket.document_id, subject_id, "create", body, "legacy_ticket")


def plan_ticket_projections(
    tickets: Iterable[LegacyTicket], existing_records: dict[str, dict]
) -> list[RecordProjection]:
    return [
        project_ticket(ticket, existing_records.get(record_id_for_ticket(ticket.document_id)))
        for ticket in tickets
    ]
