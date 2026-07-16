"""Canonical WP-01 identity, organization, membership, and consent contracts."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PrincipalStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    REVIEW = "review"


class OrganizationType(str, Enum):
    CARRIER = "carrier"
    LAW_FIRM = "law_firm"
    PARTNER = "partner"
    INTERNAL = "internal"


class MembershipStatus(str, Enum):
    INVITED = "invited"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ENDED = "ended"


class ConsentStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class Principal(BaseModel):
    id: str
    firebase_uid: str
    status: PrincipalStatus = PrincipalStatus.ACTIVE
    assurance_level: str = "authenticated"
    display_name: Optional[str] = None
    email_masked: Optional[str] = None
    phone_masked: Optional[str] = None
    role_profile_refs: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class OrganizationCreate(BaseModel):
    type: OrganizationType
    legal_name: str = Field(min_length=1, max_length=200)
    display_name: Optional[str] = Field(default=None, max_length=200)
    external_identifiers: dict[str, str] = Field(default_factory=dict)

    @field_validator("legal_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.split())


class Organization(BaseModel):
    id: str
    type: OrganizationType
    legal_name: str
    display_name: Optional[str] = None
    external_identifiers: dict[str, str] = Field(default_factory=dict)
    verification_status: str = "pending"
    tenant_status: str = "pending"
    created_by: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class MembershipCreate(BaseModel):
    principal_id: str
    role: str = Field(min_length=1, max_length=80)
    terminal_ids: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    status: MembershipStatus = MembershipStatus.INVITED
    effective_at: datetime = Field(default_factory=utc_now)
    expires_at: Optional[datetime] = None


class Membership(BaseModel):
    id: str
    organization_id: str
    principal_id: str
    role: str
    terminal_ids: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    status: MembershipStatus
    effective_at: datetime
    expires_at: Optional[datetime] = None
    created_by: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ConsentGrantCreate(BaseModel):
    subject_principal_id: str
    recipient_principal_id: Optional[str] = None
    recipient_organization_id: Optional[str] = None
    purpose: str = Field(min_length=1, max_length=120)
    record_categories: list[str] = Field(min_length=1)
    actions: list[str] = Field(default_factory=lambda: ["read"])
    disclosure_version: str = Field(min_length=1, max_length=80)
    expires_at: Optional[datetime] = None
    related_resource_type: Optional[str] = None
    related_resource_id: Optional[str] = None

    @model_validator(mode="after")
    def recipient_required(self):
        if not self.recipient_principal_id and not self.recipient_organization_id:
            raise ValueError("A recipient principal or organization is required.")
        return self


class ConsentGrant(BaseModel):
    id: str
    grantor_principal_id: str
    subject_principal_id: str
    recipient_principal_id: Optional[str] = None
    recipient_organization_id: Optional[str] = None
    purpose: str
    record_categories: list[str]
    actions: list[str]
    disclosure_version: str
    status: ConsentStatus = ConsentStatus.ACTIVE
    effective_at: datetime = Field(default_factory=utc_now)
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revocation_reason: Optional[str] = None
    related_resource_type: Optional[str] = None
    related_resource_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AuthorizationRequest(BaseModel):
    action: str
    resource_type: str
    resource_id: str
    tenant_id: Optional[str] = None
    purpose: Optional[str] = None
    record_category: Optional[str] = None
    subject_principal_id: Optional[str] = None
    terminal_id: Optional[str] = None


class AuthorizationDecision(BaseModel):
    allowed: bool
    reason: str
    policy_version: str = "wp01-v1"
    membership_id: Optional[str] = None
    consent_id: Optional[str] = None
