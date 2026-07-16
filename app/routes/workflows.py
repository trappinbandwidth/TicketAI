"""Feature-flagged WP-04 workflow and notification APIs."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.platform.service import principal_id_for_uid
from app.platform.workflow_service import WorkflowService
from app.platform.workflows import NotificationPreferences, WorkflowTaskCreate, WorkflowType
from app.services.auth_rbac import STAFF_ROLES, verify_firebase_token


router = APIRouter(prefix="/workflows", tags=["tip-os-workflows"])


class CreateWorkflowRequest(BaseModel):
    workflow_type: WorkflowType
    subject_principal_id: str
    resource_type: str = Field(min_length=1, max_length=80)
    resource_id: str = Field(min_length=1, max_length=200)
    tenant_id: Optional[str] = None
    deadline_at: Optional[datetime] = None
    deadline_basis: Optional[str] = Field(default=None, max_length=500)
    deadline_source_ref: Optional[str] = Field(default=None, max_length=300)
    deadline_confidence: Optional[float] = Field(default=None, ge=0, le=1)


class TransitionRequest(BaseModel):
    to_state: str
    reason: Optional[str] = Field(default=None, max_length=1000)
    approval_id: Optional[str] = None


class ApprovalRequest(BaseModel):
    action: str
    approved: bool
    reason: str = Field(min_length=1, max_length=1000)


class CompleteTaskRequest(BaseModel):
    evidence_ids: list[str] = Field(default_factory=list)
    waiver_reason: Optional[str] = Field(default=None, max_length=1000)


def _claims(authorization: Optional[str]) -> dict:
    if os.getenv("TIP_OS_WORKFLOWS_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Workflow APIs are not enabled.")
    return verify_firebase_token(authorization)


def _actor(claims: dict) -> str:
    uid = claims.get("uid") or claims.get("sub")
    if not uid:
        raise HTTPException(status_code=401, detail="Token does not identify a user.")
    return principal_id_for_uid(uid)


def _staff(claims: dict) -> bool:
    return claims.get("role") in STAFF_ROLES or claims.get("staff_role") in STAFF_ROLES


def _service() -> WorkflowService:
    from app.services import firebase_service

    firebase_service._init()
    if firebase_service._firestore_client is None:
        raise HTTPException(status_code=503, detail="Workflow store unavailable.")
    return WorkflowService(firebase_service._firestore_client)


def _authorized(service: WorkflowService, actor_id: str, workflow_id: str, claims: dict):
    workflow = service.get(workflow_id)
    if workflow.subject_principal_id != actor_id and not _staff(claims):
        raise HTTPException(status_code=403, detail="Workflow access denied.")
    return workflow


@router.post("", status_code=201)
def create_workflow(body: CreateWorkflowRequest, authorization: Optional[str] = Header(None)):
    claims = _claims(authorization)
    actor_id = _actor(claims)
    if body.subject_principal_id != actor_id and not _staff(claims):
        raise HTTPException(status_code=403, detail="Workflow subject access denied.")
    workflow, created = _service().create(
        actor_id,
        body.workflow_type,
        body.subject_principal_id,
        body.resource_type,
        body.resource_id,
        **body.model_dump(exclude={
            "workflow_type", "subject_principal_id", "resource_type", "resource_id"
        }),
    )
    return {"workflow": workflow, "created": created}


@router.get("/{workflow_id}")
def get_workflow(workflow_id: str, authorization: Optional[str] = Header(None)):
    claims = _claims(authorization)
    actor_id = _actor(claims)
    try:
        return {"workflow": _authorized(_service(), actor_id, workflow_id, claims)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{workflow_id}/transitions")
def transition_workflow(
    workflow_id: str, body: TransitionRequest, authorization: Optional[str] = Header(None)
):
    claims = _claims(authorization)
    actor_id = _actor(claims)
    service = _service()
    try:
        _authorized(service, actor_id, workflow_id, claims)
        workflow = service.transition(
            actor_id, workflow_id, body.to_state, body.reason, body.approval_id
        )
        return {"workflow": workflow}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{workflow_id}/approvals", status_code=201)
def approve_workflow(
    workflow_id: str, body: ApprovalRequest, authorization: Optional[str] = Header(None)
):
    claims = _claims(authorization)
    actor_id = _actor(claims)
    service = _service()
    try:
        _authorized(service, actor_id, workflow_id, claims)
        return {"approval": service.approve(
            actor_id, workflow_id, body.action, body.approved, body.reason
        )}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{workflow_id}/tasks", status_code=201)
def create_task(
    workflow_id: str, body: WorkflowTaskCreate, authorization: Optional[str] = Header(None)
):
    claims = _claims(authorization)
    actor_id = _actor(claims)
    service = _service()
    try:
        _authorized(service, actor_id, workflow_id, claims)
        return {"task": service.create_task(actor_id, workflow_id, body)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/complete")
def complete_task(
    task_id: str, body: CompleteTaskRequest, authorization: Optional[str] = Header(None)
):
    claims = _claims(authorization)
    actor_id = _actor(claims)
    service = _service()
    try:
        task = service.get_task(task_id)
        _authorized(service, actor_id, task.workflow_id, claims)
        return {"task": service.complete_task(
            actor_id, task_id, body.evidence_ids, body.waiver_reason
        )}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/me/notification-preferences")
def set_notification_preferences(
    body: NotificationPreferences, authorization: Optional[str] = Header(None)
):
    actor_id = _actor(_claims(authorization))
    try:
        return {"preferences": _service().set_preferences(actor_id, body)}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
