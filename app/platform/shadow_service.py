"""Best-effort orchestration for comparing legacy and TIP OS authorization."""
from __future__ import annotations

import logging
import os
from typing import Optional

from app.platform.models import AuthorizationDecision, AuthorizationRequest
from app.platform.service import PlatformService, evaluate_authorization, principal_id_for_uid
from app.platform.shadow import compare_decisions, write_shadow_comparison

logger = logging.getLogger(__name__)


def shadow_enabled() -> bool:
    return os.getenv("TIP_OS_AUTH_SHADOW_ENABLED", "false").lower() == "true"


def shadow_authorization(
    db,
    claims: dict,
    *,
    legacy_allowed: bool,
    legacy_reason: str,
    action: str,
    resource_type: str,
    resource_id: str,
    tenant_id: Optional[str] = None,
    purpose: Optional[str] = None,
    record_category: Optional[str] = None,
    subject_principal_id: Optional[str] = None,
    terminal_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> str:
    """Record a comparison without changing or raising into the caller's result."""
    if not shadow_enabled():
        return ""
    try:
        uid = claims.get("uid") or claims.get("sub")
        if not uid:
            return ""
        actor_id = principal_id_for_uid(uid)
        service = PlatformService(db)
        actor = service.get_principal(actor_id)
        if actor is None:
            platform = AuthorizationDecision(allowed=False, reason="canonical_principal_missing")
        else:
            request = AuthorizationRequest(
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                tenant_id=tenant_id,
                purpose=purpose,
                record_category=record_category,
                subject_principal_id=subject_principal_id,
                terminal_id=terminal_id,
            )
            platform = evaluate_authorization(
                actor=actor,
                request=request,
                memberships=service.list_memberships(actor_id),
                consents=service.list_consents(subject_principal_id) if subject_principal_id else [],
            )
        comparison = compare_decisions(legacy_allowed, legacy_reason, platform)
        return write_shadow_comparison(
            db,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            comparison=comparison,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        logger.warning(
            "[tip-os-shadow] comparison failed resource_type=%s action=%s: %s",
            resource_type,
            action,
            exc,
        )
        return ""
