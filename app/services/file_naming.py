"""Deterministic, privacy-aware display names for uploaded files."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


NAMING_POLICY_VERSION = "file-name-v1"
MAX_DISPLAY_NAME_LENGTH = 120

CONTENT_TYPE_EXTENSIONS = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
}


class FileDepartment(str, Enum):
    DRIVER = "DRIVER"
    CARRIER = "CARRIER"
    ATTORNEY = "ATTORNEY"
    CAPTAIN = "CAPTAIN"
    LEGAL = "LEGAL"
    COMPLIANCE = "COMPLIANCE"
    RESTORATION = "RESTORATION"
    ADVISORY = "ADVISORY"
    NETWORK = "NETWORK"
    RECORDS = "RECORDS"


@dataclass(frozen=True)
class GovernedFileName:
    display_name: str
    policy_version: str
    department: str
    case_component: str
    uploaded_date: str
    collision_version: int


def _ascii_component(value: str, *, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", ascii_value).strip("-")
    return cleaned or fallback


def _person_component(subject_name: str) -> str:
    parts = [
        _ascii_component(part, fallback="")
        for part in subject_name.strip().split()
    ]
    parts = [part for part in parts if part]
    if not parts:
        raise ValueError("An authorized subject name is required.")
    if len(parts) == 1:
        return parts[0]
    return f"{parts[-1]}-{'-'.join(parts[:-1])}"


def _fit_components(components: list[str], suffix: str) -> str:
    available = MAX_DISPLAY_NAME_LENGTH - len(suffix)
    if available < len(components):
        raise ValueError("Filename policy components exceed the supported length.")
    fitted = list(components)
    while len("_".join(fitted)) > available:
        longest = max(range(len(fitted)), key=lambda index: len(fitted[index]))
        if len(fitted[longest]) <= 1:
            raise ValueError("Filename policy components cannot be shortened safely.")
        fitted[longest] = fitted[longest][:-1]
    return "_".join(fitted) + suffix


def governed_file_name(
    *,
    subject_name: str,
    department: FileDepartment | str,
    case_id: str | None,
    general_id: str | None,
    uploaded_at: datetime,
    content_type: str,
    collision_version: int = 1,
    entity_name: bool = False,
) -> GovernedFileName:
    """Return the canonical display name without using document content."""
    try:
        department_value = FileDepartment(department).value
    except ValueError as exc:
        raise ValueError("Department is not an approved file-naming code.") from exc
    extension = CONTENT_TYPE_EXTENSIONS.get(content_type)
    if extension is None:
        raise ValueError("Validated content type has no approved file extension.")
    if uploaded_at.tzinfo is None:
        raise ValueError("Upload timestamp must include a timezone.")
    if collision_version < 1 or collision_version > 99:
        raise ValueError("Collision version must be between 1 and 99.")

    if case_id and case_id.strip():
        case_component = _ascii_component(case_id, fallback="")
    elif general_id and general_id.strip():
        case_component = f"GENERAL-{_ascii_component(general_id, fallback='')}"
    else:
        raise ValueError("A case ID or stable general-document ID is required.")
    if not case_component or case_component == "GENERAL-":
        raise ValueError("A case ID or stable general-document ID is required.")

    uploaded_date = uploaded_at.astimezone(timezone.utc).date().isoformat()
    version_suffix = "" if collision_version == 1 else f"_v{collision_version:02d}"
    suffix = f"{version_suffix}.{extension}"
    display_name = _fit_components(
        [
            (
                _ascii_component(subject_name, fallback="")
                if entity_name
                else _person_component(subject_name)
            ),
            department_value,
            case_component,
            uploaded_date,
        ],
        suffix,
    )
    return GovernedFileName(
        display_name=display_name,
        policy_version=NAMING_POLICY_VERSION,
        department=department_value,
        case_component=case_component,
        uploaded_date=uploaded_date,
        collision_version=collision_version,
    )


def opaque_storage_object(document_id: str, content_type: str) -> str:
    """Build a non-PII object name from a server-issued document identifier."""
    safe_id = re.fullmatch(r"[A-Za-z0-9_-]{8,100}", document_id)
    extension = CONTENT_TYPE_EXTENSIONS.get(content_type)
    if safe_id is None or extension is None:
        raise ValueError("Opaque document ID or content type is invalid.")
    return f"{document_id}.{extension}"
