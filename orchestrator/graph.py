"""
AI Ticket Engine — LangGraph Orchestration

Pipeline:
  Roux (validate input)
    → (fail) griot_escalate_red immediately
    → (ok) Carver (pass 1, temp=1.0)
         → Bolin (initial scoring)
             GREEN  → Ida Wells → Charlotte Ray → Jollof → Stagecoach Mary
                    → Bass Reeves → Banneker → Madam Walker → Tubman
                    → Douglass → griot_assemble_green
             YELLOW → Carver 2 (pass 2, temp=0.4)
                    → Bunche (merge, flag conflicts)
                    → Bolin 2 (re-score merged extraction)
                    → Ida Wells → Charlotte Ray → Jollof → Stagecoach Mary
                    → Bass Reeves → Banneker → Madam Walker → Tubman
                    → Douglass → griot_assemble_yellow
             RED    → Carver 2 → Bunche → Bolin 2 → griot_escalate_red

Ida Wells: audits extraction field-by-field, produces completeness_score
Jollof:             verifies driver CDL against Firestore profile
Stagecoach Mary:           queues Motor Vehicle Record pull (pending, async in production)
Bass Reeves:           queues FMCSA PSP report pull (pending, async in production)
Banneker:          jurisdiction enrichment — court system context, CDL rules
Madam Walker:            attorney matching — top 3 CDL attorneys by state/county
Tubman:        calculates CRITICAL/HIGH/STANDARD/LOW from court date
Douglass:   officer vs. driver dual-account, conflict map, evidence index
"""
import logging

from langgraph.graph import END, START, StateGraph

from agents.charlotte_ray import charlotte_ray_lookup
from agents.roux import roux
from agents.bunche import bunche_merge
from agents.ida_wells import ida_wells_audit
from agents.document_gate import document_gate
from agents.carver import carver_pass1, carver_pass2
from agents.stagecoach_mary import stagecoach_mary_queue
from agents.photo_analyst import photo_analyst_node
from agents.jollof import jollof_match
from agents.bass_reeves import bass_reeves_queue
from agents.bolin import bolin_score
from agents.banneker import banneker_lookup
from agents.douglass import douglass_compare
from agents.madam_walker import madam_walker_match
from agents.tubman import tubman_route
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
            "token_usage": state.get("token_usage", []),
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


def griot_assemble_green(state: TicketState) -> dict:
    logger.warning("[graph] ROUTE → griot_assemble_green  file=%s", state.get("filename", "unknown"))
    return _build_final_result(state)


def griot_assemble_yellow(state: TicketState) -> dict:
    logger.warning("[graph] ROUTE → griot_assemble_yellow  file=%s", state.get("filename", "unknown"))
    return _build_final_result(state)


def griot_escalate_red(state: TicketState) -> dict:
    logger.warning("[graph] ROUTE → griot_escalate_red  file=%s  reason=%s",
                   state.get("filename", "unknown"), state.get("referee_notes", ""))
    base = _build_final_result(state)
    base["final_result"]["escalation_reason"] = (
        state.get("escalation_reason")
        or state.get("referee_notes")
        or "Low confidence — human review required."
    )
    return base


def route_after_roux(state: TicketState) -> str:
    if state.get("intake_errors"):
        logger.warning("[graph] roux FAIL → griot_escalate_red  errors=%s", state["intake_errors"])
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


def route_after_first_bolin(state: TicketState) -> str:
    status = state.get("pass_status", PassStatus.RED)
    if status == PassStatus.GREEN:
        logger.warning("[graph] FAST PATH file=%s — GREEN on first pass, skipping dual extraction",
                       state.get("filename", "unknown"))
        return "fast_green"
    logger.warning("[graph] DUAL EXTRACTION file=%s — %s on first pass, running pass 2",
                   state.get("filename", "unknown"), status)
    return "needs_second_pass"


def route_after_douglass(state: TicketState) -> str:
    status = state.get("pass_status", PassStatus.RED)
    route = "green" if status == PassStatus.GREEN else "yellow" if status == PassStatus.YELLOW else "red"
    logger.warning("[graph] final routing  file=%s  pass_status=%s  → %s",
                   state.get("filename", "unknown"), status, route)
    return route


