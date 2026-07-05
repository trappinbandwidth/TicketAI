"""
Shared route helpers — Firestore handle + auth.

Consolidates the _db / _verify_token / _require_staff boilerplate that the
attorney-portal route modules each re-declared. New modules should import from here.

Two auth models coexist by design:
  - Firebase Bearer token (verify_token/require_staff) — the Attorney Portal, where
    each attorney has their own Firebase account.
  - x-api-key (require_api_key) — the internal admin console (frontend-qa), which has
    no per-staff Firebase login; staff instead pick their name from a fixed reviewer
    list (Quest/Justin/Eniola) and pass it explicitly as an actor field in the request.
Admin-facing routes callable from the admin console must use require_api_key, not
require_staff, or the console's plain x-api-key client gets a 401.
"""
from __future__ import annotations

import os
from typing import Optional

import firebase_admin.auth as fb_auth
from fastapi import HTTPException

STAFF_ROLES = {"account_manager", "staff", "admin", "super_admin", "reviewer"}


def require_api_key(x_api_key: Optional[str]) -> None:
    if x_api_key != os.getenv("API_KEY", "cdl-local-dev"):
        raise HTTPException(status_code=401, detail="Invalid API key.")


def get_db():
    from app.services.firebase_service import _init, _firestore_client
    _init()
    if _firestore_client is None:
        raise HTTPException(status_code=503, detail="Firestore not configured.")
    return _firestore_client


def verify_token(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    try:
        return fb_auth.verify_id_token(authorization.split(" ", 1)[1])
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc


def require_staff(authorization: Optional[str]) -> dict:
    decoded = verify_token(authorization)
    if decoded.get("role") not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="Staff role required.")
    return decoded


def iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v
