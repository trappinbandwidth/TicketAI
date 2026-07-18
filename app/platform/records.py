"""WP-02 canonical Driver Cloud record contracts."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from app.platform.models import utc_now


class RecordCategory(str, Enum):
    PROFILE = "profile"
    CREDENTIAL = "credential"
    DOCUMENT = "document"
    EMPLOYMENT = "employment"
    INSPECTION = "inspection"
    VIOLATION = "violation"
    CASE = "case"
    TRAINING = "training"
    MONITORING = "monitoring"


class RecordStatus(str, Enum):
    DRAFT = "draft"
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    SUPERSEDED = "superseded"
    DISPUTED = "disputed"
    EXPIRED = "expired"


class SharingScope(str, Enum):
    PRIVATE = "private"
    CONSENTED = "consented"
    LEGAL_TEAM = "legal_team"


class SourceProvenance(BaseModel):
    source_type: str = Field(min_length=1, max_length=80)
    source_name: str = Field(min_length=1, max_length=160)
    source_record_id: Optional[str] = Field(default=None, max_length=240)
    acquired_at: datetime = Field(default_factory=utc_now)
    effective_at: Optional[datetime] = None
    freshness_at: Optional[datetime] = None
    method: str = Field(default="manual", pattern="^(manual|upload|connector|migration|derived)$")
    provider_terms_version: Optional[str] = Field(default=None, max_length=80)


class CanonicalRecordCreate(BaseModel):
    category: RecordCategory
    record_type: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=240)
    status: RecordStatus = RecordStatus.UNVERIFIED
    occurred_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    raw: dict[str, Any] = Field(default_factory=dict)
    normalized: dict[str, Any] = Field(default_factory=dict)
    derived: dict[str, Any] = Field(default_factory=dict)
    provenance: SourceProvenance
    sharing_scope: SharingScope = SharingScope.PRIVATE
    source_legacy_ref: Optional[str] = Field(default=None, max_length=300)

    @field_validator("record_type", "title")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return " ".join(value.split())


class CanonicalRecord(CanonicalRecordCreate):
    id: str
    subject_principal_id: str
    schema_version: str = "driver-cloud-v1"
    record_version: int = 1
    raw_sha256: str
    created_by: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RecordActivity(BaseModel):
    id: str
    record_id: str
    subject_principal_id: str
    event_type: str
    actor_principal_id: str
    record_version: int
    changed_fields: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


def raw_payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
