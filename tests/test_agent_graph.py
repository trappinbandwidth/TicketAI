from collections import defaultdict, deque

from app.services.agent_identity import AGENT_IDENTITIES
from app.services.anansi import _render_message
from orchestrator.graph import (
    _build_final_result,
    route_after_document_gate,
    route_after_douglass,
    route_after_first_bolin,
    route_after_roux,
    ticket_graph,
)
from orchestrator.state import PassStatus


def test_final_result_preserves_every_reusable_enrichment_artifact():
    state = {
        "extraction": {"Citation_Number__c": {"value": "A-1"}},
        "jurisdiction_context": {"court": "County Court"},
        "attorney_matches": [{"attorney_id": "attorney-1"}],
        "no_attorney_flag": False,
        "mvr_request": {"status": "pending"},
        "psp_request": {"status": "pending"},
        "statement_of_record": {"conflicts": []},
    }

    result = _build_final_result(state)["final_result"]

    assert result["jurisdiction_context"] == {"court": "County Court"}
    assert result["attorney_matches"] == [{"attorney_id": "attorney-1"}]
    assert result["no_attorney_flag"] is False
    assert result["mvr_request"]["status"] == "pending"
    assert result["psp_request"]["status"] == "pending"
    assert result["statement_of_record"] == {"conflicts": []}


def test_every_graph_node_is_reachable_and_can_reach_a_terminal():
    graph = ticket_graph.get_graph()
    forward = defaultdict(set)
    reverse = defaultdict(set)
    for edge in graph.edges:
        forward[edge.source].add(edge.target)
        reverse[edge.target].add(edge.source)

    def reachable(start, adjacency):
        seen = {start}
        queue = deque([start])
        while queue:
            for target in adjacency[queue.popleft()]:
                if target not in seen:
                    seen.add(target)
                    queue.append(target)
        return seen

    from_start = reachable("__start__", forward)
    to_end = reachable("__end__", reverse)
    assert set(graph.nodes) == from_start
    assert set(graph.nodes) == to_end


def test_all_agent_identities_have_a_pipeline_node():
    graph_nodes = set(ticket_graph.get_graph().nodes)
    node_for_agent = {
        "carver": "carver_pass1",
        "bolin": "bolin",
        **{agent: agent for agent in AGENT_IDENTITIES if agent not in {"carver", "bolin"}},
    }
    assert set(node_for_agent) == set(AGENT_IDENTITIES)
    assert set(node_for_agent.values()) <= graph_nodes


def test_all_pipeline_branch_decisions_are_characterized():
    assert route_after_roux({"intake_errors": ["missing image"]}) == "fail"
    assert route_after_roux({"intake_errors": []}) == "ok"
    assert route_after_document_gate({"doc_type": "photo"}) == "photo"
    assert route_after_document_gate({"doc_type": "unknown"}) == "unknown"
    assert route_after_document_gate({"doc_type": "document"}) == "document"
    assert route_after_first_bolin({"pass_status": PassStatus.GREEN}) == "fast_green"
    assert route_after_first_bolin({"pass_status": PassStatus.YELLOW}) == "needs_second_pass"
    assert route_after_first_bolin({"pass_status": PassStatus.RED}) == "needs_second_pass"
    assert route_after_douglass({"pass_status": PassStatus.GREEN}) == "green"
    assert route_after_douglass({"pass_status": PassStatus.YELLOW}) == "yellow"
    assert route_after_douglass({"pass_status": PassStatus.RED}) == "red"


def test_document_request_notification_has_truthful_fallback_copy():
    specific = _render_message("Document Requested", {"description": "Current CDL copy"})
    fallback = _render_message("Document Requested")

    assert "Current CDL copy" in specific
    assert "Additional case document" in fallback
    assert _render_message("unsupported-state") is None
