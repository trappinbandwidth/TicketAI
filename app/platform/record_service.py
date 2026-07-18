"""Persistence and ownership rules for canonical Driver Cloud records."""
from __future__ import annotations

import uuid
from typing import Optional

from app.platform.models import utc_now
from app.platform.records import (
    CanonicalRecord,
    CanonicalRecordCreate,
    RecordActivity,
    raw_payload_hash,
)


def _serialize(model):
    return model.model_dump(mode="json")


class DriverCloudService:
    def __init__(self, db):
        self.db = db

    def _activity(
        self,
        record: CanonicalRecord,
        actor_id: str,
        event_type: str,
        changed_fields: Optional[list[str]] = None,
        metadata: Optional[dict] = None,
    ) -> RecordActivity:
        activity = RecordActivity(
            id=f"ract_{uuid.uuid4().hex}",
            record_id=record.id,
            subject_principal_id=record.subject_principal_id,
            event_type=event_type,
            actor_principal_id=actor_id,
            record_version=record.record_version,
            changed_fields=changed_fields or [],
            metadata=metadata or {},
        )
        self.db.collection("canonical_record_activity").document(activity.id).set(_serialize(activity))
        return activity

    def create_record(
        self,
        actor_id: str,
        subject_principal_id: str,
        body: CanonicalRecordCreate,
    ) -> CanonicalRecord:
        if actor_id != subject_principal_id:
            raise PermissionError("Drivers may only create records in their own Driver Cloud.")
        record = CanonicalRecord(
            id=f"rec_{uuid.uuid4().hex}",
            subject_principal_id=subject_principal_id,
            created_by=actor_id,
            raw_sha256=raw_payload_hash(body.raw),
            **body.model_dump(),
        )
        self.db.collection("canonical_records").document(record.id).set(_serialize(record))
        self._activity(record, actor_id, "record.created")
        return record

    def get_record(self, record_id: str) -> Optional[CanonicalRecord]:
        snapshot = self.db.collection("canonical_records").document(record_id).get()
        if not getattr(snapshot, "exists", False):
            return None
        return CanonicalRecord.model_validate(snapshot.to_dict())

    def list_records(self, subject_principal_id: str) -> list[CanonicalRecord]:
        snapshots = self.db.collection("canonical_records").where(
            "subject_principal_id", "==", subject_principal_id
        ).stream()
        records = [CanonicalRecord.model_validate(item.to_dict()) for item in snapshots]
        return sorted(records, key=lambda item: item.updated_at, reverse=True)

    def list_activity(self, subject_principal_id: str) -> list[RecordActivity]:
        snapshots = self.db.collection("canonical_record_activity").where(
            "subject_principal_id", "==", subject_principal_id
        ).stream()
        activity = [RecordActivity.model_validate(item.to_dict()) for item in snapshots]
        return sorted(activity, key=lambda item: item.created_at, reverse=True)

    def update_record(
        self,
        actor_id: str,
        record_id: str,
        expected_version: int,
        body: CanonicalRecordCreate,
    ) -> CanonicalRecord:
        current = self.get_record(record_id)
        if current is None:
            raise LookupError("Canonical record not found.")
        if current.subject_principal_id != actor_id:
            raise PermissionError("Driver Cloud record access denied.")
        if current.record_version != expected_version:
            raise RuntimeError("Record version conflict.")

        previous = current.model_dump()
        next_values = body.model_dump()
        changed_fields = sorted(
            key for key, value in next_values.items() if previous.get(key) != value
        )
        updated = CanonicalRecord(
            **{
                **previous,
                **next_values,
                "record_version": current.record_version + 1,
                "raw_sha256": raw_payload_hash(body.raw),
                "updated_at": utc_now(),
            }
        )
        self.db.collection("canonical_records").document(record_id).set(_serialize(updated))
        self._activity(updated, actor_id, "record.updated", changed_fields)
        return updated
