"""Central identity registry for AI Ticket Engine agents.

Internal agent IDs are stable implementation contracts used by graph nodes,
Firestore events, tests, and admin filters. Honor names are display metadata for
staff-facing surfaces and documentation.

When adding a future agent, update this registry as part of the same change that
adds AGENT_NAME, graph wiring, stats/config visibility, and tests. See
docs/agent-extension-guide.md for the full extension checklist.
"""
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


AGENT_IDENTITIES: dict[str, AgentIdentity] = {
    "case_intake": AgentIdentity(
        agent="case_intake",
        honor_name="Ida B. Wells",
        legacy_name="Case Intake",
        role="Validates submissions before AI spend.",
        category="Journalist, researcher, and civil rights organizer",
        namesake_note="Known for disciplined investigation and documenting truth under pressure.",
    ),
    "document_gate": AgentIdentity(
        agent="document_gate",
        honor_name="Granville T. Woods",
        legacy_name="Document Gate",
        role="Routes submissions as photos, documents, or unknown files.",
        category="Engineer and inventor",
        namesake_note="A transportation technology innovator whose work improved railroad communications and routing.",
    ),
    "photo_analyst": AgentIdentity(
        agent="photo_analyst",
        honor_name="Gordon Parks",
        legacy_name="Photo Analyst",
        role="Analyzes photo evidence outside the ticket-extraction path.",
        category="Photographer, filmmaker, and writer",
        namesake_note="Used photography to reveal context, evidence, and human truth.",
    ),
    "lone_ranger": AgentIdentity(
        agent="lone_ranger",
        honor_name="Harriet Tubman",
        legacy_name="Lone Ranger",
        role="Primary document extraction pass.",
        category="Abolitionist and freedom strategist",
        namesake_note="A precise navigator and rescuer whose work required courage, memory, and careful reading of risk.",
    ),
    "referee": AgentIdentity(
        agent="referee",
        honor_name="Thurgood Marshall",
        legacy_name="Referee",
        role="Scores extraction quality and routes GREEN, YELLOW, or RED.",
        category="Civil rights attorney and Supreme Court Justice",
        namesake_note="Represents legal judgment, standards, and careful review.",
    ),
    "consensus": AgentIdentity(
        agent="consensus",
        honor_name="Septima Poinsette Clark",
        legacy_name="Consensus",
        role="Merges two extraction passes and flags conflicts.",
        category="Educator and civil rights organizer",
        namesake_note="Built civic education networks that turned many voices into coordinated action.",
    ),
    "document_completeness": AgentIdentity(
        agent="document_completeness",
        honor_name="Mary McLeod Bethune",
        legacy_name="Document Completeness",
        role="Audits missing fields for attorney preparation.",
        category="Educator, institution builder, and advisor",
        namesake_note="Known for building durable institutions with careful attention to readiness and records.",
    ),
    "book_worm": AgentIdentity(
        agent="book_worm",
        honor_name="Carter G. Woodson",
        legacy_name="Book Worm",
        role="Adds CDL point, severity, and disqualification context.",
        category="Historian, author, and researcher",
        namesake_note="Represents research discipline, context, and preserving knowledge.",
    ),
    "pii_match": AgentIdentity(
        agent="pii_match",
        honor_name="Rebecca Lee Crumpler",
        legacy_name="PII Match",
        role="Verifies CDL identity against the driver's profile.",
        category="Physician and author",
        namesake_note="Known for careful professional assessment and service in communities with high need.",
    ),
    "mvr_request": AgentIdentity(
        agent="mvr_request",
        honor_name="Frederick McKinley Jones",
        legacy_name="MVR Request",
        role="Queues Motor Vehicle Record pulls.",
        category="Engineer and inventor",
        namesake_note="A transportation refrigeration pioneer whose work changed freight movement.",
    ),
    "psp_request": AgentIdentity(
        agent="psp_request",
        honor_name="Bessie Coleman",
        legacy_name="PSP Request",
        role="Queues FMCSA PSP safety-record pulls.",
        category="Aviator",
        namesake_note="A trailblazing pilot whose name fits safety, certification, and transportation records.",
    ),
    "research_ron": AgentIdentity(
        agent="research_ron",
        honor_name="Benjamin Banneker",
        legacy_name="Research Ron",
        role="Builds jurisdiction, court, carrier, and violation context.",
        category="Mathematician, almanac author, and surveyor",
        namesake_note="Known for measurement, research, astronomy, and practical civic knowledge.",
    ),
    "team_quest": AgentIdentity(
        agent="team_quest",
        honor_name="Maggie Lena Walker",
        legacy_name="Team Quest",
        role="Matches cases to available CDL attorneys.",
        category="Business leader and community builder",
        namesake_note="Built networks, institutions, and access to practical support.",
    ),
    "urgency_router": AgentIdentity(
        agent="urgency_router",
        honor_name="Sojourner Truth",
        legacy_name="Urgency Router",
        role="Calculates court-date urgency and priority.",
        category="Abolitionist and women's rights advocate",
        namesake_note="Represents direct advocacy, urgency, and moral clarity.",
    ),
    "statement_of_record": AgentIdentity(
        agent="statement_of_record",
        honor_name="Frederick Douglass",
        legacy_name="Statement of Record",
        role="Builds driver/officer accounts, conflict map, and evidence index.",
        category="Abolitionist, writer, editor, and statesman",
        namesake_note="His written record and testimony shaped public truth and legal memory.",
    ),
}


def agent_identity(agent: str) -> AgentIdentity:
    return AGENT_IDENTITIES[agent]


def agent_display_name(agent: str) -> str:
    return AGENT_IDENTITIES[agent].honor_name


def agent_identity_payload(agent: str) -> dict:
    return asdict(agent_identity(agent))
