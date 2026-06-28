"""
AI Ticket Engine — LangGraph Orchestration

Pipeline:
  Case Intake (validate input)
    → (fail) escalate_red immediately
    → (ok) Lone Ranger (pass 1, temp=1.0)
         → Referee (initial scoring)
             GREEN  → Document Completeness → Book Worm → PII Match → MVR Request
                    → PSP Request → Research Ron → Team Quest → Urgency Router
                    → Statement of Record → assemble_green
             YELLOW → Lone Ranger 2 (pass 2, temp=0.4)
                    → Consensus (merge, flag conflicts)
                    → Referee 2 (re-score merged extraction)
                    → Document Completeness → Book Worm → PII Match → MVR Request
                    → PSP Request → Research Ron → Team Quest → Urgency Router
                    → Statement of Record → assemble_yellow
             RED    → Lone Ranger 2 → Consensus → Referee 2 → escalate_red

Document Completeness: audits extraction field-by-field, produces completeness_score
PII Match:             verifies driver CDL against Firestore profile
MVR Request:           queues Motor Vehicle Record pull (pending, async in production)
PSP Request:           queues FMCSA PSP report pull (pending, async in production)
Research Ron:          jurisdiction enrichment — court system context, CDL rules
Team Quest:            attorney matching — top 3 CDL attorneys by state/county
Urgency Router:        calculates CRITICAL/HIGH/STANDARD/LOW from court date
Statement of Record:   officer vs. driver dual-account, conflict map, evidence index
"""
import logging

from langgraph.graph import END, START, StateGraph

from agents.book_worm import book_worm
from agents.case_intake import case_intake
from agents.consensus import consensus
from agents.document_completeness import document_completeness
from agents.document_gate import document_gate
from agents.lone_ranger import lone_ranger, lone_ranger_2
from agents.mvr_request import mvr_request
from agents.photo_analyst import photo_analyst_node
from agents.pii_match import pii_match
from agents.psp_request import psp_request
from agents.referee import referee
from agents.research_ron import research_ron
from agents.statement_of_record import statement_of_record as sor_agent
from agents.team_quest import team_quest
from agents.urgency_router import urgency_router
from app.services.bbox_matcher import attach_bboxes
from orchestrator.state import PassStatus, TicketState

logger = logging.getLogger(__name__)


def _build_final_result(state: TicketState) -> dict:
    extraction = state.get("extraction") or {}
    word_positions = state.get("word_positions") or []

    if word_positions:
        extraction = attach_bboxes(extraction, word_positions)

    return {
        "final_result": {
            **extraction,
            "pass_status": state.get("pass_status"),
            "low_confidence_fields": state.get("low_confidence_fields", []),
            "referee_notes": state.get("referee_notes"),
            "cdl_point_impact": state.get("cdl_point_impact"),
            "escalation_reason": state.get("escalation_reason"),
            "dual_conflicts": state.get("dual_conflicts", []),
            "completeness_score": state.get("completeness_score"),
            "missing_fields": state.get("missing_fields", []),
            "driver_profile": state.get("driver_profile"),
            "mvr_request": state.get("mvr_request"),
            "psp_request": state.get("psp_request"),
            "urgency_level": state.get("urgency_level"),
            "urgency_reason": state.get("urgency_reason"),
            "statement_of_record": state.get("statement_of_record"),
        }
    }


def assemble_photo(state: TicketState) -> dict:
    logger.warning("[graph] ROUTE → assemble_photo  file=%s  type=%s",
                   state.get("filename", "unknown"),
                   (state.get("extraction") or {}).get("photo_type", "unknown"))
    return _build_final_result(state)


def assemble_unknown(state: TicketState) -> dict:
    logger.warning("[graph] ROUTE → assemble_unknown  file=%s", state.get("filename", "unknown"))
    base = _build_final_result(state)
    base["final_result"]["escalation_reason"] = (
        "Unrecognized document type — not a legal document or photograph. Manual review required."
    )
    return base


def assemble_green(state: TicketState) -> dict:
    logger.warning("[graph] ROUTE → assemble_green  file=%s", state.get("filename", "unknown"))
    return _build_final_result(state)


def assemble_yellow(state: TicketState) -> dict:
    logger.warning("[graph] ROUTE → assemble_yellow  file=%s", state.get("filename", "unknown"))
    return _build_final_result(state)


def escalate_red(state: TicketState) -> dict:
    logger.warning("[graph] ROUTE → escalate_red  file=%s  reason=%s",
                   state.get("filename", "unknown"), state.get("referee_notes", ""))
    base = _build_final_result(state)
    base["final_result"]["escalation_reason"] = (
        state.get("escalation_reason")
        or state.get("referee_notes")
        or "Low confidence — human review required."
    )
    return base


def route_after_case_intake(state: TicketState) -> str:
    if state.get("intake_errors"):
        logger.warning("[graph] case_intake FAIL → escalate_red  errors=%s", state["intake_errors"])
        return "fail"
    return "ok"


