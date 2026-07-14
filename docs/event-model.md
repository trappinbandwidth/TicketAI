# Event Model

Events are the bridge from procedural workflows to transportation intelligence.
Every meaningful platform action should eventually become an event.

## Flow

```text
Entity Action -> Event -> Intelligence Service -> Recommendation -> Action -> Outcome -> Learning
```

## Storage

Phase 1 stores events in Firestore:

```text
events/{event_id}
```

Longer term this may fan out to Pub/Sub, BigQuery, or a warehouse.

## Schema

```json
{
  "id": "evt_...",
  "event_type": "ticket.uploaded",
  "version": "1.0",
  "actor_type": "driver|carrier|attorney|staff|system|integration",
  "actor_id": "driver_123",
  "entity_type": "ticket",
  "entity_id": "ticket_123",
  "related_entities": [
    {"type": "driver", "id": "driver_123"},
    {"type": "carrier", "id": "carrier_456"}
  ],
  "source": "driver_app|admin_dashboard|attorney_portal|carrier_portal|api|system",
  "payload": {},
  "metadata": {
    "request_id": "...",
    "ip_hash": "...",
    "user_agent": "..."
  },
  "created_at": "server_timestamp"
}
```

## Naming

Use lowercase dot notation:

```text
noun.verb_past_tense
```

Examples:

- `ticket.uploaded`
- `document.classified`
- `ticket.processed`
- `recommendation.created`
- `ticket.approved`
- `ticket.rejected`
- `attorney.matched`
- `case.created`
- `case.assigned`
- `outcome.recorded`
- `payment.session_created`
- `payment.captured`
- `payout.requested`
- `payout.approved`
- `ledger.entry_created`

## Current Implementation

The AI engine has `app/services/event_service.py`.

Current event writes include:

- Ticket processing: `ticket.uploaded`, `document.classified`, `ticket.processed`
- Admin review: `ticket.approved`, `ticket.rejected`
- Recommendation service: `recommendation.created`
- Financial service stubs: `payment.session_created`, `payout.requested`, `payout.approved`, `payout.submitted`, `ledger.entry_created`

Event writes are non-blocking in Phase 1. Failures log and continue unless the
event is later promoted into a security/audit requirement.
