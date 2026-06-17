"""
AI Ticket Engine — LangGraph Orchestration

Pipeline:
  Lone Ranger (pass 1, temp=1.0)
    → Referee (initial scoring)
      GREEN  → Book Worm → Research Ron → Team Quest → assemble_green   [fast path]
      YELLOW → Lone Ranger 2 (pass 2, temp=0.4)
             → Consensus (merge, flag conflicts)
             → Referee 2 (re-score merged extraction)
             → Book Worm → Research Ron → Team Quest → assemble_yellow
      RED    → Lone Ranger 2 → Consensus → Referee 2
             → Book Worm → Research Ron → Team Quest → escalate_red

Research Ron: jurisdiction enrichment — court system context, CDL disqualification rules,
              appearance requirements, attorney timeline. (Phase 2 will add S3 corpus lookup.)
Team Quest:   attorney matching — finds top 3 CDL attorneys by state/county from local DB.
"""
import logging

from langgraph.graph import END, START, StateGraph

from agents.book_worm import book_worm
from agents.consensus import consensus
from agents.lone_ranger import lone_ranger, lone_ranger_2
from agents.referee import referee
from agents.research_ron import research_ron
from agents.team_quest import team_quest
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
        }
    }


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
    base["final_result"]["escalation_reason"] = state.get("referee_notes", "Low confidence — human review required.")
    return base


def route_after_team_quest(state: TicketState) -> str:
    status = state.get("pass_status", PassStatus.RED)
    route = "green" if status == PassStatus.GREEN else "yellow" if status == PassStatus.YELLOW else "red"
    logger.warning("[graph] final routing  file=%s  pass_status=%s  → %s",
                   state.get("filename", "unknown"), status, route)
    return route


def route_after_first_referee(state: TicketState) -> str:
    status = state.get("pass_status", PassStatus.RED)
    if status == PassStatus.GREEN:
        logger.warning("[graph] FAST PATH file=%s — GREEN on first pass, skipping dual extraction",
                       state.get("filename", "unknown"))
        return "fast_green"
    logger.warning("[graph] DUAL EXTRACTION file=%s — %s on first pass, running pass 2",
                   state.get("filename", "unknown"), status)
    return "needs_second_pass"


def build_graph() -> StateGraph:
    graph = StateGraph(TicketState)

    # Nodes
    graph.add_node("lone_ranger", lone_ranger)
    graph.add_node("referee", referee)
    graph.add_node("lone_ranger_2", lone_ranger_2)
    graph.add_node("consensus", consensus)
    graph.add_node("referee_2", referee)
    graph.add_node("book_worm", book_worm)
    graph.add_node("research_ron", research_ron)
    graph.add_node("team_quest", team_quest)
    graph.add_node("assemble_green", assemble_green)
    graph.add_node("assemble_yellow", assemble_yellow)
    graph.add_node("escalate_red", escalate_red)

    # Pass 1
    graph.add_edge(START, "lone_ranger")
    graph.add_edge("lone_ranger", "referee")

    # Branch: fast path for green, second pass for yellow/red
    graph.add_conditional_edges(
        "referee",
        route_after_first_referee,
        {
            "fast_green": "book_worm",
            "needs_second_pass": "lone_ranger_2",
        },
    )

    # Second-pass chain
    graph.add_edge("lone_ranger_2", "consensus")
    graph.add_edge("consensus", "referee_2")

    # After re-scoring — all paths converge at book_worm
    graph.add_conditional_edges(
        "referee_2",
        lambda s: "book_worm" if s.get("pass_status") in (PassStatus.GREEN, PassStatus.YELLOW) else "escalate_red",
        {
            "book_worm": "book_worm",
            "escalate_red": "escalate_red",
        },
    )

    # Enrichment chain: book_worm → research_ron → team_quest → final routing
    graph.add_edge("book_worm", "research_ron")
    graph.add_edge("research_ron", "team_quest")

    graph.add_conditional_edges(
        "team_quest",
        route_after_team_quest,
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
