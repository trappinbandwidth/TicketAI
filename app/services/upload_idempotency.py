"""Replay protection for authenticated Driver uploads."""
from __future__ import annotations

import hashlib
import os
import re
import threading
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from google.api_core.exceptions import AlreadyExists

_OPERATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,199}$")
_mock_claims: set[str] = set()
_mock_lock = threading.Lock()


def _claim_key(driver_id: str, operation_id: str) -> str:
    return hashlib.sha256(f"{driver_id}:{operation_id}".encode("utf-8")).hexdigest()


def claim_driver_upload(driver_id: str, operation_id: Optional[str]) -> str:
    """Atomically claim an upload operation or reject its replay.

    Production and emulator claims live in Firestore so multiple Engine
    instances share the same boundary. Unit/mock runs use a locked in-memory
    set and never contact a cloud project.
    """
    if not operation_id or not _OPERATION_ID.fullmatch(operation_id):
        raise HTTPException(
            status_code=400,
            detail="A valid x-operation-id header is required for Driver uploads.",
        )

    key = _claim_key(driver_id, operation_id)
    mock_without_emulator = (
        os.getenv("USE_MOCK", "true").lower() == "true"
        and not os.getenv("FIRESTORE_EMULATOR_HOST")
    )
    if mock_without_emulator:
        with _mock_lock:
            if key in _mock_claims:
                raise HTTPException(status_code=409, detail="Driver upload operation already accepted.")
            _mock_claims.add(key)
        return operation_id

    try:
        from app.services.firebase_service import _firestore_client, _init

        _init()
        if _firestore_client is None:
            raise HTTPException(
                status_code=503,
                detail="Driver upload replay protection is unavailable.",
            )
        _firestore_client.collection("upload_operations").document(key).create({
            "actor_type": "driver",
            "actor_id": driver_id,
            "operation_id": operation_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except HTTPException:
        raise
    except AlreadyExists:
        raise HTTPException(
            status_code=409,
            detail="Driver upload operation already accepted.",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Driver upload replay protection is unavailable.",
        ) from exc

    return operation_id


def clear_mock_claims() -> None:
    """Test-only reset for the isolated mock claim store."""
    with _mock_lock:
        _mock_claims.clear()
