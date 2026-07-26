"""
Agent on/off configuration — staff can disable enrichment-only pipeline agents
without a deploy. Structural/routing agents (extraction passes, GREEN/YELLOW/RED
scoring) are never toggleable — disabling them would break the pipeline's control
flow, not just skip an enrichment step.

Scoped to the current agents tracked by GET /admin/stats/agents (admin.py) so
every toggle's effect is visible in the existing Agents tab and new agents cannot
silently drift out of staff visibility.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.routes._common import get_db, require_staff
from app.services.auth_rbac import require_recent_auth, require_staff as require_staff_claim
from app.services.agent_identity import agent_identity_payload
from app.services.staff_audit import write_staff_audit

router = APIRouter(tags=["admin-agent-config"])

# name → one-line reason it can/can't be toggled
STRUCTURAL_AGENTS = {
    "roux": "Intake validation gate — disabling would let malformed submissions through.",
    "document_gate": "Routes photos, documents, and unknown files before extraction.",
    "photo_analyst": "Handles photo submissions on the photo-only path.",
    "carver": "Primary extraction pass — the pipeline has nothing to score or enrich without it.",
    "bolin":     "GREEN/YELLOW/RED quality routing — disabling breaks pipeline control flow.",
    "bunche":   "Merges dual extraction passes on non-green tickets — structural to the YELLOW/RED path.",
    "banneker": "Jurisdiction enrichment used before attorney matching.",
    "madam_walker": "Attorney matching node that prepares case routing.",
    "douglass": "Builds attorney prep context from driver statements and evidence.",
}
TOGGLEABLE_AGENTS = {
    "charlotte_ray":              "CDL point/severity enrichment.",
    "ida_wells":  "Missing-field audit for attorney prep.",
    "jollof":               "CDL identity verification against the driver's Firestore profile.",
    "stagecoach_mary":             "Motor Vehicle Record pull request.",
    "bass_reeves":             "FMCSA PSP report pull request.",
    "tubman":          "Court-date-proximity urgency scoring.",
}


@router.get("/admin/agent-config")
def list_agent_config(authorization: Optional[str] = Header(None)):
    require_staff(authorization)
    db = get_db()
    configs = {}
    for name in TOGGLEABLE_AGENTS:
        snap = db.collection("agent_config").document(name).get()
        data = snap.to_dict() if snap.exists else {}
        configs[name] = {
            "enabled": data.get("enabled", True),
            "version": data.get("version", 0),
            "updated_at": data.get("updated_at"),
            "updated_by": data.get("updated_by"),
        }

    return {
        "structural": [
            {
                "agent": name,
                "name": agent_identity_payload(name)["honor_name"],
                "legacy_name": agent_identity_payload(name)["legacy_name"],
                "toggleable": False,
                "reason": reason,
                "identity": agent_identity_payload(name),
            }
            for name, reason in STRUCTURAL_AGENTS.items()
        ],
        "toggleable": [
            {
                "agent": name,
                "name": agent_identity_payload(name)["honor_name"],
                "legacy_name": agent_identity_payload(name)["legacy_name"],
                "toggleable": True,
                "reason": reason,
                **configs[name],
                "identity": agent_identity_payload(name),
            }
            for name, reason in TOGGLEABLE_AGENTS.items()
        ],
    }


class AgentConfigUpdate(BaseModel):
    enabled: bool
    expected_version: int = Field(ge=0)
    reason: str = Field(min_length=8, max_length=500)


@router.patch("/admin/agent-config/{agent_name}")
def update_agent_config(agent_name: str, body: AgentConfigUpdate, authorization: Optional[str] = Header(None)):
    decoded = require_staff(authorization)
    require_staff_claim(decoded, ["admin", "engineering"])
    require_recent_auth(decoded)
    if agent_name not in TOGGLEABLE_AGENTS:
        if agent_name in STRUCTURAL_AGENTS:
            raise HTTPException(
                status_code=400,
                detail=f"'{agent_name}' is structural and cannot be disabled: {STRUCTURAL_AGENTS[agent_name]}",
            )
        raise HTTPException(status_code=404, detail=f"Unknown agent '{agent_name}'.")

    db = get_db()
    ref = db.collection("agent_config").document(agent_name)
    snap = ref.get()
    before = snap.to_dict() if snap.exists else {"enabled": True, "version": 0}
    current_version = before.get("version", 0)
    current_enabled = before.get("enabled", True)

    if current_version != body.expected_version:
        raise HTTPException(
            status_code=409,
            detail=f"Agent configuration changed (expected version {body.expected_version}, current version {current_version}). Refresh and try again.",
        )

    if current_enabled == body.enabled:
        return {
            "ok": True,
            "changed": False,
            "agent": agent_name,
            "enabled": body.enabled,
            "version": current_version,
        }

    after = {
        "enabled": body.enabled,
        "version": current_version + 1,
        "updated_at": datetime.now(timezone.utc),
        "updated_by": decoded.get("email") or decoded.get("uid"),
    }
    ref.set(after, merge=True)
    if not write_staff_audit(
        db,
        decoded,
        "agent.enabled" if body.enabled else "agent.disabled",
        "pipeline_agent",
        agent_name,
        before=before,
        after=after,
        reason=body.reason,
    ):
        ref.set(before)
        raise HTTPException(
            status_code=503,
            detail="The change was not saved because its required audit record could not be written.",
        )
    return {
        "ok": True,
        "changed": True,
        "agent": agent_name,
        "enabled": body.enabled,
        "version": after["version"],
    }
