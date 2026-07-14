"""TIP event writer.

Phase 1 stores platform events in Firestore under events/{event_id}. Event
failures are logged and return an empty string so they do not break ticket
processing or other critical user flows.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

logger = logging.getLogger(__name__)


def _server_timestamp():
    try:
        from google.cloud.firestore_v1 import SERVER_TIMESTAMP

        return SERVER_TIMESTAMP
    except Exception:
        return None


def _db():
    from app.services.firebase_service import _firestore_client, _init

    _init()
    return _firestore_client


def build_event(
    event_type: str,
    actor_type: str,
    actor_id: Optional[str],
    entity_type: str,
    entity_id: str,
    payload: Optional[dict] = None,
    related_entities: Optional[list[dict]] = None,
    source: str = "system",
    metadata: Optional[dict] = None,
) -> dict:
    event_id = f"evt_{uuid.uuid4().hex}"
    return {
        "id": event_id,
        "event_type": event_type,
        "version": "1.0",
        "actor_type": actor_type,
        "actor_id": actor_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "related_entities": related_entities or [],
        "source": source,
        "payload": payload or {},
        "metadata": metadata or {},
        "created_at": _server_timestamp(),
    }


def write_event(
    event_type: str,
    actor_type: str,
    actor_id: Optional[str],
    entity_type: str,
    entity_id: str,
    payload: Optional[dict] = None,
    related_entities: Optional[list[dict]] = None,
    source: str = "system",
    metadata: Optional[dict] = None,
) -> str:
    event = build_event(
        event_type=event_type,
        actor_type=actor_type,
        actor_id=actor_id,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
        related_entities=related_entities,
        source=source,
        metadata=metadata,
    )

    try:
        db = _db()
        if db is None:
            logger.warning("[event_service] Firestore unavailable for event=%s entity=%s", event_type, entity_id)
            return ""
        db.collection("events").document(event["id"]).set(event)
        return event["id"]
    except Exception as exc:
        logger.warning("[event_service] write failed event=%s entity=%s: %s", event_type, entity_id, exc)
        return ""
