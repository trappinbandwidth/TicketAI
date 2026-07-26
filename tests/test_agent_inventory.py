import ast
from pathlib import Path

from app.services.agent_identity import AGENT_IDENTITIES


ROOT = Path(__file__).resolve().parents[1]


def _agent_names_from_files() -> set[str]:
    names: set[str] = set()
    for path in (ROOT / "agents").glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if not any(isinstance(target, ast.Name) and target.id == "AGENT_NAME" for target in node.targets):
                continue
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                names.add(node.value.value)
    return names


def test_agent_stats_tracks_every_logged_agent():
    admin_route = (ROOT / "app" / "routes" / "admin.py").read_text()

    missing = sorted(
        agent_name for agent_name in _agent_names_from_files()
        if f'"{agent_name}"' not in admin_route
    )

    assert missing == []


def test_agent_config_knows_every_logged_agent():
    config_route = (ROOT / "app" / "routes" / "admin_agent_config.py").read_text()

    missing = sorted(
        agent_name for agent_name in _agent_names_from_files()
        if f'"{agent_name}"' not in config_route
    )

    assert missing == []


def test_every_logged_agent_has_identity_metadata():
    assert _agent_names_from_files() == set(AGENT_IDENTITIES)

    incomplete = sorted(
        identity.agent
        for identity in AGENT_IDENTITIES.values()
        if not identity.honor_name
        or not identity.legacy_name
        or not identity.role
        or not identity.category
        or not identity.namesake_note
    )

    assert incomplete == []


def test_documented_roster_uses_runtime_agent_ids_and_names():
    roster = (ROOT / "docs" / "agent-identity-roster.md").read_text()

    for identity in AGENT_IDENTITIES.values():
        assert f"`{identity.agent}`" in roster
        assert f"| {identity.honor_name} | {identity.legacy_name} |" in roster
