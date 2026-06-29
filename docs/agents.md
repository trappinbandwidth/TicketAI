# Rig Resolve — Agent Pipeline Documentation

## Overview

The AI Ticket Engine processes uploaded documents through a **LangGraph-orchestrated multi-agent pipeline**. Each agent has a single responsibility. The pipeline is deterministic: the same inputs always follow the same graph path.

**Framework:** LangGraph (StateGraph)  
**LLM:** Claude (Anthropic) via `app/services/claude_client.py`  
**Orchestration entry point:** `orchestrator/graph.py`  
**State type:** `TicketState` (TypedDict) in `orchestrator/state.py`

---

## Pipeline Architecture

### Full Pipeline (YELLOW/RED path)

```
              ┌─────────────┐
              │ Case Intake │  validates input; fail-fast before Claude
              └──────┬──────┘
                     │ ok
              ┌──────▼──────┐
              │ Lone Ranger │  pass 1 (temp=1.0) — creative extraction
              └──────┬──────┘
                     │
              ┌──────▼──────┐
              │   Referee   │  scores extraction → GREEN / YELLOW / RED
              └──────┬──────┘
          ┌──────────┼──────────┐
        GREEN      YELLOW      RED
          │          │          │
          │   ┌──────▼──────┐   │
          │   │ Lone Ranger │   │
          │   │    Pass 2   │   │
          │   │  (temp=0.4) │   │
          │   └──────┬──────┘   │
          │          │          │
          │   ┌──────▼──────┐   │
          │   │  Consensus  │   │
          │   │ (merge pass │   │
          │   │  1 + pass 2)│   │
          │   └──────┬──────┘   │
          │          │          │
          │   ┌──────▼──────┐   │
          │   │  Referee 2  │   │
          │   │ (re-score)  │   │
          │   └──────┬──────┘   │
          │     GREEN/YELLOW    RED
          │          │           └──────────────────────►  escalate_red
          └────►┌────▼──────────────────────────────┐
                │       Enrichment Chain             │
                │                                   │
                │  Document Completeness             │
                │    → Book Worm                    │
                │      → PII Match                  │
                │        → MVR Request               │
                │          → PSP Request             │
                │            → Research Ron          │
                │              → Team Quest          │
                │                → Urgency Router    │
                │                  → Statement of    │
                │                    Record          │
                └────────────────────┬──────────────┘
                                     │
                        ┌────────────┼────────────┐
                      GREEN        YELLOW         RED
                        │            │             │
                   assemble_   assemble_       escalate_
                   green       yellow          red
```

### Fast Path (GREEN on first pass)
If Referee scores GREEN after pass 1, Lone Ranger pass 2 and Consensus are skipped. The ticket goes directly from Referee → Document Completeness (enrichment chain). This is the happy path — clean, high-confidence tickets skip dual extraction entirely.

---

## Agents — Current Production

### 1. Case Intake
**File:** `agents/case_intake.py`  
**Position:** First in pipeline — runs before any Claude API call  
**Temperature:** N/A (no LLM)

Validates that the minimum required inputs are present. Fails fast on missing data to avoid wasting Claude API budget on invalid requests.

**Validates:**
- `images_b64` is not empty
- `driver_id` is present
- `ticket_id` is present

**On failure:**
- Sets `pass_status = RED`
- Sets `escalation_reason = "Case intake failed: no_images, no_driver_id..."`
- Route: `escalate_red` (skips all Claude calls)

**Output to state:**
```python
{
  "intake_errors": ["no_images", "no_driver_id"],  # or []
  "pass_status": PassStatus.RED,  # only if errors
  "escalation_reason": "...",     # only if errors
}
```

---

### 2. Lone Ranger (Pass 1)
**File:** `agents/lone_ranger.py`  
**Position:** Second in pipeline  
**Temperature:** `1.0` — intentionally creative to maximize extraction breadth

Primary extraction agent. Runs the master prompt against all ticket images + OCR text. Uses Claude's vision capabilities to read traffic citations in any format from any state.

**Input from state:** `images_b64`, `ocr_text`, `driver_name`, `prompt_version`

