# Rig Resolve Agent System

**Last verified:** 2026-07-26
**Runtime source of truth:** `app/services/agent_identity.py`
**Pipeline:** FastAPI + LangGraph in `orchestrator/graph.py`

## Current Count

Rig Resolve has **15 active pipeline agents in 4 departments**.

| Department | Agents | Responsibility |
| --- | ---: | --- |
| Document Intelligence | 7 | Intake, routing, extraction, reconciliation, and quality/completeness |
| Compliance Intelligence | 4 | CDL impact, identity matching, and approved record-request preparation |
| Legal Intelligence | 3 | Jurisdiction, attorney matching, accounts, conflicts, and evidence |
| Operational Intelligence | 1 | Court-date urgency and work prioritization |

Financial Intelligence, Predictive Intelligence, and Copilot are not active
agent departments. The proposed Paralegal system is not part of this count.

The approved end-to-end roadmap proposes **9 additional agents in 4 new
departments**, for a future total of **24 agents across 8 departments**. Planned
agents are not represented as live, toggleable, or purchasable capabilities.

## How the Departments Interact

```text
Submission
  |
  v
Document Intelligence
  Roux -> Document Gate
    | photo               | unknown             | document
    v                     v                     v
  Photo Analyst -> end  Manual review          Carver pass 1 -> Bolin
                                                  | GREEN
                                                  v
                                                Ida Wells
                                                  |
                                YELLOW/RED         |
                           Carver pass 2 -> Bunche -> Bolin 2
                                                  |
                                            GREEN/YELLOW
                                                  v
Compliance Intelligence
  Charlotte Ray -> Jollof -> Stagecoach Mary -> Bass Reeves
                                                  |
                                                  v
Legal Intelligence
  Banneker -> Madam Walker
                  |
                  v
Operational Intelligence
  Tubman
    |
    v
Legal Intelligence
  Douglass
    |
    v
Assemble final artifact -> human review or authorized downstream workflow
```

The graph is sequential where one artifact depends on another:

- Document agents create a normalized extraction and decide whether it is safe
  to continue.
- Compliance agents add deterministic CDL context, compare identity, and
  prepare—not retrieve—MVR/PSP requests.
- Legal agents use the extraction and compliance context to add jurisdiction,
  attorney coverage, accounts, conflicts, and evidence.
- Operational Intelligence prioritizes the case by deadline.
- Douglass runs after urgency because its final case brief is the last reusable
  enrichment before assembly.

No agent may independently approve a case, publish a TIP Score, make a legal
decision, move money, or take another consequential action.

## Branching and Failure Behavior

| Decision | Result |
| --- | --- |
| Roux rejects malformed input | Stop before provider spend; route to human review |
| Document Gate returns `photo` | Run Photo Analyst and assemble a photo artifact |
| Document Gate returns `unknown` | Stop and require manual classification |
| Bolin returns GREEN after pass 1 | Skip the second extraction and continue |
| Bolin returns YELLOW or RED after pass 1 | Run Carver pass 2, Bunche, then Bolin again |
| Bolin returns RED after pass 2 | Stop enrichment and require human review |
| Bolin returns GREEN/YELLOW after pass 2 | Continue through all enrichment departments |
| Optional enrichment is disabled | Log `disabled`, return sparse state, and preserve downstream execution |

Every node is tested for reachability from start and ability to reach a terminal
state. Structural routing/extraction/assembly agents cannot be disabled.

## Complete Agent Roster

### Document Intelligence — 7 agents

#### 1. Roux (`roux`)

- **File:** `agents/roux.py`
- **Type:** structural, deterministic
- **Runs:** first, on every submission
- **Reads:** submitted image payload and required intake metadata
- **Writes:** `intake_errors`
- **Hands off to:** Document Gate when valid; human-review escalation when invalid
- **Purpose:** rejects missing or malformed input before provider cost is incurred.

#### 2. Granville T. Woods / Document Gate (`document_gate`)

- **File:** `agents/document_gate.py`
- **Type:** structural routing agent
- **Runs:** after Roux
- **Reads:** submitted image
- **Writes:** `doc_type`, accumulated provider usage
- **Hands off to:** Photo Analyst, Carver, or manual classification
- **Purpose:** distinguishes photographs, supported documents, and unknown input.
- **Failure behavior:** defaults safely to the document path rather than dropping a submission.

#### 3. Gordon Parks / Photo Analyst (`photo_analyst`)

- **File:** `agents/photo_analyst.py`
- **Type:** structural for the photo branch
- **Runs:** only when Document Gate returns `photo`
- **Reads:** photograph
- **Writes:** normalized photo type, summary, damage assessment, and attorney observations
- **Hands off to:** photo assembly and terminal
- **Purpose:** creates an evidence-oriented photo artifact without running ticket extraction.

#### 4. Carver (`carver`)

