# Intelligence Services

The internal agent IDs remain stable implementation contracts. Staff-facing
agent names are centralized in `app/services/agent_identity.py` and documented in
`agent-identity-roster.md`. External product and architecture language should
describe services by the intelligence they provide.

## Service Taxonomy

| External service | Current agents / functions |
| --- | --- |
| Document Intelligence | Document Gate, Carver, Bolin, Bunche, Photo Analyst |
| Legal Intelligence | Banneker, Madam Walker, Douglass, court lookup |
| Compliance Intelligence | Charlotte Ray, Jollof, Stagecoach Mary, Bass Reeves, violation corpus |
| Operational Intelligence | Tubman, Review Queue, Anansi, notifications |
| Financial Intelligence | Pricing, payment options, payout queue, Financial Service |
| Predictive Intelligence | Future scoring, outcome learning, attorney performance learning |

## Agent Departments

The four current departments are runtime-owned by
`app/services/agent_identity.py`. Each agent belongs to exactly one department,
and `/api/v1/admin/stats/agents` returns reconciled department and agent
rollups for the same observation window.

| Department | Current agents | Boundary |
| --- | ---: | --- |
| Document Intelligence | 7 | Intake, document/photo routing, extraction, merge, and quality/completeness checks |
| Compliance Intelligence | 4 | CDL impact, profile match, and approved MVR/PSP request preparation |
| Legal Intelligence | 3 | Jurisdiction context, attorney matching, accounts, conflicts, and evidence index |
| Operational Intelligence | 1 | Court-date urgency and work prioritization |

Financial Intelligence and Predictive Intelligence are taxonomy placeholders,
not active agent departments. Copilot is also not an active department.

## Current Pipeline Mapping

```text
Document Intelligence
  -> Legal Intelligence
  -> Compliance Intelligence
  -> Operational Intelligence
  -> Recommendations
```

The pipeline should keep returning the existing response shape while also writing
platform primitives:

- `events/{event_id}`
- `recommendations/{recommendation_id}`
- future intelligence-service outputs

## Guidance

- Do not rename working agent IDs just to match the external taxonomy or display
  roster.
- New user-facing copy should use the service taxonomy.
- New AI outputs should consider whether they should emit an Event,
  Recommendation, or both.
- Human approval remains required for legal, financial, and account-impacting
  actions.
- New agents should follow `agent-extension-guide.md` so graph wiring, state,
  identity, admin visibility, tests, and docs stay aligned.