**Output to state:**
```python
{
  "extraction": {...},       # all extracted fields as ExtractedField objects
  "is_mock": False,
  "pass1_extraction": {...}  # snapshot of pass 1 for training data
}
```

Each extracted field is an `ExtractedField`:
```python
{
  "value": "03/15/2024",
  "confidence_score": 0.97,
  "ai_reason": "Date clearly printed at top of citation.",
  "bbox": {...}  # word bounding box, attached later by bbox_matcher
}
```

**Fields extracted:**
- Ticket fields: `Date_of_Ticket__c`, `Court_Date__c`, `Violation_Description__c`, `Violation_Category__c`, `Citation_Number__c`, `Ticket_State__c`, `Ticket_County__c`, `Ticket_City__c`, `Ticket_Court__c`, `Court_Phone_Number__c`, `Mandatory_Appearance__c`, `School_Zone__c`, `Construction_Zone__c`, `Accident__c`, `Drivers_License_Type__c`
- Driver fields: `Driver_Name__c`, `Driver_Address__c`, `Driver_DOB__c`, `CDL_License_Number__c`, `CDL_Class__c`, `CDL_Expiration__c`
- IR fields (inspection reports): `Inspection_Date__c`, `Inspection_Level__c`, `DOT_Number__c`, `VIN__c`, `Unit_Make__c`, `Driver_OOS__c`, `Vehicle_OOS__c`, `BASIC_Categories__c`
- Crash fields: `Crash_Report_Number__c`, `Crash_Date__c`, `Federal_Recordable__c`
- MVR fields: `MVR_License_Number__c`, `MVR_Total_Points__c`

---

### 3. Referee (Pass 1 and Pass 2)
**File:** `agents/referee.py`  
**Position:** After each Lone Ranger pass  
**Temperature:** N/A (no LLM — pure scoring logic)

Scores the extraction and assigns GREEN / YELLOW / RED. The same function runs twice — once after pass 1, once after Consensus.

**Thresholds:**
- `GREEN` — average score ≥ 0.85 AND no low-confidence fields
- `YELLOW` — average score ≥ 0.60 OR some fields low-confidence
- `RED` — average score < 0.60 OR any critical field below 0.70

**Critical fields** (empty = score 0.0; below 0.70 = RED):
```
Court_Date__c, Date_of_Ticket__c, Citation_Number__c,
Violation_Category__c, Drivers_License_Type__c
```

**State-specific exemptions:**
- 18 states don't print `Citation_Number__c` — exempt from critical set
- Colorado and Virginia don't print `Ticket_County__c` — not penalized

**Score capping rules** (prevents false greens):
- Date fields: if value doesn't match `MM/DD/YYYY` → cap to 0.50
- Phone fields: if value doesn't match `(NNN) NNN-NNNN` → cap to 0.50
- `Violation_Category__c`: if value not in picklist → cap to 0.40
- `Drivers_License_Type__c`: if value not in recognized CDL types → cap to 0.30
- Empty critical field → force to 0.0

**Cross-validation checks:**
- Speed category vs. description: if description says "72/60 mph" but category is "Speeding (1-14)" → flag
- Zone flags vs. category: school/construction zone on admin violation → flag
- Mandatory appearance with no court date and no date-calculation rule → force RED

**Court date exemption:** If only missing field is `Court_Date__c` but `Date_of_Ticket__c` is present, downgrade from RED to YELLOW (an artificial date +10 days will be generated).

**Output to state:**
```python
{
  "pass_status": "green" | "yellow" | "red",
  "low_confidence_fields": ["Court_Date__c", "Ticket_County__c"],
  "referee_notes": "All fields high confidence. Avg score: 0.91"
}
```

---

### 4. Lone Ranger (Pass 2)
**File:** `agents/lone_ranger.py` (`lone_ranger_2` function)  
**Position:** After Referee when YELLOW or RED  
**Temperature:** `0.4` — conservative, deterministic to converge on a stable answer

Second extraction pass with lower temperature. The intent: pass 1 explores broadly, pass 2 verifies. Conflicts between passes are surfaced to the reviewer.

**Output to state:** `extraction_2`, `pass2_extraction`

---

### 5. Consensus
**File:** `agents/consensus.py`  
**Position:** After Lone Ranger Pass 2  
**Temperature:** N/A (no LLM — merge logic)