- **File:** `agents/carver.py`
- **Type:** structural provider-backed extraction
- **Runs:** pass 1 on documents; pass 2 only after an uncertain first score
- **Reads:** document image, OCR text, versioned extraction prompt
- **Writes:** pass extraction fields and normalized provider usage
- **Hands off to:** Bolin after each pass
- **Purpose:** extracts ticket/document fields with value, confidence, and reason.
- **Provider boundary:** document extraction routes through the configured
  Anthropic/OpenAI provider policy where supported; offline tests use mocks.

#### 5. Bolin (`bolin`)

- **File:** `agents/bolin.py`
- **Type:** structural, deterministic quality gate
- **Runs:** after every Carver pass
- **Reads:** extracted fields, confidence, state-aware field expectations
- **Writes:** `pass_status`, low-confidence fields, review notes
- **Hands off to:** enrichment, second pass, or human-review escalation
- **Purpose:** routes GREEN/YELLOW/RED without using an LLM.

#### 6. Bunche (`bunche`)

- **File:** `agents/bunche.py`
- **Type:** structural, deterministic merge
- **Runs:** only on the second-pass branch
- **Reads:** Carver pass 1 and pass 2
- **Writes:** consensus extraction and dual conflicts
- **Hands off to:** Bolin for final quality scoring
- **Purpose:** selects the stronger field result deterministically and preserves disagreements.

#### 7. Ida Wells (`ida_wells`)

- **File:** `agents/ida_wells.py`
- **Type:** structural completeness audit
- **Runs:** after a GREEN/YELLOW quality decision
- **Reads:** accepted extraction
- **Writes:** `completeness_score`, `missing_fields`
- **Hands off to:** Charlotte Ray
- **Purpose:** separates document completeness from extraction confidence.

### Compliance Intelligence — 4 agents

#### 8. Charlotte Ray (`charlotte_ray`)

- **File:** `agents/charlotte_ray.py`
- **Type:** toggleable deterministic enrichment
- **Runs:** after Ida Wells
- **Reads:** normalized violation category
- **Writes:** `cdl_point_impact` with severity and compliance category context
- **Hands off to:** Jollof
- **Purpose:** applies the approved local CDL mapping. It does not replace an official record or legal opinion.

#### 9. Jollof (`jollof`)

- **File:** `agents/jollof.py`
- **Type:** toggleable identity enrichment
- **Runs:** after Charlotte Ray
- **Reads:** extracted CDL number and the authenticated Driver profile
- **Writes:** Driver-profile match, mismatch, unavailable, or skipped state
- **Hands off to:** Stagecoach Mary
- **Purpose:** flags profile/extraction inconsistencies for review without resolving identity autonomously.

#### 10. Stagecoach Mary (`stagecoach_mary`)

- **File:** `agents/stagecoach_mary.py`
- **Type:** toggleable external-request preparation
- **Runs:** after Jollof
- **Reads:** Driver/CDL/state context
- **Writes:** `mvr_request` metadata with pending/skipped state
- **Hands off to:** Bass Reeves
- **Purpose:** prepares an MVR request artifact.
- **Current limitation:** no approved live DMV vendor connector is active; pending metadata is not an official MVR.

#### 11. Bass Reeves (`bass_reeves`)

- **File:** `agents/bass_reeves.py`
- **Type:** toggleable external-request preparation
- **Runs:** after Stagecoach Mary
- **Reads:** Driver, CDL, consent, and scan context
- **Writes:** `psp_request` metadata with pending/skipped state
- **Hands off to:** Banneker
- **Purpose:** prepares an FMCSA PSP request artifact.
- **Current limitation:** no approved live PSP retrieval is active; consent and provider policy remain mandatory.

### Legal Intelligence — 3 agents

#### 12. Banneker (`banneker`)

- **File:** `agents/banneker.py`
- **Type:** structural local-data enrichment
- **Runs:** after Compliance Intelligence
- **Reads:** state, county, violation, and available Carrier context
- **Writes:** `jurisdiction_context`
- **Hands off to:** Madam Walker
- **Purpose:** adds court-rule, jurisdiction, violation-corpus, and available Carrier context from local approved data.
- **Boundary:** informational context only; it does not provide legal advice or guarantee an outcome.

#### 13. Madam Walker (`madam_walker`)

- **File:** `agents/madam_walker.py`
- **Type:** structural matching
- **Runs:** after Banneker
- **Reads:** jurisdiction and available attorney coverage records
- **Writes:** ranked `attorney_matches`, `no_attorney_flag`
- **Hands off to:** Tubman
- **Purpose:** prepares candidate coverage matches. Human and governed workflow rules control assignment.

#### 14. Douglass (`douglass`)

- **File:** `agents/douglass.py`
- **Type:** structural case-artifact assembly
- **Runs:** after Tubman
- **Reads:** ticket facts, Driver statement, evidence, jurisdiction, matches, and urgency
- **Writes:** `statement_of_record` with officer/Driver accounts, conflicts, and evidence index
- **Hands off to:** final GREEN/YELLOW assembly or RED escalation
- **Purpose:** builds a reusable pre-review case brief while preserving conflicting accounts.

### Operational Intelligence — 1 agent

#### 15. Tubman (`tubman`)

