# Agent Extension Guide

This guide is the handoff path for adding future feature agents, intelligence
services, or human-developer contributions to the AI Ticket Engine.

The goal is simple: a new agent should be easy to add, easy to observe, easy to
disable when appropriate, and hard to hide from tests, docs, or the Admin
Dashboard.

## When To Add A New Agent

Add a new agent when the work has a clear responsibility and produces a reusable
case artifact. Good examples:

- A new compliance check with its own output
- A new legal research enrichment
- A new carrier or attorney matching signal
- A new document analysis path
- A new post-processing quality gate

Do not add a new agent for ordinary helper code, one-off formatting, or logic
that belongs inside an existing domain service.

## Stable Contracts

Every agent needs these stable contracts:

| Contract | Standard |
| --- | --- |
| Internal ID | Snake-case `AGENT_NAME`, for example `court_deadline_predictor` |
| File | `agents/{agent_name}.py` unless the implementation is intentionally split |
| Graph node | Stable LangGraph node name in `orchestrator/graph.py` |
| State fields | Added to `orchestrator/state.py` with a short comment |
| Event logging | Uses `log_agent_event(scan_id, AGENT_NAME, event, detail)` |
| Identity | Added to `app/services/agent_identity.py` |
| Admin visibility | Added to `/admin/stats/agents` aggregation in `app/routes/admin.py` |
| Config visibility | Added to `app/routes/admin_agent_config.py` as structural or toggleable |
| Tests | Covered by `tests/test_agent_inventory.py` and focused behavior tests |
| Docs | Listed in `docs/agents.md` and mapped in `docs/intelligence-services.md` |

Internal IDs should not be renamed casually. They are used by graph nodes, event
history, admin filters, tests, and analytics.

## Agent File Template

Use this shape for most new agents:

```python
from __future__ import annotations

import logging

from app.services.queue_store import is_agent_enabled, log_agent_event
from orchestrator.state import TicketState

logger = logging.getLogger(__name__)
AGENT_NAME = "new_agent_name"


def new_agent_name(state: TicketState) -> dict:
    scan_id = state.get("scan_id", "")

    if not is_agent_enabled(AGENT_NAME):
        log_agent_event(scan_id, AGENT_NAME, "disabled", {})
        return {}

    try:
        result = {}
        log_agent_event(scan_id, AGENT_NAME, "complete", result)
        return {"new_state_field": result}
    except Exception as exc:
        logger.exception("[%s] failed", AGENT_NAME)
        log_agent_event(scan_id, AGENT_NAME, "error", {"error": str(exc)})
        return {"new_state_field": None}
```

Use `is_agent_enabled()` only for enrichment agents that can safely skip work.
Routing, extraction, scoring, and assembly agents should usually be structural
and not toggleable.

## Graph Wiring

Update `orchestrator/graph.py` in three places:

1. Import the new agent.
2. Register the node with `graph.add_node(...)`.
3. Add edges or conditional edges.

Prefer adding new enrichment agents inside the shared enrichment chain after
quality scoring. Only change the document/photo routing branches when the agent
really needs to alter pipeline control flow.

## State Updates

Add any new output fields to `orchestrator/state.py`.

Keep fields small and typed. For example:

```python
new_signal: dict | None
```

Avoid storing raw provider responses unless they are explicitly needed for audit.
Store normalized, product-shaped data instead.

## Events And Recommendations

Agents should log operational events. If the output advises a human or affects a
case decision, also consider writing a recommendation.

Use:

- `log_agent_event(...)` for agent-level observability
- `write_event(...)` for platform-level audit/timeline events
- `write_recommendation(...)` for explainable human-facing recommendations

Human approval remains required for legal, financial, account-impacting, or
driver/carrier/attorney-facing actions.

## Admin Dashboard Requirements

Every logged agent must show up in staff visibility.

Update:

- `app/routes/admin.py` for stats aggregation
- `app/routes/admin_agent_config.py` for structural/toggleable config
- `app/services/agent_identity.py` for display identity
- Admin Dashboard `AgentsTab.tsx` only when the agent has metrics not covered by
  the generic health/event display

UI rule: do not change Rig Resolve brand styling for agent additions. Add the
needed information inside the existing dashboard design language.

## Toggleable Vs Structural

Use this decision rule:

| Agent type | Toggleable? | Why |
| --- | --- | --- |
| Intake, routing, extraction, scoring, assembly | No | Disabling breaks pipeline control flow |
| Optional enrichment | Usually yes | Can safely skip and continue |
| External provider request | Usually yes | Useful for cost/vendor outage control |
| Legal/financial action | No direct automation | Must require human approval |

## Test Checklist

Before merging a new agent:

- `AGENT_NAME` exists in the agent file
- `tests/test_agent_inventory.py` passes
- Focused behavior test covers the agent's success and skip/error path
- `make syntax` passes
- `make test` passes for the focused AI-engine suite
- `make secret-scan` passes

If a new provider or external API is introduced, tests must run offline with a
fake provider or mock response. Do not require real Anthropic, Firebase, Stripe,
Twilio, SendGrid, TenStreet, Workday, S3, or GCP calls for local tests.

## Documentation Checklist

When adding or changing an agent, update:

- `docs/agents.md`
- `docs/intelligence-services.md`
- `docs/agent-identity-roster.md`
- `docs/event-model.md` if a new platform event is emitted
- `docs/recommendation-contract.md` if a new recommendation type is emitted
- `docs/api.md` if API response shape changes
- `docs/uiux.md` if staff/driver/attorney/carrier UI changes

For Claude/onboarding files, patch existing sections in place. Do not replace
the files wholesale.

## Human Developer Handoff Standard

Each future developer-facing PR should include:

- What changed
- Why it exists
- What data it reads and writes
- Whether it can be disabled
- Which user or staff surface sees it
- Verification commands run
- Any migration, backfill, or deploy notes

Use `docs/SCOPED_PR_PLAN.md` when splitting multi-repo work.

