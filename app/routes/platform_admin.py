"""Feature-flagged WP-09 Captain/Admin APIs."""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from app.platform.admin_service import AdminService, FeatureFlagUpdate, PrivilegedAccessRequest
from app.platform.service import principal_id_for_uid
from app.services.auth_rbac import STAFF_ROLES, verify_firebase_token


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


@router.get("/operations-summary")
def operations_summary(authorization: Optional[str] = Header(None)):
    _claims(authorization)
    return _service().operations_summary()


@router.put("/feature-flags/{key}")
def update_feature_flag(
    key: str, body: FeatureFlagUpdate, authorization: Optional[str] = Header(None)
):
    claims = _claims(authorization)
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
    return {"access": _service().start_privileged_access(_actor(claims), body)}
