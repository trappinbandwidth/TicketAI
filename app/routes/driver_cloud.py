"""Feature-flagged WP-02 Driver Cloud API."""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query

from app.platform.record_service import DriverCloudService
from app.platform.records import CanonicalRecordCreate, RecordCategory
from app.platform.service import principal_id_for_uid
from app.services.auth_rbac import verify_firebase_token


router = APIRouter(prefix="/driver-cloud", tags=["tip-os-driver-cloud"])


def _claims(authorization: Optional[str]) -> dict:
    if os.getenv("TIP_OS_RECORDS_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Driver Cloud APIs are not enabled.")
    return verify_firebase_token(authorization)


def _actor_id(claims: dict) -> str:
    uid = claims.get("uid") or claims.get("sub")
    if not uid:
        raise HTTPException(status_code=401, detail="Token does not identify a user.")
    return principal_id_for_uid(uid)


def _service() -> DriverCloudService:
    from app.services import firebase_service

    firebase_service._init()
    if firebase_service._firestore_client is None:
        raise HTTPException(status_code=503, detail="Driver Cloud store unavailable.")
    return DriverCloudService(firebase_service._firestore_client)


@router.get("/me")
def get_driver_cloud(
    category: Optional[RecordCategory] = Query(default=None),
    authorization: Optional[str] = Header(None),
):
    actor_id = _actor_id(_claims(authorization))
    records = _service().list_records(actor_id)
    if category is not None:
        records = [record for record in records if record.category == category]
    return {
        "subject_principal_id": actor_id,
        "records": records,
        "groups": {
            item.value: [record for record in records if record.category == item]
            for item in RecordCategory
        },
    }


@router.post("/me/records", status_code=201)
def create_record(body: CanonicalRecordCreate, authorization: Optional[str] = Header(None)):
    actor_id = _actor_id(_claims(authorization))
    return {"record": _service().create_record(actor_id, actor_id, body)}


@router.put("/me/records/{record_id}")
def update_record(
    record_id: str,
    body: CanonicalRecordCreate,
    expected_version: int = Query(ge=1),
    authorization: Optional[str] = Header(None),
):
    actor_id = _actor_id(_claims(authorization))
    try:
        record = _service().update_record(actor_id, record_id, expected_version, body)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"record": record}


@router.get("/me/activity")
def get_record_activity(authorization: Optional[str] = Header(None)):
    actor_id = _actor_id(_claims(authorization))
    return {"activity": _service().list_activity(actor_id)}
