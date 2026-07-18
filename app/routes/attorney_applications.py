"""
Attorney application pipeline (Dashboard spec Slice 2).

  POST /applications                                     PUBLIC — no auth, pre-account
  GET  /admin/attorney-applications                      staff review queue (x-api-key)
  POST /admin/attorney-applications/{id}/interview-complete   (x-api-key)
  POST /admin/attorney-applications/{id}/approve         provisions Auth + attorneys/ doc

Approval (§3.3): creates a Firebase Auth account, a password-set link, and the
attorneys/{uid} doc seeded with BOTH specs' default fields so downstream reads never
hit missing keys. junior/law_student require interview_complete before approval.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import firebase_admin.auth as fb_auth
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.routes._common import require_staff
from app.services import attorney_dashboard as dash
from app.services import attorney_levels as levels

logger = logging.getLogger(__name__)
router = APIRouter(tags=["attorney-applications"])

_INTERVIEW_REQUIRED_TIERS = {"junior", "law_student"}
_VALID_TIERS = {"senior", "junior", "law_student"}


def _db():
    from app.services.firebase_service import _init, _firestore_client
    _init()
    if _firestore_client is None:
        raise HTTPException(status_code=503, detail="Firestore not configured.")
    return _firestore_client


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


# ── Public application submission ─────────────────────────────────────────────
class ApplicationSubmission(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = None
    bar_number: Optional[str] = None
    bar_state: Optional[str] = None
    states_licensed: list[str] = []
    counties_covered: list[str] = []
    years_experience: Optional[int] = None
    tier_requested: str = "senior"
    firm_name: Optional[str] = None
    firm_city: Optional[str] = None
    firm_state: Optional[str] = None
    resume_url: Optional[str] = None
    bar_license_doc_url: Optional[str] = None
    malpractice_insurance_doc_url: Optional[str] = None
    referral_source: Optional[str] = None


@router.post("/applications")
def submit_application(body: ApplicationSubmission):
    """Public — an attorney applies to join the network. No auth (pre-account)."""
    db = _db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    if body.tier_requested not in _VALID_TIERS:
        raise HTTPException(status_code=400,
                            detail=f"tier_requested must be one of {sorted(_VALID_TIERS)}")

    application_id = str(uuid.uuid4())
    doc = {
        "full_name": body.full_name,
        "email": body.email.lower().strip(),
        "phone": body.phone,
        "bar_number": body.bar_number,
        "bar_state": (body.bar_state or "").upper() or None,
        "states_licensed": [s.upper() for s in body.states_licensed],
        "counties_covered": body.counties_covered,
        "years_experience": body.years_experience,
        "tier_requested": body.tier_requested,
        "firm_name": body.firm_name,
        "firm_city": body.firm_city,
        "firm_state": (body.firm_state or "").upper() or None,
        "resume_url": body.resume_url,
        "bar_license_doc_url": body.bar_license_doc_url,
        "malpractice_insurance_doc_url": body.malpractice_insurance_doc_url,
        "referral_source": body.referral_source,
        "status": "submitted",
        "interview_notes": None,
        "reviewed_by": None,
        "reviewed_at": None,
        "rejection_reason": None,
        "submitted_at": SERVER_TIMESTAMP,
    }
    db.collection("attorney_applications").document(application_id).set(doc)
    logger.warning("[applications] submitted id=%s email=%s tier=%s",
                   application_id, doc["email"], doc["tier_requested"])

    interview = body.tier_requested in _INTERVIEW_REQUIRED_TIERS
    return {
        "ok": True,
        "application_id": application_id,
        "interview_required": interview,
        # Concrete timeline, not "we'll be in touch soon" (brand voice §6).
        "message": (
            "Application received. We review new attorneys within 3 business days."
            + (" Your tier includes a short interview — we'll email you to schedule it."
               if interview else "")
        ),
    }


# ── Staff review queue ────────────────────────────────────────────────────────
@router.get("/admin/attorney-applications")
def list_applications(status: Optional[str] = None, limit: int = 100,
                      authorization: Optional[str] = Header(None)):
    require_staff(authorization)
    db = _db()
    query = db.collection("attorney_applications")
    if status:
        query = query.where("status", "==", status)
    apps = []
    application_emails = set()
    for d in query.limit(limit).stream():
        data = d.to_dict()
        data["application_id"] = d.id
        data["submitted_at"] = _iso(data.get("submitted_at"))
        data["reviewed_at"] = _iso(data.get("reviewed_at"))
        apps.append(data)
        application_emails.add((data.get("email") or "").lower())

    # Accounts created through /auth/bootstrap historically bypassed the public
    # application collection. Surface those provisioned, unapproved attorneys in
    # the same review queue so staff approval remains authoritative.
    if not status or status in {"submitted", "provisioned"}:
        for attorney_doc in db.collection("attorneys").where("status", "==", "provisioned").limit(limit).stream():
            attorney = attorney_doc.to_dict() or {}
            email = (attorney.get("email") or "").lower()
            if email in application_emails:
                continue
            apps.append({
                "application_id": f"account:{attorney_doc.id}",
                "attorney_id": attorney_doc.id,
                "full_name": attorney.get("full_name"),
                "email": email,
                "phone": attorney.get("phone"),
                "firm_name": attorney.get("firm_name"),
                "states_licensed": attorney.get("states_licensed") or attorney.get("states_covered") or [],
                "counties_covered": attorney.get("counties_covered") or [],
                "tier_requested": attorney.get("tier") or "senior",
                "status": "provisioned",
                "submitted_at": _iso(attorney.get("created_at")),
                "source": "attorney_signup",
            })
    apps.sort(key=lambda a: a.get("submitted_at") or "", reverse=True)
    return {"applications": apps, "count": len(apps)}


class InterviewComplete(BaseModel):
    reviewed_by: str
    interview_notes: Optional[str] = None


@router.post("/admin/attorney-applications/{application_id}/interview-complete")
def mark_interview_complete(application_id: str, body: InterviewComplete,
                            authorization: Optional[str] = Header(None)):
    require_staff(authorization)
    db = _db()
    ref = db.collection("attorney_applications").document(application_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Application not found.")
    ref.update({
        "status": "interview_complete",
        "interview_notes": body.interview_notes,
        "reviewed_by": body.reviewed_by,
        "reviewed_at": datetime.now(timezone.utc),
    })
    return {"ok": True, "application_id": application_id, "status": "interview_complete"}


# ── Approval → provisioning ───────────────────────────────────────────────────
class ApproveApplication(BaseModel):
    reviewed_by: str
    tier_override: Optional[str] = None      # staff may override tier_requested


@router.post("/admin/attorney-applications/{application_id}/approve")
def approve_application(application_id: str, body: ApproveApplication,
                        authorization: Optional[str] = Header(None)):
    require_staff(authorization)
    db = _db()
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    if application_id.startswith("account:"):
        uid = application_id.split(":", 1)[1]
        attorney_ref = db.collection("attorneys").document(uid)
        attorney_snap = attorney_ref.get()
        if not attorney_snap.exists:
            raise HTTPException(status_code=404, detail="Attorney account not found.")
        attorney_ref.update({
            "status": "onboarded", "application_status": "approved",
            "reviewed_by": body.reviewed_by, "reviewed_at": SERVER_TIMESTAMP,
            "onboarded_at": SERVER_TIMESTAMP,
        })
        return {"ok": True, "application_id": application_id, "attorney_id": uid,
                "tier": attorney_snap.to_dict().get("tier") or "senior"}

    ref = db.collection("attorney_applications").document(application_id)
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Application not found.")
    app_data = snap.to_dict()

    if app_data.get("status") == "approved":
        raise HTTPException(status_code=409, detail="Application already approved.")

    tier = body.tier_override or app_data.get("tier_requested") or "senior"
    if tier not in _VALID_TIERS:
        raise HTTPException(status_code=400, detail=f"Invalid tier '{tier}'.")

    # Interview gate for junior / law_student (§3.3).
    if tier in _INTERVIEW_REQUIRED_TIERS and app_data.get("status") != "interview_complete":
        raise HTTPException(
            status_code=400,
            detail=f"Tier '{tier}' requires interview_complete before approval "
                   f"(current status: {app_data.get('status')}).",
        )

    email = (app_data.get("email") or "").lower().strip()
    if not email:
        raise HTTPException(status_code=400, detail="Application has no email.")

    # ── Provision Firebase Auth account (idempotent on email) ─────────────────
    reset_link = None
    try:
        try:
            user = fb_auth.get_user_by_email(email)
        except fb_auth.UserNotFoundError:
            user = fb_auth.create_user(email=email, display_name=app_data.get("full_name"))
        uid = user.uid
        # Attorney role claim for downstream gating.
        try:
            fb_auth.set_custom_user_claims(uid, {"role": "attorney"})
        except Exception as exc:
            logger.warning("[applications] set_custom_claims failed uid=%s: %s", uid, exc)
        try:
            reset_link = fb_auth.generate_password_reset_link(email)
        except Exception as exc:
            logger.warning("[applications] password link failed email=%s: %s", email, exc)
    except Exception as exc:
        logger.error("[applications] Auth provisioning failed email=%s: %s", email, exc)
        raise HTTPException(status_code=502, detail=f"Auth provisioning failed: {exc}") from exc

    # ── Create attorneys/{uid} seeded with BOTH specs' defaults ───────────────
    attorney_doc = {
        **levels.default_level_fields(),
        **dash.dashboard_field_defaults(),
        "full_name": app_data.get("full_name"),
        "email": email,
        "phone": app_data.get("phone"),
        "tier": tier,                              # Experience Tier
        "bar_number": app_data.get("bar_number"),
        "bar_state": app_data.get("bar_state"),
        "states_covered": app_data.get("states_licensed", []),
        "counties_covered": app_data.get("counties_covered", []),
        "firm_name": app_data.get("firm_name"),
        "firm_city": app_data.get("firm_city"),
        "firm_state": app_data.get("firm_state"),
        "status": "onboarded",                     # attorney network status
        "application_status": "approved",
        "application_id": application_id,
        "cases_active": 0,
        "created_at": SERVER_TIMESTAMP,
        "onboarded_at": SERVER_TIMESTAMP,
    }
    db.collection("attorneys").document(uid).set(attorney_doc, merge=True)

    ref.update({
        "status": "approved",
        "reviewed_by": body.reviewed_by,
        "reviewed_at": datetime.now(timezone.utc),
        "provisioned_uid": uid,
    })

    logger.warning("[applications] APPROVED id=%s → attorney uid=%s tier=%s",
                   application_id, uid, tier)
    return {
        "ok": True,
        "application_id": application_id,
        "attorney_id": uid,
        "tier": tier,
        "password_set_link": reset_link,   # staff can relay if email delivery is deferred
    }


class RejectApplication(BaseModel):
    reason: str
    rejected_by: Optional[str] = None


@router.post("/admin/attorney-applications/{application_id}/reject")
def reject_application(application_id: str, body: RejectApplication,
                       authorization: Optional[str] = Header(None)):
    actor = require_staff(authorization)
    db = _db()
    update = {
        "status": "rejected", "rejection_reason": body.reason,
        "reviewed_by": body.rejected_by or actor.get("email") or actor.get("uid"),
        "reviewed_at": datetime.now(timezone.utc),
    }
    if application_id.startswith("account:"):
        uid = application_id.split(":", 1)[1]
        ref = db.collection("attorneys").document(uid)
    else:
        ref = db.collection("attorney_applications").document(application_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Application not found.")
    ref.update(update)
    return {"ok": True, "application_id": application_id, "status": "rejected"}
