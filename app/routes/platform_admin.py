"""Feature-flagged WP-09 Captain/Admin APIs."""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from firebase_admin import storage

from app.platform.admin_service import (
    AdminService,
    CarrierAuthorityDecision,
    FeatureFlagUpdate,
    PrivilegedAccessRequest,
)
from app.platform.service import principal_id_for_uid
from app.services.auth_rbac import STAFF_ROLES, require_recent_auth, verify_firebase_token


router = APIRouter(prefix="/platform-admin", tags=["tip-os-platform-admin"])


def _claims(authorization: Optional[str]):
    if os.getenv("TIP_OS_ADMIN_CONSOLE_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Platform Admin APIs are not enabled.")
    claims = verify_firebase_token(authorization)
    if claims.get("role") not in STAFF_ROLES and claims.get("staff_role") not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="Staff role required.")
    return claims


def _actor(claims: dict):
    return principal_id_for_uid(claims.get("uid") or claims.get("sub"))


def _service():
    from app.services import firebase_service

    firebase_service._init()
    if firebase_service._firestore_client is None:
        raise HTTPException(status_code=503, detail="Admin store unavailable.")
    return AdminService(firebase_service._firestore_client)


def _bucket():
    name = os.getenv("FIREBASE_STORAGE_BUCKET") or (
        f'{os.getenv("FIREBASE_PROJECT_ID", "rigresolve")}.appspot.com'
    )
    return storage.bucket(name)


@router.get("/operations-summary")
def operations_summary(authorization: Optional[str] = Header(None)):
    _claims(authorization)
    return _service().operations_summary()


@router.get("/carrier-authority-claims")
def carrier_authority_claims(
    status: Optional[str] = Query(
        default=None,
        pattern=(
            "^(pending_evidence|pending_review|verified|rejected|"
            "duplicate_disputed)$"
        ),
    ),
    limit: int = Query(default=100, ge=1, le=100),
    authorization: Optional[str] = Header(None),
):
    _claims(authorization)
    return {
        "claims": _service().list_carrier_authority_claims(
            status=status,
            limit=limit,
        )
    }


@router.get(
    "/carrier-authority-claims/{claim_id}/evidence/{evidence_id}/download"
)
def download_carrier_authority_evidence(
    claim_id: str,
    evidence_id: str,
    authorization: Optional[str] = Header(None),
):
    claims = _claims(authorization)
    require_recent_auth(claims, require_mfa=True)
    try:
        evidence = _service().carrier_authority_evidence_for_review(
            claim_id,
            evidence_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        url = _bucket().blob(evidence["storage_path"]).generate_signed_url(
            version="v4",
            expiration=900,
            method="GET",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Authority evidence download is unavailable.",
        ) from exc
    return {"url": url, "expires_in": 900}


@router.post("/carrier-authority-claims/{claim_id}/decision")
def decide_carrier_authority(
    claim_id: str,
    body: CarrierAuthorityDecision,
    authorization: Optional[str] = Header(None),
):
    claims = _claims(authorization)
    require_recent_auth(claims, require_mfa=True)
    try:
        return {
            "claim": _service().decide_carrier_authority(
                _actor(claims),
                claim_id,
                body,
            )
        }
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/feature-flags/{key}")
def update_feature_flag(
    key: str, body: FeatureFlagUpdate, authorization: Optional[str] = Header(None)
):
    claims = _claims(authorization)
    require_recent_auth(claims, require_mfa=True)
    if key != body.key:
        raise HTTPException(status_code=400, detail="Feature flag key mismatch.")
    try:
        return {"feature_flag": _service().set_feature_flag(_actor(claims), body)}
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/privileged-access", status_code=201)
def start_privileged_access(
    body: PrivilegedAccessRequest, authorization: Optional[str] = Header(None)
):
    claims = _claims(authorization)
    require_recent_auth(claims, require_mfa=True)
    return {"access": _service().start_privileged_access(_actor(claims), body)}
