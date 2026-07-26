from fastapi import HTTPException
import pytest

from app.routes import attorney_workspace
from app.routes.attorney_workspace import MarkPaid


def test_mark_paid_uses_verified_actor_and_requires_mfa(monkeypatch):
    actor = {
        "uid": "staff-1",
        "email": "aam@example.com",
        "role": "staff",
        "staff_role": "attorney_account_manager",
    }
    calls = []
    monkeypatch.setattr(attorney_workspace, "require_staff", lambda _header: actor)
    monkeypatch.setattr(
        attorney_workspace,
        "require_staff_claim",
        lambda claims, roles: calls.append(("roles", claims, roles)) or claims,
    )
    monkeypatch.setattr(
        attorney_workspace,
        "require_recent_auth",
        lambda claims, require_mfa=False: calls.append(("recent", claims, require_mfa)) or claims,
    )
    monkeypatch.setattr(attorney_workspace, "get_db", lambda: object())
    monkeypatch.setattr(
        attorney_workspace.cl,
        "mark_payout_paid",
        lambda _db, payout_id, method, staff_id: {
            "payout_id": payout_id,
            "method": method,
            "staff_id": staff_id,
        },
    )

    result = attorney_workspace.admin_mark_paid(
        "payout-1",
        MarkPaid(payout_method="Choice Digital"),
        "Bearer token",
    )

    assert result["staff_id"] == "aam@example.com"
    assert ("roles", actor, ["admin", "attorney_account_manager"]) in calls
    assert ("recent", actor, True) in calls


def test_mark_paid_denies_unauthorized_staff_role(monkeypatch):
    actor = {"uid": "reviewer-1", "role": "staff", "staff_role": "reviewer"}
    monkeypatch.setattr(attorney_workspace, "require_staff", lambda _header: actor)
    monkeypatch.setattr(
        attorney_workspace,
        "require_staff_claim",
        lambda _claims, _roles: (_ for _ in ()).throw(
            HTTPException(status_code=403, detail="Required staff role missing."),
        ),
    )

    with pytest.raises(HTTPException) as error:
        attorney_workspace.admin_mark_paid(
            "payout-1",
            MarkPaid(payout_method="Choice Digital"),
            "Bearer token",
        )

    assert error.value.status_code == 403
