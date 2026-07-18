"""WP-15 launch readiness assessment API (never activates features)."""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from app.platform.launch import LaunchAssessmentRequest, LaunchService
from app.platform.service import principal_id_for_uid
from app.services.auth_rbac import STAFF_ROLES, verify_firebase_token

router = APIRouter(prefix="/platform-launch", tags=["tip-os-launch"])


def _staff(authorization: Optional[str]):
    if os.getenv("TIP_OS_LAUNCH_ASSESSMENT_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Launch assessment is not enabled.")
    claims = verify_firebase_token(authorization)
    if claims.get("role") not in STAFF_ROLES and claims.get("staff_role") not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="Staff role required.")
    return principal_id_for_uid(claims.get("uid") or claims.get("sub"))


def _service():
    from app.services import firebase_service
    firebase_service._init()
    if firebase_service._firestore_client is None:
        raise HTTPException(status_code=503, detail="Launch assessment store unavailable.")
    return LaunchService(firebase_service._firestore_client)


@router.post("/assess")
def assess(body: LaunchAssessmentRequest, authorization: Optional[str] = Header(None)):
    return {"assessment": _service().assess(body, _staff(authorization))}