Merges pass 1 and pass 2 extractions. For each field:
- If both passes agree → take the higher-confidence value
- If passes disagree → take the higher-confidence value, flag as `dual_conflict`

**`dual_conflicts`** is the list of field names where pass 1 and pass 2 gave different answers. Reviewers see this list as a signal that the AI was uncertain about those specific fields.

**Output to state:**
```python
{
  "extraction": {...},    # merged best extraction
  "dual_conflicts": ["Ticket_County__c"],
  "consensus_extraction": {...}  # snapshot for training data
}
```

---

### 6. Document Completeness
**File:** `agents/document_completeness.py`  
**Position:** First in enrichment chain  
**Temperature:** N/A (no LLM — field presence check)

Audits which critical fields the AI successfully extracted. Produces a completeness score for attorney awareness — attorneys use this to know what info they need to gather manually.

**Critical fields checked:**
```
Citation_Number__c, Date_of_Ticket__c, Court_Date__c,
Violation_Category__c, Violation_Description__c,
Ticket_State__c, Ticket_County__c, Driver_Name__c,
CDL_Number__c, Court_Location__c
```

**Output to state:**
```python
{
  "completeness_score": 0.9,        # 1.0 = all 10 fields present
  "missing_fields": ["Court_Location__c"]
}
```

---

### 7. Book Worm
**File:** `agents/book_worm.py`  
**Position:** After Document Completeness  
**Temperature:** N/A (no LLM — rule lookup)

Maps violation category to CDL-specific legal consequence data. Uses a hardcoded point map reflecting FMCSA/state CDL rules.

**CDL Point Map:**
| Category | Points | Severity | CSA Category |
|----------|--------|----------|-------------|
| Driver license violation | 6 | critical | Driver Fitness |
| Alcohol / Drug | 6 | critical | Controlled Substances |
| Reckless Driving | 5 | serious | Unsafe Driving |
| Speeding (15+) | 4 | serious | Unsafe Driving |
| Cell Phone | 4 | serious | Unsafe Driving |
| Failure to yield (emergency vehicle) | 4 | serious | Unsafe Driving |
| Following too close | 3 | serious | Unsafe Driving |
| ELD/Logs | 3 | standard | Hours of Service |
| Careless Driving | 3 | standard | Unsafe Driving |
| Lane Violation | 2 | standard | Unsafe Driving |
| Failure to Obey Traffic Device | 2 | standard | Unsafe Driving |
| Too Fast for Conditions | 2 | standard | Unsafe Driving |
| Speeding (1-14) | 2 | standard | Unsafe Driving |
| Equipment/Maintenance | 2 | standard | Vehicle Maintenance |
| Seatbelt | 1 | standard | Unsafe Driving |
| Registration Violations | 1 | minor | Vehicle Maintenance |
| Overweight/Overlength | 1 | minor | Vehicle Maintenance |
| Parking | 0 | minor | Unsafe Driving |

**Mandatory court appearance** required for: Driver license violation, Alcohol/Drug, Reckless Driving.  
**Attorney recommended** when: points ≥ 3 OR mandatory appearance required.

**Output to state:**
```python
{
  "cdl_point_impact": {
    "violation_category": "Speeding (15+)",
    "cdl_points": 4,
    "severity": "serious",
    "csa_category": "Unsafe Driving",
    "must_appear_in_court": False,
    "attorney_recommended": True
  }
}
```

---

### 8. PII Match
**File:** `agents/pii_match.py`  
**Position:** After Book Worm  
**Temperature:** N/A (no LLM — Firestore lookup)

Verifies the CDL number extracted from the ticket against the driver's Firestore profile. Flags mismatches for attorney review.