- **File:** `agents/tubman.py`
- **Type:** toggleable deterministic prioritization
- **Runs:** after Madam Walker
- **Reads:** normalized court/response date
- **Writes:** urgency level, reason, and days-until-court context
- **Hands off to:** Douglass
- **Purpose:** prioritizes time-sensitive work. It does not file, contact a court, or take legal action.

## Shared State and Final Artifact

The agents communicate through typed `TicketState` fields in
`orchestrator/state.py`. Final assembly preserves:

- extraction, confidence, missing fields, and dual conflicts;
- CDL impact and Driver-profile match;
- pending MVR/PSP request artifacts;
- jurisdiction context and attorney matches;
- no-attorney state;
- urgency and statement of record;
- normalized provider usage;
- escalation reason when human review is required.

This artifact is consumed by the process route and authorized downstream
workflows. Portal code must not reproduce agent logic.

## Observability and Controls

Every agent logs structured operational events under:

```text
scan_queue/{scan_id}/agent_events/{event_id}
```

Captain Agent Health aggregates the same event data over bounded 7/30/90-day
windows and displays:

- department and agent identity;
- observations and errors;
- observed health (unknown when there are no events);
- recorded provider cost;
- agent-specific diagnostics;
- enabled/disabled state where applicable.

Only optional enrichment agents are toggleable. Changes require staff
authorization, recent authentication, confirmation, a reason, optimistic
version matching, audit evidence, and rollback if the audit cannot be written.

## Adjacent Operational Services — Not Pipeline Agents

These named services participate after or around the pipeline but are not
LangGraph agents and are not included in the count of 15:

| Service | Responsibility |
| --- | --- |
| Anansi | Writes Driver lifecycle and court/document-request notifications |
| Bessie Coleman | Builds the authorized court-deadline work queue and reminders |
| William Still | Records a governed case outcome and related projections |
| Maggie Walker | Reports subscription/payment alerts for staff review |
| Bayard Rustin | Returns operational case-status summaries |
| Review Queue | Human correction, approval, rejection, and release |

They must use their own authorization, idempotency, audit, and recovery
contracts. Being named does not grant autonomous action authority.

## Current Data Boundaries

The active agents can function locally with emulator data, uploaded evidence,
mock provider output, court rules, violation mappings/corpus, inspection
baselines, and seeded attorney coverage.

The following are not live capabilities unless separately approved and
connected: official MVR, PSP, Clearinghouse, CDLIS, medical registry, DataQs,
court docket/filing, live FMCSA refresh, email/SMS delivery, marketplace,
payment, or external monitoring. Pending or unavailable states must never be
presented as verified results.

## Future Agents — Not Active

The approved roadmap proposes these agents. They are not included in the active
count:

| Planned department | Agent | Responsibility |
| --- | --- | --- |
| Restoration Intelligence | Government Record Translator | Explain normalized government facts with citations |
| Restoration Intelligence | Restoration Analyst | Identify evidence, deadlines, limitations, and potential correction paths |
| Restoration Intelligence | Challenge Draft Agent | Draft DataQs, MVR, PSP, then court correction packets for professional review |
| Advisory Intelligence | Attorney Case Brief Agent | Produce an access-scoped case, evidence, and deadline brief |
| Advisory Intelligence | Career Action Planner | Produce prioritized, measurable, non-guaranteed Driver actions |
| Network Intelligence | Court Research Agent | Research official/approved court facts with snapshots for verification |
| Network Intelligence | Outreach Draft Agent | Draft human-approved outreach for verified attorney coverage gaps |
| Operational Intelligence | Captain Copilot | Answer cited, read-only operational questions under RBAC |
| Records Administration | File Naming Agent | Assign governed display filenames from authorized metadata while preserving original names and opaque storage keys |

Document upload classification remains in Document Intelligence. SambaSafety
MVR acquisition, DataQs/PSP/court integrations, monitoring, learned attorney
ranking, payments, payouts, and notifications are connectors or deterministic
services—not agents. Driver Career Coach is a later interface over Career Action
Planner rather than a separate source of facts.

The File Naming Agent uses the deterministic convention
`LastName-FirstName_Department_CaseID_YYYY-MM-DD.ext`. Uploads without a case
use `GENERAL-{short-id}`, and collisions append `_v02`, `_v03`, and so on. It
does not use an LLM to construct names or infer a person or case from content.

They require separate approved tasks, source/retention/consent contracts,
provider-neutral telemetry, human-review policy, and role/data-access testing.
Every restoration or legal draft requires professional approval before
submission. The full service map and delivery order are recorded in
`_coordination/AGENT_SYSTEM_ROADMAP.md`.

## Adding Another Agent

Follow `docs/agent-extension-guide.md`. A new agent must include:

1. stable `AGENT_NAME` and typed state output;
2. graph node and tested routing;
3. identity and exactly one approved department;
4. Agent Health and configuration visibility;
5. success, disabled/skip, error, and terminal-path tests;
6. data provenance and authorization boundaries;
7. documentation updates;
8. human approval for legal, financial, account-impacting, or public actions.