def route_after_document_gate(state: TicketState) -> str:
    doc_type = state.get("doc_type", "document")
    logger.warning("[graph] document_gate=%r  file=%s", doc_type, state.get("filename", "unknown"))
    if doc_type == "photo":
        return "photo"
    if doc_type == "unknown":
        return "unknown"
    return "document"


def route_after_first_referee(state: TicketState) -> str:
    status = state.get("pass_status", PassStatus.RED)
    if status == PassStatus.GREEN:
        logger.warning("[graph] FAST PATH file=%s — GREEN on first pass, skipping dual extraction",
                       state.get("filename", "unknown"))
        return "fast_green"
    logger.warning("[graph] DUAL EXTRACTION file=%s — %s on first pass, running pass 2",
                   state.get("filename", "unknown"), status)
    return "needs_second_pass"


def route_after_sor_agent(state: TicketState) -> str:
    status = state.get("pass_status", PassStatus.RED)
    route = "green" if status == PassStatus.GREEN else "yellow" if status == PassStatus.YELLOW else "red"
    logger.warning("[graph] final routing  file=%s  pass_status=%s  → %s",
                   state.get("filename", "unknown"), status, route)
    return route


def build_graph() -> StateGraph:
    graph = StateGraph(TicketState)

    # ── Nodes ────────────────────────────────────────────────────────────────
    graph.add_node("case_intake", case_intake)
    graph.add_node("document_gate", document_gate)
    graph.add_node("photo_analyst", photo_analyst_node)
    graph.add_node("assemble_photo", assemble_photo)
    graph.add_node("assemble_unknown", assemble_unknown)
    graph.add_node("lone_ranger", lone_ranger)
    graph.add_node("referee", referee)
    graph.add_node("lone_ranger_2", lone_ranger_2)
    graph.add_node("consensus", consensus)
    graph.add_node("referee_2", referee)
    graph.add_node("document_completeness", document_completeness)
    graph.add_node("book_worm", book_worm)
    graph.add_node("pii_match", pii_match)
    graph.add_node("mvr_agent", mvr_request)
    graph.add_node("psp_agent", psp_request)
    graph.add_node("research_ron", research_ron)
    graph.add_node("team_quest", team_quest)
    graph.add_node("urgency_router", urgency_router)
    graph.add_node("sor_agent", sor_agent)
    graph.add_node("assemble_green", assemble_green)
    graph.add_node("assemble_yellow", assemble_yellow)
    graph.add_node("escalate_red", escalate_red)

    # ── Edges ────────────────────────────────────────────────────────────────

    # Case Intake gate — fail fast before touching Claude
    graph.add_edge(START, "case_intake")
    graph.add_conditional_edges(
        "case_intake",
        route_after_case_intake,
        {
            "ok": "document_gate",
            "fail": "escalate_red",
        },
    )

    # Document Gate — route photos/unknowns before running the full pipeline
    graph.add_conditional_edges(
        "document_gate",
        route_after_document_gate,
        {
            "photo":    "photo_analyst",
            "unknown":  "assemble_unknown",
            "document": "lone_ranger",
        },
    )
    graph.add_edge("photo_analyst", "assemble_photo")
    graph.add_edge("assemble_photo", END)
    graph.add_edge("assemble_unknown", END)

    # Pass 1
    graph.add_edge("lone_ranger", "referee")

    # Branch: fast path for green, second pass for yellow/red
    graph.add_conditional_edges(
        "referee",
        route_after_first_referee,
        {
            "fast_green": "document_completeness",
            "needs_second_pass": "lone_ranger_2",
        },
    )

    # Second-pass chain
    graph.add_edge("lone_ranger_2", "consensus")
    graph.add_edge("consensus", "referee_2")

    # After re-scoring — GREEN/YELLOW into enrichment chain, RED to escalate
    graph.add_conditional_edges(
        "referee_2",
        lambda s: "enrich" if s.get("pass_status") in (PassStatus.GREEN, PassStatus.YELLOW) else "escalate_red",
        {
            "enrich": "document_completeness",
            "escalate_red": "escalate_red",
        },
    )

    # Enrichment chain (shared by fast-green and yellow paths)
    graph.add_edge("document_completeness", "book_worm")
    graph.add_edge("book_worm", "pii_match")
    graph.add_edge("pii_match", "mvr_agent")
    graph.add_edge("mvr_agent", "psp_agent")
    graph.add_edge("psp_agent", "research_ron")
    graph.add_edge("research_ron", "team_quest")
    graph.add_edge("team_quest", "urgency_router")
    graph.add_edge("urgency_router", "sor_agent")

    # Final routing
    graph.add_conditional_edges(
        "sor_agent",
        route_after_sor_agent,
        {
            "green": "assemble_green",
            "yellow": "assemble_yellow",
            "red": "escalate_red",
        },
    )

    graph.add_edge("assemble_green", END)
    graph.add_edge("assemble_yellow", END)
    graph.add_edge("escalate_red", END)

    return graph.compile()


ticket_graph = build_graph()
