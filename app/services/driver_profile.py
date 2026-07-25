"""Server-owned Driver profile storage with a separated verification vault."""
from __future__ import annotations

import base64
import binascii
import os
from datetime import datetime, timezone
from typing import Any, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException

SENSITIVE_PUBLIC_FIELDS = {
    "address",
    "cdl_expiration",
    "cdl_number",
    "dob",
    "profile_image",
    "ssn_last4",
}
ALLOWED_AVATAR_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_AVATAR_BYTES = 512 * 1024


def _matches_image_signature(raw: bytes, content_type: str) -> bool:
    if content_type == "image/jpeg":
        return raw.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return raw.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/webp":
        return len(raw) >= 12 and raw.startswith(b"RIFF") and raw[8:12] == b"WEBP"
    return False


class PiiCipher:
    """AES-256-GCM envelope using a versioned key supplied by Secret Manager."""

    def __init__(self, key: bytes, key_id: str):
        if len(key) != 32:
            raise ValueError("PII encryption key must contain exactly 32 bytes.")
        if not key_id:
            raise ValueError("PII encryption key ID is required.")
        self._cipher = AESGCM(key)
        self._key_id = key_id

    @classmethod
    def from_env(cls) -> "PiiCipher":
        encoded = os.getenv("PII_ENCRYPTION_KEY_B64", "").strip()
        key_id = os.getenv("PII_ENCRYPTION_KEY_ID", "").strip()
        if not encoded or not key_id:
            raise HTTPException(
                status_code=503,
                detail="Driver verification storage is unavailable.",
            )
        try:
            key = base64.b64decode(encoded, validate=True)
            return cls(key, key_id)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(
                status_code=503,
                detail="Driver verification storage is unavailable.",
            ) from exc

    def encrypt(self, value: str, *, subject: str, field: str) -> dict:
        nonce = os.urandom(12)
        aad = f"{subject}:{field}:{self._key_id}".encode("utf-8")
        ciphertext = self._cipher.encrypt(nonce, value.encode("utf-8"), aad)
        return {
            "algorithm": "AES-256-GCM",
            "key_id": self._key_id,
            "nonce_b64": base64.b64encode(nonce).decode("ascii"),
            "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
        }


def decode_avatar(data_url: str) -> tuple[bytes, str, str]:
    try:
        header, encoded = data_url.split(",", 1)
        content_type = header.removeprefix("data:").split(";", 1)[0].lower()
        extension = ALLOWED_AVATAR_TYPES[content_type]
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, KeyError, binascii.Error) as exc:
        raise HTTPException(status_code=422, detail="Profile image is malformed or unsupported.") from exc
    if not raw or not _matches_image_signature(raw, content_type):
        raise HTTPException(status_code=422, detail="Profile image content does not match its type.")
    if len(raw) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=413, detail="Profile image must be 512 KB or smaller.")
    return raw, content_type, extension


def _upload_avatar(uid: str, data_url: str) -> str:
    raw, content_type, extension = decode_avatar(data_url)
    project_id = os.getenv("FIREBASE_PROJECT_ID", "").strip()
    if not project_id:
        raise HTTPException(status_code=503, detail="Profile image storage is unavailable.")
    try:
        from firebase_admin import storage

        path = f"driver_profiles/{uid}/avatar.{extension}"
        storage.bucket(f"{project_id}.appspot.com").blob(path).upload_from_string(
            raw,
            content_type=content_type,
        )
        return path
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Profile image storage is unavailable.") from exc


class DriverProfileService:
    def __init__(self, db, cipher: PiiCipher, avatar_uploader=_upload_avatar):
        self.db = db
        self.cipher = cipher
        self.avatar_uploader = avatar_uploader

    def get(self, uid: str, phone: Optional[str] = None) -> dict:
        public_snap = self.db.collection("drivers").document(uid).get()
        private_snap = self.db.collection("driver_private").document(uid).get()
        public = public_snap.to_dict() if public_snap.exists else {}
        private = private_snap.to_dict() if private_snap.exists else {}
        safe_public = {
            key: value for key, value in (public or {}).items()
            if key not in SENSITIVE_PUBLIC_FIELDS
        }
        verification = {
            key: value for key, value in (private or {}).items()
            if key != "ssn_last4_encrypted"
        }
        return {
            "driver_id": uid,
            **safe_public,
            **verification,
            "phone": phone or safe_public.get("phone"),
            "ssn_last4_present": bool((private or {}).get("ssn_last4_encrypted")),
        }

    def save(self, uid: str, body: Any, phone: Optional[str] = None) -> dict:
        avatar_path = self.avatar_uploader(uid, body.profile_image)
        now = datetime.now(timezone.utc).isoformat()
        public_ref = self.db.collection("drivers").document(uid)
        existing_snap = public_ref.get()
        existing = existing_snap.to_dict() if existing_snap.exists else {}
        public = {
            key: value for key, value in (existing or {}).items()
            if key not in SENSITIVE_PUBLIC_FIELDS
        }
        public.update({
            "driver_id": uid,
            "first_name": body.first_name.strip(),
            "middle_initial": body.middle_initial.strip().upper()[:1],
            "last_name": body.last_name.strip(),
            "email": body.email.strip().lower(),
            "phone": phone or body.phone,
            "driver_role": body.driver_role,
            "carrier_name": body.carrier_name.strip() if body.carrier_name else None,
            "business_name": body.business_name.strip() if body.business_name else None,
            "profile_image_path": avatar_path,
            "profile_complete": True,
            "updated_at": now,
        })
        private = {
            "driver_id": uid,
            "dob": body.dob,
            "cdl_number": body.cdl_number.strip().upper(),
            "cdl_state": body.cdl_state,
            "cdl_expiration": body.cdl_expiration,
            "address": body.address.model_dump(),
            "ssn_last4_encrypted": self.cipher.encrypt(
                body.ssn_last4,
                subject=uid,
                field="ssn_last4",
            ),
            "updated_at": now,
        }
        private_ref = self.db.collection("driver_private").document(uid)
        batch = self.db.batch()
        batch.set(public_ref, public)
        batch.set(private_ref, private)
        batch.commit()
        return self.get(uid, phone=phone)

    def edit_public(self, uid: str, body: Any, phone: Optional[str] = None) -> dict:
        """Edit non-verification profile fields without re-sending protected PII."""
        ref = self.db.collection("drivers").document(uid)
        snap = ref.get()
        if not snap.exists or not (snap.to_dict() or {}).get("profile_complete"):
            raise HTTPException(status_code=409, detail="Complete Driver setup before editing your profile.")
        ref.set({
            "email": body.email.strip().lower(),
            "driver_role": body.driver_role,
            "carrier_name": body.carrier_name.strip() if body.carrier_name else None,
            "business_name": body.business_name.strip() if body.business_name else None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, merge=True)
        return self.get(uid, phone=phone)
