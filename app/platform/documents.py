"""WP-03 secure document lifecycle contracts and validation."""
from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, Protocol

from pydantic import BaseModel, Field

from app.platform.models import utc_now


class DocumentStatus(str, Enum):
    QUARANTINED = "quarantined"
    SCAN_PENDING = "scan_pending"
    UNSAFE = "unsafe"
    READY = "ready"
    CLASSIFYING = "classifying"
    EXTRACTING = "extracting"
    REVIEW_REQUIRED = "review_required"
    VERIFIED = "verified"
    FAILED = "failed"


class ScanResult(str, Enum):
    CLEAN = "clean"
    UNSAFE = "unsafe"
    UNAVAILABLE = "unavailable"


class MalwareScanner(Protocol):
    def scan(self, content: bytes) -> ScanResult: ...


class SafeFallbackScanner:
    """Never marks a file clean when the production scanner is unavailable."""

    EICAR = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"

    def scan(self, content: bytes) -> ScanResult:
        if self.EICAR in content:
            return ScanResult.UNSAFE
        return ScanResult.UNAVAILABLE


class DocumentAsset(BaseModel):
    id: str
    owner_principal_id: str
    filename: str
    original_filename: Optional[str] = None
    naming_policy_version: Optional[str] = None
    naming_department: Optional[str] = None
    naming_case: Optional[str] = None
    content_type: str
    byte_size: int
    sha256: str
    version: int = 1
    status: DocumentStatus
    malware_scan_result: ScanResult
    storage_path: Optional[str] = None
    duplicate_of: Optional[str] = None
    retention_class: str = "driver_legal_record"
    classification: Optional[str] = None
    extraction_run_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ExtractionField(BaseModel):
    field_name: str
    value: str
    confidence: float = Field(ge=0, le=1)
    page: Optional[int] = Field(default=None, ge=1)
    bounding_box: Optional[dict[str, float]] = None
    raw_evidence: Optional[str] = None
    corrected_value: Optional[str] = None
    verified: bool = False


class ExtractionRun(BaseModel):
    id: str
    document_id: str
    document_version: int
    status: str = "review_required"
    classifier_version: str
    extractor_version: str
    model_provider: str
    model_name: str
    prompt_version: str
    input_sha256: str
    fields: list[ExtractionField] = Field(default_factory=list)
    reviewer_principal_id: Optional[str] = None
    verified_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utc_now)


class DocumentJob(BaseModel):
    id: str
    document_id: str
    owner_principal_id: str
    document_version: int
    status: str = Field(default="queued", pattern="^(queued|running|review_required|completed|failed)$")
    attempts: int = 0
    max_attempts: int = 3
    correlation_id: str
    error_code: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


ALLOWED_CONTENT_TYPES = {
    "application/pdf": (b"%PDF",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
}
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024


def sanitize_filename(filename: str) -> str:
    base = filename.replace("\\", "/").split("/")[-1]
    cleaned = re.sub(r"[^A-Za-z0-9._ -]", "_", base).strip(" .")
    return cleaned[:180] or "document"


def validate_upload(filename: str, content_type: str, content: bytes) -> tuple[str, str]:
    if not content or len(content) > MAX_DOCUMENT_BYTES:
        raise ValueError("Document must be between 1 byte and 20 MB.")
    signatures = ALLOWED_CONTENT_TYPES.get(content_type)
    if not signatures or not any(content.startswith(signature) for signature in signatures):
        raise ValueError("File content does not match an allowed PDF, JPEG, or PNG type.")
    return sanitize_filename(filename), hashlib.sha256(content).hexdigest()


def new_document_id() -> str:
    return f"doc_{uuid.uuid4().hex}"
