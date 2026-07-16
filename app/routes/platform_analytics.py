"""Feature-flagged WP-13 analytics and data-quality APIs."""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from app.platform.analytics import AnalyticsQuery, AnalyticsService, QualityRule
from app.services.auth_rbac import STAFF_ROLES, verify_firebase_token

router = APIRouter(prefix="/platform-analytics", tags=["tip-os-analytics"])


def _staff(authorization: Optional[str]):
    if os.getenv("TIP_OS_ANALYTICS_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Platform analytics are not enabled.")
    claims = verify_firebase_token(authorization)
    if claims.get("role") not in STAFF_ROLES and claims.get("staff_role") not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="Staff role required.")


def _service():
    from app.services import firebase_service
    firebase_service._init()
    if firebase_service._firestore_client is None:
        raise HTTPException(status_code=503, detail="Analytics store unavailable.")
    return AnalyticsService(firebase_service._firestore_client)


@router.post("/operational-snapshot")
def operational_snapshot(body: AnalyticsQuery, authorization: Optional[str] = Header(None)):
    _staff(authorization)
    return {"snapshot": _service().operational_snapshot(body)}


@router.post("/quality-rules/evaluate")
def evaluate_quality(
    body: QualityRule,
    tenant_id: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    _staff(authorization)
    return {"result": _service().evaluate_quality(body, tenant_id)}
