from fastapi import HTTPException
import pytest

from app.routes import admin_agent_config
from app.routes.admin_agent_config import AgentConfigUpdate
from tests.test_platform_identity import FakeDb


@pytest.fixture
def configured_route(monkeypatch):
    db = FakeDb()
    actor = {
        "uid": "staff-1",
        "email": "operator@example.com",
        "role": "admin",
        "auth_time": 1,
    }
    audits = []
    monkeypatch.setattr(admin_agent_config, "get_db", lambda: db)
    monkeypatch.setattr(admin_agent_config, "require_staff", lambda _header: actor)
    monkeypatch.setattr(admin_agent_config, "require_staff_claim", lambda claims, _roles: claims)
    monkeypatch.setattr(admin_agent_config, "require_recent_auth", lambda claims: claims)
    monkeypatch.setattr(
        admin_agent_config,
        "write_staff_audit",
        lambda *_args, **kwargs: audits.append(kwargs) is None,
    )
    return db, audits


def test_agent_config_lists_complete_roster_with_safe_defaults(configured_route):
    db, _ = configured_route

    result = admin_agent_config.list_agent_config("Bearer token")

    assert len(result["structural"]) == 9
    assert len(result["toggleable"]) == 6
    assert all(row["enabled"] is True and row["version"] == 0 for row in result["toggleable"])
    assert db.collection("agent_config").rows == {}


def test_agent_config_change_is_versioned_reasoned_and_audited(configured_route):
    db, audits = configured_route

    result = admin_agent_config.update_agent_config(
        "tubman",
        AgentConfigUpdate(
            enabled=False,
            expected_version=0,
            reason="Investigate elevated urgency errors",
        ),
        "Bearer token",
    )

    assert result == {
        "ok": True,
        "changed": True,
        "agent": "tubman",
        "enabled": False,
        "version": 1,
    }
    assert db.collection("agent_config").rows["tubman"]["enabled"] is False
    assert audits[0]["reason"] == "Investigate elevated urgency errors"
    assert audits[0]["before"] == {"enabled": True, "version": 0}
    assert audits[0]["after"]["version"] == 1


def test_agent_config_replay_is_noop_and_stale_version_is_rejected(configured_route):
    db, audits = configured_route
    db.collection("agent_config").document("tubman").set({"enabled": False, "version": 1})

    replay = admin_agent_config.update_agent_config(
        "tubman",
        AgentConfigUpdate(enabled=False, expected_version=1, reason="Retry prior disable request"),
        "Bearer token",
    )
    assert replay["changed"] is False
    assert audits == []

    with pytest.raises(HTTPException) as error:
        admin_agent_config.update_agent_config(
            "tubman",
            AgentConfigUpdate(enabled=True, expected_version=0, reason="Restore after investigation"),
            "Bearer token",
        )
    assert error.value.status_code == 409


def test_structural_and_unknown_agents_cannot_be_changed(configured_route):
    for agent, status in (("carver", 400), ("not-real", 404)):
        with pytest.raises(HTTPException) as error:
            admin_agent_config.update_agent_config(
                agent,
                AgentConfigUpdate(enabled=False, expected_version=0, reason="Test invalid control path"),
                "Bearer token",
            )
        assert error.value.status_code == status


def test_agent_change_is_restricted_to_control_plane_roles(configured_route, monkeypatch):
    monkeypatch.setattr(
        admin_agent_config,
        "require_staff_claim",
        lambda _claims, _roles: (_ for _ in ()).throw(
            HTTPException(status_code=403, detail="Required staff role missing."),
        ),
    )

    with pytest.raises(HTTPException) as error:
        admin_agent_config.update_agent_config(
            "tubman",
            AgentConfigUpdate(
                enabled=False,
                expected_version=0,
                reason="Reviewer cannot change pipeline controls",
            ),
            "Bearer token",
        )

    assert error.value.status_code == 403


def test_audit_failure_rolls_back_agent_change(configured_route, monkeypatch):
    db, _ = configured_route
    monkeypatch.setattr(admin_agent_config, "write_staff_audit", lambda *_args, **_kwargs: False)

    with pytest.raises(HTTPException) as error:
        admin_agent_config.update_agent_config(
            "tubman",
            AgentConfigUpdate(enabled=False, expected_version=0, reason="Investigate elevated urgency errors"),
            "Bearer token",
        )

    assert error.value.status_code == 503
    assert db.collection("agent_config").rows["tubman"] == {"enabled": True, "version": 0}
