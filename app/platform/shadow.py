"""Non-enforcing authorization comparison records for staged WP-01 rollout."""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from typing import Optional

from app.platform.models import AuthorizationDecision, utc_now


@dataclass(frozen=True)
class ShadowComparison:
    legacy_allowed: bool
    platform_allowed: bool
    match: bool
    legacy_reason: str
    platform_reason: str


def compare_decisions(legacy_allowed: bool, legacy_reason: str, platform: AuthorizationDecision) -> ShadowComparison:
    return ShadowComparison(
        legacy_allowed=legacy_allowed,
        platform_allowed=platform.allowed,
        match=legacy_allowed == platform.allowed,
        legacy_reason=legacy_reason,
        platform_reason=platform.reason,
    )


def write_shadow_comparison(
    db,
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    comparison: ShadowComparison,
    correlation_id: Optional[str] = None,
) -> str:
    """Persist a comparison only; callers must continue using the legacy result."""
    comparison_id = f"authshadow_{uuid.uuid4().hex}"
    db.collection("authorization_shadow_comparisons").document(comparison_id).set({
        "id": comparison_id,
        "actor_id": actor_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "comparison": asdict(comparison),
        "correlation_id": correlation_id,
        "enforced": False,
        "policy_version": "wp01-v1",
        "created_at": utc_now().isoformat(),
    })
    return comparison_id
