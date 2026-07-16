"""Firebase Auth and role helpers for API routes.

The helpers raise FastAPI HTTPException so route modules can call them directly
without repeating token parsing and custom-claim checks.
"""
from __future__ import annotations

import time
from typing import Optional, Sequence

import firebase_admin.auth as fb_auth
from fastapi import HTTPException


STAFF_ROLES = {"staff", "admin", "super_admin", "account_manager", "ops_staff", "reviewer"}
ATTORNEY_ROLES = {"attorney"}
CARRIER_ROLES = {"carrier"}


def _claim(decoded_token: dict, key: str) -> str:
    value = decoded_token.get(key)
    return value if isinstance(value, str) else ""


def _staff_role(decoded_token: dict) -> str:
    return _claim(decoded_token, "staff_role") or _claim(decoded_token, "role")


def verify_firebase_token(auth_header: Optional[str]) -> dict:
    """Verify an Authorization: Bearer <id_token> header and return decoded claims."""
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")

    try:
        return fb_auth.verify_id_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc


def require_role(decoded_token: dict, allowed_roles: Sequence[str]) -> dict:
    """Require a decoded token to carry one of the allowed top-level roles."""
    if _claim(decoded_token, "role") not in set(allowed_roles):
        raise HTTPException(status_code=403, detail="Required role missing.")
    return decoded_token


def require_staff(
    decoded_token: dict,
    allowed_staff_roles: Optional[Sequence[str]] = None,
) -> dict:
    """Require a staff/admin token, optionally constrained to specific staff roles."""
    role = _claim(decoded_token, "role")
    staff_role = _staff_role(decoded_token)
    if role not in STAFF_ROLES and staff_role not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="Staff role required.")

    if allowed_staff_roles and staff_role not in set(allowed_staff_roles):
        raise HTTPException(status_code=403, detail="Required staff role missing.")

    return decoded_token


def require_carrier(decoded_token: dict, carrier_id: Optional[str] = None) -> dict:
    """Require a carrier token and optionally enforce a specific carrier id claim."""
    require_role(decoded_token, CARRIER_ROLES)
    token_carrier_id = _claim(decoded_token, "carrier_id")
    if carrier_id and token_carrier_id and token_carrier_id != carrier_id:
        raise HTTPException(status_code=403, detail="Carrier access denied.")
    if carrier_id and not token_carrier_id:
        raise HTTPException(status_code=403, detail="Carrier claim required.")
    return decoded_token


def require_attorney(decoded_token: dict, attorney_id: Optional[str] = None) -> dict:
    """Require an attorney token and optionally enforce a specific attorney id claim."""
    require_role(decoded_token, ATTORNEY_ROLES)
    token_attorney_id = _claim(decoded_token, "attorney_id")
    if attorney_id and token_attorney_id and token_attorney_id != attorney_id:
        raise HTTPException(status_code=403, detail="Attorney access denied.")
    if attorney_id and not token_attorney_id:
        raise HTTPException(status_code=403, detail="Attorney claim required.")
    return decoded_token


def require_recent_auth(
    decoded_token: dict,
    max_age_seconds: int = 600,
    require_mfa: bool = False,
    now_epoch: Optional[int] = None,
) -> dict:
    """Require a recent Firebase authentication event and optional MFA factor."""
    auth_time = decoded_token.get("auth_time")
    now = int(now_epoch if now_epoch is not None else time.time())
    if (
        not isinstance(auth_time, (int, float))
        or auth_time > now
        or now - int(auth_time) > max_age_seconds
    ):
        raise HTTPException(status_code=403, detail="Recent authentication required.")
    if require_mfa:
        firebase_claim = decoded_token.get("firebase") or {}
        factor = (
            firebase_claim.get("sign_in_second_factor")
            or decoded_token.get("mfa_verified")
            or decoded_token.get("amr")
        )
        if not factor or factor == ["pwd"]:
            raise HTTPException(status_code=403, detail="Multi-factor authentication required.")
    return decoded_token
