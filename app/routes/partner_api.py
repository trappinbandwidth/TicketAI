"""WP-12 versioned partner and staff management APIs."""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query

from app.platform.partner_api import (
    PartnerApiService,
    PartnerClientCreate,
    PartnerEventCreate,
    WebhookSubscriptionCreate,
)
from app.platform.service import principal_id_for_uid
from app.services.auth_rbac import STAFF_ROLES, verify_firebase_token

router = APIRouter(tags=["tip-os-partner-api"])


def _enabled():
    if os.getenv("TIP_OS_PARTNER_API_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Partner APIs are not enabled.")


def _service():
    from app.services import firebase_service
    firebase_service._init()
    if firebase_service._firestore_client is None:
        raise HTTPException(status_code=503, detail="Partner API store unavailable.")
    return PartnerApiService(firebase_service._firestore_client)


def _staff(authorization: Optional[str]):
    _enabled()
    claims = verify_firebase_token(authorization)
    if claims.get("role") not in STAFF_ROLES and claims.get("staff_role") not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="Staff role required.")
    return principal_id_for_uid(claims.get("uid") or claims.get("sub"))


def _partner(client_id: Optional[str], client_secret: Optional[str], scope: str):
    _enabled()
    if not client_id or not client_secret:
        raise HTTPException(status_code=401, detail="Partner credentials required.")
    try:
        return _service().authenticate(client_id, client_secret, scope)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/platform-partners/clients", status_code=201)
def create_client(body: PartnerClientCreate, authorization: Optional[str] = Header(None)):
    return _service().create_client(body, _staff(authorization))


@router.post("/platform-partners/webhook-subscriptions", status_code=201)
def create_subscription(
    body: WebhookSubscriptionCreate, authorization: Optional[str] = Header(None)
):
    try:
        return {"subscription": _service().create_subscription(body, _staff(authorization))}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/platform-partners/events", status_code=202)
def publish_event(body: PartnerEventCreate, authorization: Optional[str] = Header(None)):
    _staff(authorization)
    event, deliveries = _service().publish(body)
    return {"event": event, "deliveries_queued": len(deliveries)}


@router.get("/partner/v1/events")
def list_partner_events(
    event_type: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=200),
    x_partner_client_id: Optional[str] = Header(None),
    x_partner_client_secret: Optional[str] = Header(None),
):
    context = _partner(x_partner_client_id, x_partner_client_secret, "events:read")
    service = _service()
    reference = service.db.collection("partner_events")
    rows = list(reference.rows.values()) if hasattr(reference, "rows") else [
        item.to_dict() or {} for item in reference.limit(1000).stream()
    ]
    events = [
        item for item in rows
        if item.get("tenant_id") == context["tenant_id"]
        and (not event_type or item.get("event_type") == event_type)
    ]
    events.sort(key=lambda item: str(item.get("occurred_at", "")), reverse=True)
    return {"data": events[:limit], "meta": {"count": min(len(events), limit), "limit": limit}}
