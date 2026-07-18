"""Feature-flagged WP-08 Carrier/Safety views."""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from app.platform.service import principal_id_for_uid
from app.services.auth_rbac import verify_firebase_token
from app.services.carrier_resolve import CarrierResolveService


router = APIRouter(prefix="/carrier-resolve", tags=["tip-os-carrier-resolve"])


def _claims(authorization: Optional[str]):
    if os.getenv("TIP_OS_CARRIER_RESOLVE_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Carrier Resolve APIs are not enabled.")
    return verify_firebase_token(authorization)


def _actor(claims: dict):
    uid = claims.get("uid") or claims.get("sub")
    if not uid:
        raise HTTPException(status_code=401, detail="Token does not identify a user.")
    return principal_id_for_uid(uid)


def _service():
    from app.services import firebase_service

    firebase_service._init()
    if firebase_service._firestore_client is None:
        raise HTTPException(status_code=503, detail="Carrier Resolve store unavailable.")
    return CarrierResolveService(firebase_service._firestore_client)


@router.get("/organizations/{organization_id}/drivers/{driver_principal_id}/summary")
def get_driver_safety_summary(
    organization_id: str,
    driver_principal_id: str,
    authorization: Optional[str] = Header(None),
):
    actor_id = _actor(_claims(authorization))
    try:
        return _service().driver_summary(actor_id, organization_id, driver_principal_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
