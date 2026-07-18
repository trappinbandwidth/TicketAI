"""Staff-only entity reconciliation queue."""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from app.platform.entity_resolution import EntityResolutionService, ResolutionCaseCreate, ResolutionDecision
from app.platform.service import principal_id_for_uid
from app.services.auth_rbac import STAFF_ROLES, require_recent_auth, verify_firebase_token

router = APIRouter(prefix="/platform-resolution", tags=["tip-os-entity-resolution"])


def _staff(authorization: Optional[str], recent=False):
    if os.getenv("TIP_OS_ENTITY_RESOLUTION_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Entity resolution is not enabled.")
    claims = verify_firebase_token(authorization)
    if claims.get("role") not in STAFF_ROLES and claims.get("staff_role") not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="Staff role required.")
    if recent:
        require_recent_auth(claims, require_mfa=True)
    return principal_id_for_uid(claims.get("uid") or claims.get("sub"))


def _service():
    from app.services import firebase_service
    firebase_service._init()
    if firebase_service._firestore_client is None:
        raise HTTPException(status_code=503, detail="Resolution store unavailable.")
    return EntityResolutionService(firebase_service._firestore_client)


@router.post("/cases", status_code=201)
def open_case(body: ResolutionCaseCreate, authorization: Optional[str] = Header(None)):
    case, created = _service().open_case(body, _staff(authorization))
    return {"case": case, "created": created}


@router.post("/cases/{case_id}/decision")
def decide(
    case_id: str, body: ResolutionDecision, authorization: Optional[str] = Header(None)
):
    try:
        case, changed = _service().decide(case_id, body, _staff(authorization, recent=True))
        return {"case": case, "changed": changed}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
