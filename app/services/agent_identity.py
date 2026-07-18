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


def _identity(agent: str, name: str, legacy: str, role: str, category: str = "Rig Resolve agent") -> AgentIdentity:
    return AgentIdentity(agent, name, legacy, role, category, f"{name} is the canonical Rig Resolve identity for this role.")


AGENT_IDENTITIES: dict[str, AgentIdentity] = {
    "roux": _identity("roux", "Roux", "Case Intake", "Validates submissions before AI spend.", "Culinary foundation"),
    "document_gate": _identity("document_gate", "Granville T. Woods", "Document Gate", "Routes submissions as photos, documents, or unknown files.", "Engineer and inventor"),
    "photo_analyst": _identity("photo_analyst", "Gordon Parks", "Photo Analyst", "Analyzes photo evidence outside the ticket-extraction path.", "Photographer, filmmaker, and writer"),
    "carver": _identity("carver", "Carver", "Lone Ranger", "Performs the primary and secondary document extraction passes.", "Scientist and inventor"),
    "bolin": _identity("bolin", "Bolin", "Referee", "Scores extraction quality and routes GREEN, YELLOW, or RED.", "Judge and legal pioneer"),
    "bunche": _identity("bunche", "Bunche", "Consensus", "Merges two extraction passes and flags conflicts.", "Diplomat and mediator"),
    "ida_wells": _identity("ida_wells", "Ida Wells", "Document Completeness", "Audits missing fields for attorney preparation.", "Journalist and investigator"),
    "charlotte_ray": _identity("charlotte_ray", "Charlotte Ray", "Book Worm", "Adds CDL point, severity, and disqualification context.", "Attorney and legal pioneer"),
    "jollof": _identity("jollof", "Jollof", "PII Match", "Verifies CDL identity against the driver's profile.", "West African culinary tradition"),
    "stagecoach_mary": _identity("stagecoach_mary", "Stagecoach Mary", "MVR Request", "Queues Motor Vehicle Record pulls.", "Transportation pioneer"),
    "bass_reeves": _identity("bass_reeves", "Bass Reeves", "PSP Request", "Queues FMCSA PSP safety-record pulls.", "Deputy U.S. Marshal"),
    "banneker": _identity("banneker", "Banneker", "Research Ron", "Builds jurisdiction, court, carrier, and violation context.", "Mathematician, author, and surveyor"),
    "madam_walker": _identity("madam_walker", "Madam Walker", "Team Quest", "Matches cases to available CDL attorneys.", "Entrepreneur and philanthropist"),
    "tubman": _identity("tubman", "Tubman", "Urgency Router", "Calculates court-date urgency and priority.", "Abolitionist and strategist"),
    "douglass": _identity("douglass", "Douglass", "Statement of Record", "Builds driver/officer accounts, conflict map, and evidence index.", "Writer, editor, and statesman"),
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
