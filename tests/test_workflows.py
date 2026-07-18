from datetime import datetime, timezone

import pytest

from app.platform.workflow_service import WorkflowService
from app.platform.workflows import (
    NotificationPreferences,
    WORKFLOW_DEFINITIONS,
    WorkflowTaskCreate,
    WorkflowType,
)
from tests.test_platform_identity import FakeDb


def test_each_workflow_rejects_invalid_transition_and_preserves_history():
    for workflow_type in WorkflowType:
        service = WorkflowService(FakeDb())
        workflow, created = service.create(
            "prn_driver", workflow_type, "prn_driver", workflow_type.value, "resource-1"
        )

        assert created is True
        assert workflow.definition_version == WORKFLOW_DEFINITIONS[workflow_type]["version"]
        with pytest.raises(ValueError, match="Invalid transition"):
            service.transition("prn_driver", workflow.id, "not-a-state")
        assert service.get(workflow.id).history[0].to_state == workflow.current_state


def test_consequential_transition_requires_matching_human_approval():
    service = WorkflowService(FakeDb())
    workflow, _ = service.create(
        "prn_driver", WorkflowType.CASE, "prn_driver", "case", "case-1"
    )
    workflow = service.transition("prn_ops", workflow.id, "conflict_check")
    workflow = service.transition("prn_ops", workflow.id, "offered")
    workflow = service.transition("prn_driver", workflow.id, "engagement_pending")

    with pytest.raises(PermissionError, match="human approval"):
        service.transition("prn_driver", workflow.id, "active")
    rejected = service.approve("prn_driver", workflow.id, "active", False, "Declined terms")
    with pytest.raises(PermissionError, match="approved action"):
        service.transition("prn_driver", workflow.id, "active", approval_id=rejected.id)
    approval = service.approve("prn_driver", workflow.id, "active", True, "Accepted engagement")
    active = service.transition("prn_driver", workflow.id, "active", approval_id=approval.id)

    assert active.current_state == "active"
    assert active.history[-1].approval_id == approval.id


def test_task_dependencies_and_evidence_are_enforced():
    service = WorkflowService(FakeDb())
    workflow, _ = service.create(
        "prn_driver", WorkflowType.DATAQS, "prn_driver", "inspection", "inspection-1"
    )
    evidence = service.create_task(
        "prn_safety", workflow.id,
        WorkflowTaskCreate(title="Collect inspection report", requires_evidence=True),
    )
    package = service.create_task(
        "prn_safety", workflow.id,
        WorkflowTaskCreate(title="Prepare package", dependency_ids=[evidence.id]),
    )

    with pytest.raises(ValueError, match="dependencies"):
        service.complete_task("prn_safety", package.id, [])
    with pytest.raises(ValueError, match="evidence"):
        service.complete_task("prn_safety", evidence.id, [])
    completed = service.complete_task("prn_safety", evidence.id, ["doc_1"])
    package = service.complete_task("prn_safety", package.id, [])

    assert completed.status.value == "completed"
    assert package.status.value == "completed"


def test_deadline_metadata_is_utc_and_source_aware():
    service = WorkflowService(FakeDb())
    workflow, _ = service.create(
        "prn_driver",
        WorkflowType.CREDENTIAL,
        "prn_driver",
        "credential",
        "cdl-1",
        deadline_at=datetime(2026, 8, 1, 5, 0, tzinfo=timezone.utc),
        deadline_basis="CDL expiration date",
        deadline_source_ref="rec_credential",
        deadline_confidence=1.0,
    )

    assert workflow.deadline_at.tzinfo is not None
    assert workflow.deadline_basis == "CDL expiration date"
    assert workflow.deadline_source_ref == "rec_credential"


def test_notification_preferences_dedupe_and_disclosed_urgent_override():
    service = WorkflowService(FakeDb())
    preferences = service.set_preferences(
        "prn_driver",
        NotificationPreferences(
            principal_id="prn_driver",
            email=False,
            sms=False,
            push=False,
            urgent_deadline_override=True,
        ),
    )
    first, created = service.create_alert(
        "prn_driver", "Court deadline", "Respond today", "urgent",
        "deadline:case-1:2026-07-16", "corr-1",
    )
    second, created_again = service.create_alert(
        "prn_driver", "Court deadline", "Respond today", "urgent",
        "deadline:case-1:2026-07-16", "corr-1",
    )

    assert preferences.disclosure_version == "notifications-v1"
    assert created is True and created_again is False
    assert first.id == second.id
    assert set(first.channels) == {"in_app", "email", "sms", "push"}


def test_preferences_are_owner_controlled():
    service = WorkflowService(FakeDb())
    with pytest.raises(PermissionError):
        service.set_preferences(
            "prn_other", NotificationPreferences(principal_id="prn_driver")
        )


def test_same_external_resource_id_does_not_cross_driver_boundary():
    service = WorkflowService(FakeDb())
    first, _ = service.create(
        "prn_a", WorkflowType.TICKET, "prn_a", "ticket", "shared-external-id"
    )
    second, _ = service.create(
        "prn_b", WorkflowType.TICKET, "prn_b", "ticket", "shared-external-id"
    )

    assert first.id != second.id
    assert first.subject_principal_id != second.subject_principal_id