**Match outcomes:**
- `match` — CDL on ticket matches CDL in `drivers/{driver_id}.cdl_number`
- `mismatch` — CDLs differ (renewal, error, or fraud indicator)
- `unverified` — one or both CDLs are blank (can't compare)
- `not_found` — no Firestore profile exists for driver_id

Gracefully skips if `driver_id` is absent or Firestore is unavailable.

**Output to state:**
```python
{
  "driver_profile": {
    "driver_id": "...",
    "status": "found",
    "cdl_match": "match",
    "profile_cdl": "TX12345678",
    "ticket_cdl": "TX12345678",
    "driver_name_on_file": "James T. Booker"
  }
}
```

---

### 9. MVR Request
**File:** `agents/mvr_request.py`  
**Position:** After PII Match  
**Temperature:** N/A (no LLM — metadata assembly)

Queues a Motor Vehicle Record (MVR) pull request. Currently creates a metadata record only — the actual MVR pull (via state DMV API or third-party provider) is a Phase 2 feature.

Skips if no CDL number or ticket state was extracted.

**Output to state:**
```python
{
  "mvr_request": {
    "status": "pending",
    "driver_id": "...",
    "driver_name": "James T. Booker",
    "cdl_number": "TX12345678",
    "cdl_state": "Texas",
    "requested_at": "2024-03-15T10:23:44Z",
    "scan_id": "...",
    "note": "Queued for MVR pull — driver history needed for attorney assessment."
  }
}
```

---

### 10. PSP Request
**File:** `agents/psp_request.py`  
**Position:** After MVR Request  
**Temperature:** N/A (no LLM — metadata assembly)

Queues an FMCSA Pre-Employment Screening Program (PSP) report pull. Currently metadata only. PSP covers 5 years of crash history and 3 years of inspection violations (MCMIS dataset). Requires driver consent per 49 CFR 391.23.

**Output to state:**
```python
{
  "psp_request": {
    "status": "pending",
    "driver_name": "James T. Booker",
    "cdl_number": "TX12345678",
    "driver_dob": "01/15/1982",
    "requested_at": "...",
    "report_type": "PSP",
    "fmcsa_dataset": "MCMIS",
    "covers": {"crash_history_years": 5, "inspection_violation_years": 3},
    "consent_required": True
  }
}
```

---

### 11. Research Ron
**File:** `agents/research_ron.py`  
**Position:** After PSP Request  
**Temperature:** N/A (no LLM — data lookup and rule application)

Jurisdiction enrichment agent. Assembles court system context, CDL disqualification rules, zone modifiers, carrier validation, and FMCSA benchmarks into a structured `jurisdiction_context` map for attorneys.

**Data sources:**
- `court_rulebook.json` — court system per state (local file)
- County court data — address, phone, scheduling URL
- `motus_carriers.json` — carrier DOT validation (FMCSA data)
- `crash_by_dot.json` — carrier crash history by DOT number
- `inspection_national_stats.json` — FMCSA national violation/OOS rates
- `violation_corpus.json` — Phase 2: Kaggle CDL ticket dataset (not yet built)

**CDL disqualification rules (FMCSA 49 CFR 383.51):**
- **Serious violations** (Speeding 15+, Reckless, Following Too Close, Lane, Cell Phone, Failure to Yield):
  - 2 within 3 years → 60-day CDL disqualification
  - 3 within 3 years → 120-day disqualification
- **Major violations** (Alcohol/Drug, Driver License):
  - 1st offense → 1-year mandatory disqualification regardless of plea

**Output to state:** `jurisdiction_context` map (see schema doc for all fields)

---

### 12. Team Quest
**File:** `agents/team_quest.py`  
**Position:** After Research Ron  
**Temperature:** N/A (no LLM — SQLite attorney database query)

Attorney matching agent. Finds the top 3 available CDL attorneys for the ticket's state and county from the local attorney database.

**Match type hierarchy:**
1. `county` — attorney covers this specific county (best match)
2. `state` — attorney licensed in this state but not county-specific

**Query logic:**
- First tries county-level match
- Falls back to state-level if no county match found
- Filters: `status == "active"` AND `cases_active < max_active_cases`
- Sorts by win rate descending

**Output to state:**
```python
{
  "attorney_matches": [
    AttorneyMatch(
      attorney_id="atty-001",
      name="Marcus T. Williams",
      email="...",
      phone="...",
      win_rate=0.81,
      match_type="state"
    )
  ],
  "no_attorney_flag": False
}
```

---

### 13. Urgency Router
**File:** `agents/urgency_router.py`  
**Position:** After Team Quest  
**Temperature:** N/A (no LLM — date math)

Calculates urgency level from the court date and the current date.

**Urgency levels:**
- `CRITICAL` — court date is < 7 days away (or in the past)
- `HIGH` — 7–21 days
- `STANDARD` — 21–60 days
- `LOW` — > 60 days OR no court date

**Output to state:**
```python
{
  "urgency_level": "HIGH",
  "urgency_reason": "Court date in 14 days — attorney must be contacted within 24 hours."
}
```

---

### 14. Statement of Record
**File:** `agents/statement_of_record.py`  
**Position:** Last in enrichment chain, before final assembly  
**Temperature:** N/A (no LLM — structured assembly)

Builds a dual-account record of the incident by comparing what the ticket says (officer's account) against what the driver submitted via the intake form (driver's account). Produces a conflict map and evidence index for the attorney.

**Officer account:** extracted ticket fields (violation description, location, speed, etc.)

**Driver account (from intake form, if submitted):**
- Where they were when stopped
- What they were doing at the time
- Weather conditions
- Whether road signs were visible
- Their speed
- What the officer stated as the violation
- Whether they had a dashcam
- Whether there were other witnesses
- Their dispute of the ticket details

**Conflict map:** field-level comparison of where officer and driver accounts differ.  
**Evidence index:** links uploaded evidence files (dashcam footage, photos) to specific conflicts.

**Output to state:**
```python
{
  "statement_of_record": {
    "officer_account": {...},
    "driver_account": {...},
    "conflict_map": [
      {
        "field": "speed",
        "officer_stated": "72 MPH",
        "driver_stated": "65 MPH",
        "conflict_type": "value_mismatch"
      }
    ],
    "evidence_index": [...],
    "conflict_count": 1,
    "evidence_count": 0,
    "uncategorized_evidence": 0
  }
}
```

---

### 15. Final Assembly Nodes

**`assemble_green`** — packages GREEN state into `final_result`  
**`assemble_yellow`** — packages YELLOW state into `final_result`  
**`escalate_red`** — packages RED state into `final_result`, sets `escalation_reason`

All three nodes call `_build_final_result(state)` which:
1. Takes the merged extraction
2. Attaches word bounding boxes via `attach_bboxes()` (from Textract data)
3. Packages all agent outputs (urgency, completeness, PII, MVR/PSP, jurisdiction, SoR) into the final dict

---

## Agent Event Logging

Every agent logs structured events to the SQLite `agent_events` table via `log_agent_event()`:

```python
log_agent_event(
    scan_id="uuid",
    agent="lone_ranger",
    event="pass_1_complete",
    detail={
        "fields_filled": 14,
        "empty_fields": ["CDL_License_Number__c"],
        "low_confidence_fields": ["Court_Date__c"]
    }
)
```

These events power the **Agents tab** in the admin dashboard. Each agent's health score is `1 - (errors / total_events)`.

---

## State Schema (TicketState)

Key fields on `TicketState` (TypedDict):

```python
# Inputs
images_b64: list[str]           # base64-encoded image pages
ocr_text: str                   # OCR text from PDF
driver_name: str | None
driver_id: str | None
ticket_id: str | None
filename: str
prompt_version: str
scan_id: str
word_positions: list[dict]      # Textract bounding boxes

# Extraction
extraction: dict | None          # current best extraction
extraction_2: dict | None        # pass 2 raw extraction
pass1_extraction: dict | None    # snapshot for training
pass2_extraction: dict | None
consensus_extraction: dict | None
dual_conflicts: list[str]

# Scoring
pass_status: PassStatus | None   # green | yellow | red
low_confidence_fields: list[str]
referee_notes: str | None

# Agent outputs
completeness_score: float | None
missing_fields: list[str]
driver_profile: dict | None      # PII match result
mvr_request: dict | None
psp_request: dict | None
cdl_point_impact: dict | None
jurisdiction_context: dict | None
attorney_matches: list
no_attorney_flag: bool
urgency_level: str | None
urgency_reason: str | None
statement_of_record: dict | None

# Intake
intake_errors: list[str]
driver_statement: dict | None    # from driver upload form
evidence_files: list[dict]

# Terminal
final_result: dict | None
escalation_reason: str | None
is_mock: bool
```

---

## Operational Agents (Non-Pipeline)

These agents run as API endpoints called by the admin dashboard or Cloud Scheduler. They are not part of the per-scan pipeline but operate on Firestore data in bulk.

### Court Deadline Monitor
**Endpoint:** `POST /api/v1/operations/court-deadlines`  
**Cron target:** Daily 8am  

Scans all open tickets, classifies by urgency (CRITICAL/HIGH/STANDARD/LOW/NO_DATE), and sends court reminder push notifications to drivers via Driver Concierge.

### Outcome Recorder
**Endpoint:** `POST /api/v1/operations/record-outcome/{ticket_id}`  
**Trigger:** Admin action after attorney reports outcome

Writes outcome to both Firestore paths (`tickets/` and `drivers/.../tickets/`), triggers driver notification.

### Payment Alert
**Endpoint:** `GET /api/v1/operations/payment-alerts`  
**Cron target:** Daily  

Scans all driver profiles for lapsed or expiring subscriptions. Critical alert when a driver has an open case but a lapsed subscription.

### Case Status Tracker
**Endpoint:** `GET /api/v1/operations/case-status`  
**Trigger:** On demand  

Unified work queue across all active statuses. Supports filtering by state and urgency. Surfaces `needs_action` cases (CRITICAL urgency, CDL mismatch, low completeness).

### Driver Concierge
**File:** `app/services/driver_concierge.py`  
**Trigger:** Called by approve/reject endpoints and operational agents

Not an API endpoint — a service module that writes notification documents to `drivers/{driver_id}/notifications/`. Sends status update messages on every ticket lifecycle transition and court reminder messages at 14 days, 7 days, and daily when < 7 days.

---

## Future Agents (Planned)

### Phase 2: Research Ron Corpus Lookup
**ClickUp:** #86b9ryenz  
**Status:** Code wired but corpus not yet built

Research Ron has Phase 2 code that queries a local `violation_corpus.json` file built from a 30K-record Kaggle CDL ticket dataset. When the corpus is available, every scan will get:
- Citation rate for this state + violation category
- Top counties where this violation is most frequently cited (enforcement hotspot data)
- Defense note based on patterns (e.g., "85% of Harris County speeding tickets reduced when contested")
- High-risk flag when citation rate > 70%

### MVR Pull Integration
**Status:** Queued (metadata only today)

Wire the MVR Request agent to an actual DMV API or third-party service (e.g., SambaSafety, Verisk). On completion, write the MVR report back to the ticket and send a notification to the attorney. Will expose CDL point history, prior violations, license status.

### PSP Pull Integration
**Status:** Queued (metadata only today)

Wire the PSP Request agent to the FMCSA PSP API. Requires driver consent workflow. On completion, write crash history and inspection violation history to the ticket. Critical for attorney assessment of disqualification risk.

### Automated MVR/PSP at Onboarding
When a driver signs up and opts in to the safe driver discount, automatically trigger an MVR/PSP pull to verify eligibility. If clean record confirmed → `safe_driver_verified: true`, `safe_driver_rate_applied: true`.

### Stripe / Rainforest Payment Agent
**Status:** Not started

Automate subscription billing and attorney payouts. Today both are manual. Integration will update `subscriptions.stripe_subscription_id`, `attorney_payouts.stripe_transfer_id`, and handle webhooks for failed payments (→ trigger Payment Alert agent).

### Court Research Agent (Phase 3)
A future agent that, when no court info is found in the local rulebook, queries court websites or a court data API to populate the `courts/` collection. Would replace the "No court date — attorney should contact court immediately" fallback with actual scheduling links.

### Attorney Match Optimization Agent
Today attorney matching is rule-based (county → state fallback, sorted by win rate). A future agent would learn from case outcomes:
- Which attorneys win which violation categories
- Attorney response time patterns
- Geographic coverage gaps → auto-alert team when no attorney covers an incoming ticket's state

### Document Classification Pre-filter
Today all documents go through the same Lone Ranger prompt regardless of document type. A lightweight classification pass before Lone Ranger could route documents to type-specific prompts (ticket vs. inspection report vs. crash report vs. MVR), potentially improving accuracy and reducing token usage.

---

*Last updated: 2026-06-26*
