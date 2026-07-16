"""Feature-flagged WP-10 integration operations."""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from app.platform.integrations import ConnectorRequest, IntegrationService, ManualSourceRecord, ReconciliationRequest
from app.platform.service import principal_id_for_uid
from app.services.auth_rbac import STAFF_ROLES, verify_firebase_token

router = APIRouter(prefix="/platform-integrations", tags=["tip-os-integrations"])


def _claims(authorization: Optional[str]):
    if os.getenv("TIP_OS_INTEGRATIONS_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Platform integrations are not enabled.")
    claims = verify_firebase_token(authorization)
    if claims.get("role") not in STAFF_ROLES and claims.get("staff_role") not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="Staff role required.")
    return claims


def _service():
    from app.services import firebase_service
    firebase_service._init()
    if firebase_service._firestore_client is None:
        raise HTTPException(status_code=503, detail="Integration store unavailable.")
    return IntegrationService(firebase_service._firestore_client)


@router.post("/sync", status_code=202)
def run_sync(body: ConnectorRequest, authorization: Optional[str] = Header(None)):
    claims = _claims(authorization)
    try:
        job, source = _service().run(body, principal_id_for_uid(claims.get("uid") or claims.get("sub")))
        return {"sync_job": job, "source_record": source}
    except LookupError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/manual-source", status_code=201)
def manual_source(body: ManualSourceRecord, authorization: Optional[str] = Header(None)):
    claims = _claims(authorization)
    job, source = _service().submit_manual(
        body, principal_id_for_uid(claims.get("uid") or claims.get("sub"))
    )
    return {"sync_job": job, "source_record": source}


@router.post("/reconcile")
def reconcile(body: ReconciliationRequest, authorization: Optional[str] = Header(None)):
    _claims(authorization)
    return {"reconciliation": _service().reconcile(body)}