def build_graph() -> StateGraph:
    graph = StateGraph(TicketState)

    # ── Nodes ────────────────────────────────────────────────────────────────
    # Future agents should be added with a stable AGENT_NAME, state field,
    # identity metadata, admin visibility, and tests. See
    # docs/agent-extension-guide.md before changing graph control flow.
    graph.add_node("roux", roux)
    graph.add_node("document_gate", document_gate)
    graph.add_node("photo_analyst", photo_analyst_node)
    graph.add_node("assemble_photo", assemble_photo)
    graph.add_node("assemble_unknown", assemble_unknown)
    graph.add_node("carver_pass1", carver_pass1)
    graph.add_node("bolin", bolin_score)
    graph.add_node("carver_pass2", carver_pass2)
    graph.add_node("bunche", bunche_merge)
    graph.add_node("bolin_2", bolin_score)
    graph.add_node("ida_wells", ida_wells_audit)
    graph.add_node("charlotte_ray", charlotte_ray_lookup)
    graph.add_node("jollof", jollof_match)
    graph.add_node("stagecoach_mary", stagecoach_mary_queue)
    graph.add_node("bass_reeves", bass_reeves_queue)
    graph.add_node("banneker", banneker_lookup)
    graph.add_node("madam_walker", madam_walker_match)
    graph.add_node("tubman", tubman_route)
    graph.add_node("douglass", douglass_compare)
    graph.add_node("griot_assemble_green", griot_assemble_green)
    graph.add_node("griot_assemble_yellow", griot_assemble_yellow)
    graph.add_node("griot_escalate_red", griot_escalate_red)

    # ── Edges ────────────────────────────────────────────────────────────────

    # Roux gate — fail fast before touching Claude
    graph.add_edge(START, "roux")
    graph.add_conditional_edges(
        "roux",
        route_after_roux,
        {
            "ok": "document_gate",
            "fail": "griot_escalate_red",
        },
    )

    # Document Gate — route photos/unknowns before running the full pipeline
    graph.add_conditional_edges(
        "document_gate",
        route_after_document_gate,
        {
            "photo":    "photo_analyst",
            "unknown":  "assemble_unknown",
            "document": "carver_pass1",
        },
    )
    graph.add_edge("photo_analyst", "assemble_photo")
    graph.add_edge("assemble_photo", END)
    graph.add_edge("assemble_unknown", END)

    # Pass 1
    graph.add_edge("carver_pass1", "bolin")

    # Branch: fast path for green, second pass for yellow/red
    graph.add_conditional_edges(
        "bolin",
        route_after_first_bolin,
        {
            "fast_green": "ida_wells",
            "needs_second_pass": "carver_pass2",
        },
    )

    # Second-pass chain
    graph.add_edge("carver_pass2", "bunche")
    graph.add_edge("bunche", "bolin_2")

    # After re-scoring — GREEN/YELLOW into enrichment chain, RED to escalate
    graph.add_conditional_edges(
        "bolin_2",
        lambda s: "enrich" if s.get("pass_status") in (PassStatus.GREEN, PassStatus.YELLOW) else "griot_escalate_red",
        {
            "enrich": "ida_wells",
            "griot_escalate_red": "griot_escalate_red",
        },
    )

    # Enrichment chain (shared by fast-green and yellow paths)
    graph.add_edge("ida_wells", "charlotte_ray")
    graph.add_edge("charlotte_ray", "jollof")
    graph.add_edge("jollof", "stagecoach_mary")
    graph.add_edge("stagecoach_mary", "bass_reeves")
    graph.add_edge("bass_reeves", "banneker")
    graph.add_edge("banneker", "madam_walker")
    graph.add_edge("madam_walker", "tubman")
    graph.add_edge("tubman", "douglass")

    # Final routing
    graph.add_conditional_edges(
        "douglass",
        route_after_douglass,
        {
            "green": "griot_assemble_green",
            "yellow": "griot_assemble_yellow",
            "red": "griot_escalate_red",
        },
    )

    graph.add_edge("griot_assemble_green", END)
    graph.add_edge("griot_assemble_yellow", END)
    graph.add_edge("griot_escalate_red", END)

    return graph.compile()


ticket_graph = build_graph()
