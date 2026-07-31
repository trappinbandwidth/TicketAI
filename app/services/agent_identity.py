"""Canonical identities and historical aliases for AI Ticket Engine agents."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AgentIdentity:
    agent: str
    honor_name: str
    legacy_name: str
    role: str
    category: str
    namesake_note: str
    department: str


AGENT_DEPARTMENTS = {
    "document_intelligence": {
        "name": "Document Intelligence",
        "description": "Validates, routes, extracts, reconciles, and quality-checks submitted evidence.",
    },
    "compliance_intelligence": {
        "name": "Compliance Intelligence",
        "description": "Adds CDL impact, identity, and approved state/federal record-request context.",
    },
    "legal_intelligence": {
        "name": "Legal Intelligence",
        "description": "Builds jurisdiction, attorney-match, account, conflict, and evidence context.",
    },
    "operational_intelligence": {
        "name": "Operational Intelligence",
        "description": "Prioritizes time-sensitive work without taking consequential action.",
    },
}


def _identity(
    agent: str,
    name: str,
    legacy: str,
    role: str,
    department: str,
    category: str = "Rig Resolve agent",
) -> AgentIdentity:
    if department not in AGENT_DEPARTMENTS:
        raise ValueError(f"Unknown agent department: {department}")
    return AgentIdentity(
        agent,
        name,
        legacy,
        role,
        category,
        f"{name} is the canonical Rig Resolve identity for this role.",
        department,
    )


AGENT_IDENTITIES: dict[str, AgentIdentity] = {
    "roux": _identity("roux", "Roux", "Case Intake", "Validates submissions before AI spend.", "document_intelligence", "Culinary foundation"),
    "document_gate": _identity("document_gate", "Granville T. Woods", "Document Gate", "Routes submissions as photos, documents, or unknown files.", "document_intelligence", "Engineer and inventor"),
    "photo_analyst": _identity("photo_analyst", "Gordon Parks", "Photo Analyst", "Analyzes photo evidence outside the ticket-extraction path.", "document_intelligence", "Photographer, filmmaker, and writer"),
    "carver": _identity("carver", "Carver", "Lone Ranger", "Performs the primary and secondary document extraction passes.", "document_intelligence", "Scientist and inventor"),
    "bolin": _identity("bolin", "Bolin", "Referee", "Scores extraction quality and routes GREEN, YELLOW, or RED.", "document_intelligence", "Judge and legal pioneer"),
    "bunche": _identity("bunche", "Bunche", "Consensus", "Merges two extraction passes and flags conflicts.", "document_intelligence", "Diplomat and mediator"),
    "ida_wells": _identity("ida_wells", "Ida Wells", "Document Completeness", "Audits missing fields for attorney preparation.", "document_intelligence", "Journalist and investigator"),
    "charlotte_ray": _identity("charlotte_ray", "Charlotte Ray", "Book Worm", "Adds CDL point, severity, and disqualification context.", "compliance_intelligence", "Attorney and legal pioneer"),
    "jollof": _identity("jollof", "Jollof", "PII Match", "Verifies CDL identity against the driver's profile.", "compliance_intelligence", "West African culinary tradition"),
    "stagecoach_mary": _identity("stagecoach_mary", "Stagecoach Mary", "MVR Request", "Queues Motor Vehicle Record pulls.", "compliance_intelligence", "Transportation pioneer"),
    "bass_reeves": _identity("bass_reeves", "Bass Reeves", "PSP Request", "Queues FMCSA PSP safety-record pulls.", "compliance_intelligence", "Deputy U.S. Marshal"),
    "banneker": _identity("banneker", "Banneker", "Research Ron", "Builds jurisdiction, court, carrier, and violation context.", "legal_intelligence", "Mathematician, author, and surveyor"),
    "madam_walker": _identity("madam_walker", "Madam Walker", "Team Quest", "Matches cases to available CDL attorneys.", "legal_intelligence", "Entrepreneur and philanthropist"),
    "tubman": _identity("tubman", "Tubman", "Urgency Router", "Calculates court-date urgency and priority.", "operational_intelligence", "Abolitionist and strategist"),
    "douglass": _identity("douglass", "Douglass", "Statement of Record", "Builds driver/officer accounts, conflict map, and evidence index.", "legal_intelligence", "Writer, editor, and statesman"),
}

# Option A from the rename handoff: historical event rows are never rewritten.
# Reads canonicalize old IDs so historical and new events appear on one card.
LEGACY_AGENT_ALIASES: dict[str, str] = {
    "case_intake": "roux",
    "lone_ranger": "carver",
    "referee": "bolin",
    "consensus": "bunche",
    "document_completeness": "ida_wells",
    "book_worm": "charlotte_ray",
    "pii_match": "jollof",
    "mvr_request": "stagecoach_mary",
    "psp_request": "bass_reeves",
    "research_ron": "banneker",
    "team_quest": "madam_walker",
    "urgency_router": "tubman",
    "statement_of_record": "douglass",
}


def canonical_agent_name(agent: str) -> str:
    return LEGACY_AGENT_ALIASES.get(agent, agent)


def agent_identity(agent: str) -> AgentIdentity:
    return AGENT_IDENTITIES[canonical_agent_name(agent)]


def agent_display_name(agent: str) -> str:
    return agent_identity(agent).honor_name


def agent_identity_payload(agent: str) -> dict:
    return asdict(agent_identity(agent))


def agent_department_summaries(agent_results: list[dict]) -> list[dict]:
    summaries = []
    for department_id, definition in AGENT_DEPARTMENTS.items():
        members = [
            result for result in agent_results
            if result.get("identity", {}).get("department") == department_id
        ]
        total_events = sum(int(result.get("total_events", 0)) for result in members)
        errors = sum(int(result.get("errors", 0)) for result in members)
        summaries.append({
            "department": department_id,
            **definition,
            "agent_count": len(members),
            "total_events": total_events,
            "errors": errors,
            "health_score": round(1 - (errors / total_events), 3) if total_events else None,
            "cost_usd": round(sum(float(result.get("cost_usd", 0)) for result in members), 4),
        })
    return summaries
