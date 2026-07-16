"""Feature-flagged TIP OS WP-01 platform endpoints."""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.platform.models import (
    AuthorizationRequest,
    ConsentGrantCreate,
    MembershipCreate,
    OrganizationCreate,
)
from app.platform.service import PlatformService, evaluate_authorization, principal_id_for_uid
from app.services.auth_rbac import STAFF_ROLES, verify_firebase_token


router = APIRouter(prefix="/platform", tags=["tip-os-platform"])


class RevokeConsentRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


def _enabled() -> None:
    if os.getenv("TIP_OS_IDENTITY_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="TIP OS identity APIs are not enabled.")


def _service() -> PlatformService:
    from app.services.firebase_service import _firestore_client, _init

    _init()
    if _firestore_client is None:
        raise HTTPException(status_code=503, detail="Identity store unavailable.")
    return PlatformService(_firestore_client)


def _claims(authorization: Optional[str]) -> dict:
    _enabled()
    return verify_firebase_token(authorization)


def _actor_id(claims: dict) -> str:
    uid = claims.get("uid") or claims.get("sub")
    if not uid:
        raise HTTPException(status_code=401, detail="Token does not identify a user.")
    return principal_id_for_uid(uid)


def _is_staff(claims: dict) -> bool:
    return claims.get("role") in STAFF_ROLES or claims.get("staff_role") in STAFF_ROLES


@router.post("/identity/bootstrap")
def bootstrap_identity(authorization: Optional[str] = Header(None)):
    claims = _claims(authorization)
    try:
        principal, created = _service().bootstrap_principal(claims)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"principal": principal, "created": created}


@router.get("/me")
def get_me(authorization: Optional[str] = Header(None)):
    claims = _claims(authorization)
    service = _service()
    principal = service.get_principal(_actor_id(claims))
    if principal is None:
        raise HTTPException(status_code=404, detail="Canonical principal not bootstrapped.")
    return {"principal": principal}


@router.get("/me/memberships")
def get_my_memberships(authorization: Optional[str] = Header(None)):
    claims = _claims(authorization)
    actor_id = _actor_id(claims)
    return {"memberships": _service().list_memberships(actor_id)}


@router.post("/organizations", status_code=201)
def create_organization(body: OrganizationCreate, authorization: Optional[str] = Header(None)):
    claims = _claims(authorization)
    actor_id = _actor_id(claims)
    service = _service()
    if service.get_principal(actor_id) is None:
        raise HTTPException(status_code=409, detail="Bootstrap canonical identity first.")
    return {"organization": service.create_organization(actor_id, body)}


@router.post("/organizations/bootstrap-current")
def bootstrap_current_organization(authorization: Optional[str] = Header(None)):
    claims = _claims(authorization)
    try:
        organization, membership, created = _service().bootstrap_role_organization(claims)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"organization": organization, "membership": membership, "created": created}


@router.get("/organizations/{organization_id}")
def get_organization(organization_id: str, authorization: Optional[str] = Header(None)):
    claims = _claims(authorization)
    actor_id = _actor_id(claims)
    service = _service()
    organization = service.get_organization(organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    member_ids = {item.organization_id for item in service.list_memberships(actor_id)}
    if organization.created_by != actor_id and organization_id not in member_ids and not _is_staff(claims):
        raise HTTPException(status_code=403, detail="Organization access denied.")
    return {"organization": organization}


@router.post("/organizations/{organization_id}/memberships", status_code=201)
def create_membership(
    organization_id: str,
    body: MembershipCreate,
    authorization: Optional[str] = Header(None),
):
    claims = _claims(authorization)
    actor_id = _actor_id(claims)
    service = _service()
    organization = service.get_organization(organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    if organization.created_by != actor_id and not _is_staff(claims):
        raise HTTPException(status_code=403, detail="Organization administrator access required.")
    if service.get_principal(body.principal_id) is None:
        raise HTTPException(status_code=400, detail="Membership principal does not exist.")
    return {"membership": service.create_membership(actor_id, organization_id, body)}


@router.post("/consents", status_code=201)
def create_consent(body: ConsentGrantCreate, authorization: Optional[str] = Header(None)):
    claims = _claims(authorization)
    actor_id = _actor_id(claims)
    try:
        return {"consent": _service().create_consent(actor_id, body)}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/consents")
def list_consents(authorization: Optional[str] = Header(None)):
    claims = _claims(authorization)
    actor_id = _actor_id(claims)
    return {"consents": _service().list_consents(actor_id)}


@router.post("/consents/{consent_id}/revoke")
def revoke_consent(
    consent_id: str,
    body: RevokeConsentRequest,
    authorization: Optional[str] = Header(None),
):
    claims = _claims(authorization)
    actor_id = _actor_id(claims)
    try:
        return {"consent": _service().revoke_consent(actor_id, consent_id, body.reason)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/authorization/evaluate")
def evaluate_policy(body: AuthorizationRequest, authorization: Optional[str] = Header(None)):
    claims = _claims(authorization)
    actor_id = _actor_id(claims)
    service = _service()
    actor = service.get_principal(actor_id)
    if actor is None:
        raise HTTPException(status_code=409, detail="Bootstrap canonical identity first.")
    decision = evaluate_authorization(
        actor=actor,
        request=body,
        memberships=service.list_memberships(actor_id),
        consents=service.list_consents(body.subject_principal_id) if body.subject_principal_id else [],
    )
    return {"decision": decision}
