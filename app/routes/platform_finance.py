"""Feature-flagged WP-11 ledger, hold, and reconciliation APIs."""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from app.platform.ledger import (
    FundsHoldRequest,
    HoldTransition,
    JournalRequest,
    LedgerAccount,
    LedgerService,
)
from app.platform.service import principal_id_for_uid
from app.services.auth_rbac import STAFF_ROLES, verify_firebase_token

router = APIRouter(prefix="/platform-finance", tags=["tip-os-finance"])


def _context(authorization: Optional[str]):
    if os.getenv("TIP_OS_FINANCIAL_LEDGER_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Platform financial ledger is not enabled.")
    claims = verify_firebase_token(authorization)
    role = claims.get("role") or claims.get("staff_role")
    if role not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="Staff role required.")
    return claims, principal_id_for_uid(claims.get("uid") or claims.get("sub"))


def _service():
    from app.services import firebase_service
    firebase_service._init()
    if firebase_service._firestore_client is None:
        raise HTTPException(status_code=503, detail="Financial store unavailable.")
    return LedgerService(firebase_service._firestore_client)


@router.post("/accounts", status_code=201)
def create_account(body: LedgerAccount, authorization: Optional[str] = Header(None)):
    _context(authorization)
    account, created = _service().create_account(body)
    return {"account": account, "created": created}


@router.post("/journals", status_code=201)
def post_journal(body: JournalRequest, authorization: Optional[str] = Header(None)):
    _, actor = _context(authorization)
    try:
        journal, created = _service().post_journal(body, actor)
        return {"journal": journal, "created": created}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/holds", status_code=201)
def create_hold(body: FundsHoldRequest, authorization: Optional[str] = Header(None)):
    _, actor = _context(authorization)
    hold, created = _service().create_hold(body, actor)
    return {"hold": hold, "created": created}


@router.post("/holds/{hold_id}/transition")
def transition_hold(
    hold_id: str, body: HoldTransition, authorization: Optional[str] = Header(None)
):
    _, actor = _context(authorization)
    try:
        hold, changed = _service().transition_hold(hold_id, body, actor)
        return {"hold": hold, "changed": changed}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/reconcile/{tenant_id}/{provider}")
def reconcile_provider(
    tenant_id: str,
    provider: str,
    settlements: list[dict],
    authorization: Optional[str] = Header(None),
):
    _context(authorization)
    return {"reconciliation": _service().reconcile_provider(tenant_id, provider, settlements)}
