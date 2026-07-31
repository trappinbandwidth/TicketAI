from datetime import datetime, timedelta, timezone

import pytest

from app.services.file_naming import (
    FileDepartment,
    governed_file_name,
    opaque_storage_object,
)


def test_canonical_case_filename_uses_last_first_department_case_and_utc_date():
    result = governed_file_name(
        subject_name="Jane María Doe",
        department=FileDepartment.DRIVER,
        case_id="CASE-10482",
        general_id=None,
        uploaded_at=datetime(2026, 7, 27, 1, 30, tzinfo=timezone(timedelta(hours=2))),
        content_type="application/pdf",
    )

    assert result.display_name == "Doe-Jane-Maria_DRIVER_CASE-10482_2026-07-26.pdf"
    assert result.policy_version == "file-name-v1"


def test_general_document_and_collision_version_are_deterministic():
    values = {
        "subject_name": "Prince",
        "department": "RECORDS",
        "case_id": None,
        "general_id": "doc_a1b2c3d4",
        "uploaded_at": datetime(2026, 7, 26, tzinfo=timezone.utc),
        "content_type": "image/jpeg",
        "collision_version": 2,
    }

    first = governed_file_name(**values)
    second = governed_file_name(**values)

    assert first == second
    assert first.display_name == "Prince_RECORDS_GENERAL-doc-a1b2c3d4_2026-07-26_v02.jpg"


def test_unsafe_components_are_sanitized_and_length_is_bounded():
    result = governed_file_name(
        subject_name="../../ Jane O'Connor",
        department="ATTORNEY",
        case_id="../../CASE 55",
        general_id=None,
        uploaded_at=datetime(2026, 7, 26, tzinfo=timezone.utc),
        content_type="image/png",
    )
    assert "/" not in result.display_name
    assert "'" not in result.display_name
    assert len(result.display_name) <= 120
    assert result.display_name.endswith(".png")


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"subject_name": " ", "case_id": "C1"}, "subject name"),
        ({"subject_name": "Jane Doe", "case_id": None}, "case ID"),
        ({"subject_name": "Jane Doe", "case_id": "C1", "department": "SALES"}, "Department"),
        ({"subject_name": "Jane Doe", "case_id": "C1", "content_type": "text/plain"}, "content type"),
    ],
)
def test_missing_or_unapproved_metadata_is_rejected(kwargs, message):
    values = {
        "subject_name": "Jane Doe",
        "department": "DRIVER",
        "case_id": None,
        "general_id": None,
        "uploaded_at": datetime(2026, 7, 26, tzinfo=timezone.utc),
        "content_type": "application/pdf",
    }
    values.update(kwargs)
    with pytest.raises(ValueError, match=message):
        governed_file_name(**values)


def test_storage_object_is_opaque_and_media_type_controls_extension():
    assert opaque_storage_object("doc_12345678", "application/pdf") == "doc_12345678.pdf"
    with pytest.raises(ValueError):
        opaque_storage_object("../../Jane_Doe", "application/pdf")
