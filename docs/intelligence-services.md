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
| Records Administration | Deterministic governed display naming, original-name provenance, and opaque storage identity |

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
not active agent departments. Records Administration has a partially integrated
deterministic naming service but is not an active LangGraph department. Copilot
is also not an active department.

## Governed File Naming

`app/services/file_naming.py` owns policy version `file-name-v1`:

```text
LastName-FirstName_Department_CaseID_YYYY-MM-DD.ext
```

Organization subjects preserve organization-name order. General documents use
`GENERAL-{short-id}`. Display names never determine object storage identity;
private storage keys use server-issued opaque document IDs. The validated media
type—not the client extension—selects `pdf`, `jpg`, or `png`.

Current integrations are the shared document API, Driver case documents,
Carrier documents, and Carrier authority evidence. Ticket-processing and
Attorney-delegated uploads remain gated on authoritative subject-name
resolution.

## Current Pipeline Mapping

```text
Document Intelligence
  -> Compliance Intelligence
  -> Legal Intelligence (jurisdiction and attorney match)
  -> Operational Intelligence (urgency)
  -> Legal Intelligence (final statement of record)
  -> Final artifact / human review
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
