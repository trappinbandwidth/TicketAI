"""Persistence and deterministic transition rules for WP-04."""
from __future__ import annotations

import uuid

from app.platform.models import utc_now
from app.platform.workflows import (
    Alert,
    Approval,
    NotificationPreferences,
    TaskStatus,
    WORKFLOW_DEFINITIONS,
    WorkflowHistory,
    WorkflowInstance,
    WorkflowTask,
    WorkflowTaskCreate,
    WorkflowType,
    new_workflow,
)


class WorkflowService:
    def __init__(self, db):
        self.db = db

    def _audit(self, actor_id: str, event_type: str, entity_type: str, entity_id: str, correlation_id: str, payload=None):
        event_id = f"audit_{uuid.uuid4().hex}"
        self.db.collection("audit_events").document(event_id).set({
            "id": event_id, "actor_id": actor_id, "event_type": event_type,
            "entity_type": entity_type, "entity_id": entity_id,
            "correlation_id": correlation_id, "payload": payload or {},
            "created_at": utc_now().isoformat(),
        })

    def create(self, actor_id: str, workflow_type: WorkflowType, subject_id: str, resource_type: str, resource_id: str, **kwargs):
        existing = self.db.collection("workflow_instances").where("resource_id", "==", resource_id).stream()
        for item in existing:
            workflow = WorkflowInstance.model_validate(item.to_dict())
            if (
                workflow.workflow_type == workflow_type
                and workflow.subject_principal_id == subject_id
                and workflow.resource_type == resource_type
            ):
                return workflow, False
        workflow = new_workflow(workflow_type, subject_id, resource_type, resource_id, actor_id, **kwargs)
        self.db.collection("workflow_instances").document(workflow.id).set(workflow.model_dump(mode="json"))
        self._audit(actor_id, "workflow.created", "workflow", workflow.id, workflow.correlation_id)
        return workflow, True

    def get(self, workflow_id: str) -> WorkflowInstance:
        snapshot = self.db.collection("workflow_instances").document(workflow_id).get()
        if not getattr(snapshot, "exists", False):
            raise LookupError("Workflow not found.")
        return WorkflowInstance.model_validate(snapshot.to_dict())

    def list_for_subject(self, subject_id: str) -> list[WorkflowInstance]:
        snapshots = self.db.collection("workflow_instances").where(
            "subject_principal_id", "==", subject_id
        ).stream()
        workflows = [WorkflowInstance.model_validate(item.to_dict()) for item in snapshots]
        return sorted(workflows, key=lambda item: item.updated_at, reverse=True)

    def transition(self, actor_id: str, workflow_id: str, to_state: str, reason: str | None = None, approval_id: str | None = None):
        workflow = self.get(workflow_id)
        definition = WORKFLOW_DEFINITIONS[workflow.workflow_type]
        allowed = definition["transitions"].get(workflow.current_state, set())
        if to_state not in allowed:
            raise ValueError(f"Invalid transition: {workflow.current_state} -> {to_state}")
        if to_state in definition["approval_actions"]:
            if not approval_id:
                raise PermissionError("Recorded human approval is required.")
            approval = self.get_approval(approval_id)
            if approval.workflow_id != workflow_id or approval.action != to_state or approval.status != "approved":
                raise PermissionError("Matching approved action is required.")
        prior = workflow.current_state
        workflow.current_state = to_state
        workflow.updated_at = utc_now()
        workflow.history.append(WorkflowHistory(
            from_state=prior, to_state=to_state, actor_principal_id=actor_id,
            reason=reason, approval_id=approval_id,
        ))
        self.db.collection("workflow_instances").document(workflow.id).set(workflow.model_dump(mode="json"))
        self._audit(actor_id, "workflow.transitioned", "workflow", workflow.id, workflow.correlation_id, {
            "from_state": prior, "to_state": to_state, "approval_id": approval_id,
        })
        return workflow

    def approve(self, actor_id: str, workflow_id: str, action: str, approved: bool, reason: str):
        self.get(workflow_id)
        approval = Approval(
            id=f"apr_{uuid.uuid4().hex}", workflow_id=workflow_id, action=action,
            approver_principal_id=actor_id, status="approved" if approved else "rejected", reason=reason,
        )
        self.db.collection("workflow_approvals").document(approval.id).set(approval.model_dump(mode="json"))
        workflow = self.get(workflow_id)
        self._audit(actor_id, "workflow.approval_recorded", "approval", approval.id, workflow.correlation_id, {
            "action": action, "status": approval.status,
        })
        return approval

    def get_approval(self, approval_id: str) -> Approval:
        snapshot = self.db.collection("workflow_approvals").document(approval_id).get()
        if not getattr(snapshot, "exists", False):
            raise LookupError("Approval not found.")
        return Approval.model_validate(snapshot.to_dict())

    def create_task(self, actor_id: str, workflow_id: str, body: WorkflowTaskCreate):
        self.get(workflow_id)
        task = WorkflowTask(id=f"tsk_{uuid.uuid4().hex}", workflow_id=workflow_id, **body.model_dump())
        if body.dependency_ids:
            task.status = TaskStatus.BLOCKED
        self.db.collection("workflow_tasks").document(task.id).set(task.model_dump(mode="json"))
        workflow = self.get(workflow_id)
        self._audit(actor_id, "workflow.task_created", "task", task.id, workflow.correlation_id)
        return task

    def get_task(self, task_id: str) -> WorkflowTask:
        snapshot = self.db.collection("workflow_tasks").document(task_id).get()
        if not getattr(snapshot, "exists", False):
            raise LookupError("Task not found.")
        return WorkflowTask.model_validate(snapshot.to_dict())

    def list_tasks(self, workflow_id: str) -> list[WorkflowTask]:
        snapshots = self.db.collection("workflow_tasks").where(
            "workflow_id", "==", workflow_id
        ).stream()
        return [WorkflowTask.model_validate(item.to_dict()) for item in snapshots]

    def complete_task(self, actor_id: str, task_id: str, evidence_ids: list[str], waiver_reason: str | None = None):
        ref = self.db.collection("workflow_tasks").document(task_id)
        task = self.get_task(task_id)
        for dependency_id in task.dependency_ids:
            dependency = WorkflowTask.model_validate(
                self.db.collection("workflow_tasks").document(dependency_id).get().to_dict()
            )
            if dependency.status not in {TaskStatus.COMPLETED, TaskStatus.WAIVED}:
                raise ValueError("Task dependencies are incomplete.")
        if task.requires_evidence and not evidence_ids and not waiver_reason:
            raise ValueError("Completion evidence or a formal waiver is required.")
        task.status = TaskStatus.WAIVED if waiver_reason else TaskStatus.COMPLETED
        task.completion_evidence_ids = evidence_ids
        task.waiver_reason = waiver_reason
        task.completed_by = actor_id
        task.completed_at = utc_now()
        task.updated_at = utc_now()
        ref.set(task.model_dump(mode="json"))
        workflow = self.get(task.workflow_id)
        self._audit(actor_id, "workflow.task_completed", "task", task.id, workflow.correlation_id, {
            "status": task.status.value,
        })
        return task

    def set_preferences(self, actor_id: str, preferences: NotificationPreferences):
        if actor_id != preferences.principal_id:
            raise PermissionError("Notification preferences are owner-controlled.")
        preferences.updated_at = utc_now()
        self.db.collection("notification_preferences").document(actor_id).set(preferences.model_dump(mode="json"))
        self._audit(actor_id, "notifications.preferences_updated", "principal", actor_id, f"prefs-{actor_id}")
        return preferences

    def create_alert(self, principal_id: str, title: str, message: str, severity: str, dedupe_key: str, correlation_id: str, workflow_id: str | None = None):
        existing = self.db.collection("alerts").where("dedupe_key", "==", dedupe_key).stream()
        for item in existing:
            return Alert.model_validate(item.to_dict()), False
        pref_snapshot = self.db.collection("notification_preferences").document(principal_id).get()
        preferences = (
            NotificationPreferences.model_validate(pref_snapshot.to_dict())
            if getattr(pref_snapshot, "exists", False)
            else NotificationPreferences(principal_id=principal_id)
        )
        channels = [
            channel for channel in ("in_app", "email", "sms", "push")
            if getattr(preferences, channel)
        ]
        if severity == "urgent" and preferences.urgent_deadline_override:
            channels = sorted(set(channels) | {"in_app", "email", "sms", "push"})
        alert = Alert(
            id=f"alt_{uuid.uuid4().hex}", principal_id=principal_id, workflow_id=workflow_id,
            severity=severity, title=title, message=message, channels=channels,
            dedupe_key=dedupe_key, correlation_id=correlation_id,
        )
        self.db.collection("alerts").document(alert.id).set(alert.model_dump(mode="json"))
        self._audit("system", "alert.created", "alert", alert.id, correlation_id, {
            "severity": severity, "channels": channels,
        })
        return alert, True
