"""Staff audit log writer.

Audit entries are append-only Firestore documents under staff_audit/{audit_id}.
Callers pass the Firestore client they already use so audit writes participate in
the same configured Firebase context as the route.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _server_timestamp():
    try:
        from google.cloud.firestore_v1 import SERVER_TIMESTAMP

        return SERVER_TIMESTAMP
    except Exception:
        return None


def _actor_role(actor: dict) -> str:
    role = actor.get("staff_role") or actor.get("role") or "staff"
    return role if isinstance(role, str) else "staff"


def write_staff_audit(
    db,
    actor: dict,
    action: str,
    entity_type: str,
    entity_id: str,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
    reason: Optional[str] = None,
    source: str = "admin_dashboard",
) -> bool:
    """Write a staff audit entry. Returns False instead of raising on write errors."""
    if db is None:
        logger.warning("[staff_audit] Firestore client unavailable for action=%s entity=%s", action, entity_id)
        return False

    entry = {
        "actor_uid": actor.get("uid") or actor.get("sub") or "",
        "actor_email": actor.get("email") or "",
        "actor_role": _actor_role(actor),
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "before": before or {},
        "after": after or {},
        "reason": reason,
        "source": source,
        "created_at": _server_timestamp(),
    }

    try:
        db.collection("staff_audit").document().set(entry)
        return True
    except Exception as exc:
        logger.warning("[staff_audit] write failed action=%s entity=%s: %s", action, entity_id, exc)
        return False
