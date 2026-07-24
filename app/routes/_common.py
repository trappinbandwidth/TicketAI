"""
Shared route helpers — Firestore handle + auth.

Consolidates the _db / _verify_token / _require_staff boilerplate that the
attorney-portal route modules each re-declared. New modules should import from here.

Two auth models coexist by design:
  - Firebase Bearer token (verify_token/require_staff) — staff/admin surfaces and
    attorney-facing routes that need per-user authorization.
  - x-api-key (require_api_key) — shared upload, queue, quote, webhook, or integration
    routes that still use the service-level key while the auth model is being migrated.

Prefer require_staff for admin-console-only routes. Keep require_api_key only where
the route is intentionally shared with non-staff clients or external integrations.
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import HTTPException
from app.services.auth_rbac import (
    STAFF_ROLES,
    require_staff as require_staff_claim,
    verify_firebase_token,
)


def require_api_key(x_api_key: Optional[str]) -> None:
    if x_api_key != os.getenv("API_KEY", "cdl-local-dev"):
        raise HTTPException(status_code=401, detail="Invalid API key.")


def get_db():
    # Read the handle from the module after initialization. Importing the
    # variable itself would retain the pre-init `None` value in this scope.
    from app.services import firebase_service

    firebase_service._init()
    if firebase_service._firestore_client is None:
        raise HTTPException(status_code=503, detail="Firestore not configured.")
    return firebase_service._firestore_client


def verify_token(authorization: Optional[str]) -> dict:
    return verify_firebase_token(authorization)


def require_staff(authorization: Optional[str]) -> dict:
    decoded = verify_token(authorization)
    return require_staff_claim(decoded)


def iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v
