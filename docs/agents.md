# Rig Resolve — AI Agent Pipeline
## Team Education Reference

**Last updated:** 2026-07-04  
**Engine:** FastAPI + LangGraph · Model: Claude Sonnet 4.6 · Cloud Run: `ai-ticket-engine`

---

## What This System Does

When a driver or staff member uploads a traffic citation, the AI Ticket Engine runs it through a **sequential chain of specialized AI agents**. Each agent does one job. Together they turn a photo of a paper ticket into a fully structured case record — with attorney matched, court date flagged, CDL risk assessed, and driver's story documented — before any human touches it.

**Who benefits:**
| Person | What they get from the pipeline |
|--------|--------------------------------|
| **Attorney** | Walk into a case with extracted ticket fields, CDL risk score, urgency level, conflict map, evidence index, matched peers, and court system context — before the first call |
| **Driver** | Ticket uploaded → case assigned → status updates in real time. No phone tag, no paperwork |
| **Eniola / Staff** | See exactly which cases need human review, which states need attorney coverage, and full case audit trail |

---

## The Pipeline — End to End

```
SUBMISSION (image upload)
        │
        ▼
┌──────────────────┐
│   Roux    │  "Is this a valid submission?" — fail fast before spending $
└────────┬─────────┘
         │ ok
         ▼
┌──────────────────┐
│  Document Gate   │  "Is this a photo or a legal document?" — $0.00004 haiku call
└────────┬─────────┘
         │
    ┌────┴──────────────┐
  PHOTO              DOCUMENT            UNKNOWN
    │                    │                  │
    ▼                    ▼                  ▼
┌────────┐      ┌──────────────┐     ┌───────────────┐
│ Photo  │      │ Carver  │     │  Escalate Red │
│Analyst │      │   (Pass 1)   │     │  (no spend)   │
└────┬───┘      └──────┬───────┘     └───────────────┘
     │                 │
     ▼                 ▼
Assemble          ┌──────────┐
  Photo           │  Bolin │  GREEN / YELLOW / RED
  → END           └────┬─────┘
                       │
            ┌──────────┼──────────┐
          GREEN      YELLOW      RED
            │          │          │
            │   ┌──────▼───────┐  │
            │   │ Carver  │  │
            │   │   (Pass 2)   │  │
            │   └──────┬───────┘  │
            │          │          │
            │   ┌──────▼───────┐  │
            │   │  Bunche   │  │
            │   └──────┬───────┘  │
            │          │          │
            │   ┌──────▼───────┐  │
            │   │  Bolin 2   │  │
            │   └──────┬───────┘  │
            │     GREEN/YELLOW   RED → Escalate RED
            │          │
            └────┬─────┘
                 │  (shared enrichment chain)
                 ▼
   ┌─────────────────────────┐
   │  Ida Wells  │  "What fields are still missing?"
   └────────────┬────────────┘
                ▼
   ┌─────────────────────────┐
   │       Charlotte Ray         │  CDL point impact, disqualification risk
   └────────────┬────────────┘
                ▼
   ┌─────────────────────────┐
   │       Jollof         │  Verify CDL against driver Firestore profile
   └────────────┬────────────┘
                ▼
   ┌─────────────────────────┐
   │      Stagecoach Mary        │  Queue Motor Vehicle Record pull
   └────────────┬────────────┘
                ▼
   ┌─────────────────────────┐
   │      Bass Reeves        │  Queue FMCSA federal safety record pull
   └────────────┬────────────┘
                ▼
   ┌─────────────────────────┐
   │      Banneker       │  Court system, appearance rules, jurisdiction
   └────────────┬────────────┘
                ▼
   ┌─────────────────────────┐
   │      Madam Walker         │  Match top 3 CDL attorneys by state/county
   └────────────┬────────────┘
                ▼
   ┌─────────────────────────┐
   │     Tubman      │  CRITICAL / HIGH / STANDARD / LOW
   └────────────┬────────────┘
                ▼
   ┌─────────────────────────┐
   │  Douglass    │  Officer account vs. driver account, conflict map
   └────────────┬────────────┘
                ▼
   ┌─────────────────────────┐
   │       Assemble          │  Build final_result, write to Firestore
   └─────────────────────────┘
```

---

## Agent Reference — Current (15 Agents)

---

### 1. Roux
**File:** `agents/roux.py`  
**Cost:** $0 — no Claude call  
**Runs:** Always, first

Validates that the submission has actual image data before spending any API money. If a file was corrupted or the upload failed, it fails immediately with a clear error instead of burning credits and returning garbage output.

**Output:** `intake_errors` list. If non-empty, the entire pipeline is skipped and the case is escalated.

---

### 2. Document Gate
**File:** `agents/document_gate.py`  
**Model:** `claude-haiku-4-5` (cheapest, fastest)  
**Cost:** ~$0.00004 per call (~100 tokens)  
**Runs:** After Roux passes

Looks at the image and answers one question: **is this a photo or a legal document?** Routes the submission before any expensive processing begins.

Without this gate, a driver uploading an accident scene photo would burn $0.15–$0.22 running through ticket extraction and produce nothing useful. The gate catches it in 100 tokens.

**Routes to:**
- `photo` → Photo Analyst path (~$0.01 total)
- `document` → Carver path (~$0.07–$0.13 total)
- `unknown` → Escalate immediately ($0.00004 total — no more Claude calls)

**Failure behavior:** If the gate itself fails for any reason, it defaults to `"document"` and proceeds to Carver. No submission is ever silently dropped.

---

### 3. Carver (Pass 1 + Pass 2)
**File:** `agents/carver.py`  
**Model:** `claude-sonnet-4-6`  
**Cost:** ~$0.07 per pass (with prompt caching active)  
**Runs:** Every document submission; Pass 2 only when first pass is uncertain

The main extraction engine. Reads the ticket image and OCR text simultaneously using the master prompt (`prompts/v2.md`). Pulls every field on the ticket:

- Court date, date of ticket, citation number
- Violation description (verbatim) and violation category
- Court name, court phone, court city
- Driver name, CDL number, CDL class, DOB
- Fine amount, mandatory appearance, school/construction zone
- Officer name, officer badge, speed enforcement method
- Vehicle plate, vehicle state

**Pass 1** runs at temperature 1.0 — more creative, catches edge cases and unusual layouts.  
**Pass 2** runs at temperature 0.4 — more conservative and precise. Only runs when Pass 1 scored YELLOW or RED.

**Prompt caching:** The 18,107-token system prompt is cached on the Anthropic API. After the first call writes the cache, all subsequent calls pay ~75% less for the prompt portion.

**Output:** `extraction` dict — 60+ fields, each with `value`, `confidence_score`, and `ai_reason` explaining why that value was extracted.

---

### 4. Bolin
**File:** `agents/bolin.py`  
**Cost:** $0 — pure logic, no Claude call  
**Runs:** After every Carver pass

Scores the extraction and routes accordingly:

| Grade | Condition | Next Step |
|-------|-----------|-----------|
| **GREEN** | Average confidence ≥ 0.85 AND no critical field below 0.70 | Skip to enrichment (fast path) |
| **YELLOW** | Average confidence ≥ 0.60 | Run Pass 2, merge, re-score |
| **RED** | Average confidence < 0.60 OR any critical field below 0.70 | Escalate for human review |

**Critical fields** — any one of these below 0.70 forces RED:  
`Court_Date__c`, `Date_of_Ticket__c`, `Citation_Number__c`, `Violation_Category__c`, `Drivers_License_Type__c`

**State-aware scoring:** The Bolin knows that certain states do not print certain fields on their tickets. For example, California never prints citation numbers, and Colorado never prints county. A field that's correctly absent for a known state is scored 0.95 (high confidence the absence is intentional), not 0.0 (which would look like an extraction failure).

---

### 5. Bunche
**File:** `agents/bunche.py`  
**Cost:** $0 — pure logic  
**Runs:** Only when Pass 2 is needed (YELLOW or RED after Pass 1)

Merges the two Carver passes field by field using these rules:
1. Take the value with the higher confidence score
2. If both have equal confidence, keep Pass 1 (deterministic tiebreak)
3. If both passes extracted **different values** and both have confidence ≥ 0.70 → flag as `dual_conflict`

**Dual conflicts** are surfaced to attorneys in the portal. An attorney seeing a dual conflict on `Court_Date__c` knows to verify that date against the physical ticket before filing.

---

### 6. Ida Wells
**File:** `agents/ida_wells.py`  
**Cost:** $0 — pure logic  
**Runs:** After GREEN or YELLOW score, before enrichment

Audits 10 critical fields and produces a `completeness_score` from 0.0 to 1.0.

**Fields checked:** Citation Number · Date of Ticket · Court Date · Violation Category · Violation Description · Ticket State · Ticket County · Driver Name · CDL Number · Court Location

A score of 1.0 means all 10 were extracted. A score of 0.60 means 4 fields are still missing and the attorney will need to gather them manually. This is shown on the case card so attorneys know what they're walking into before accepting.

---

### 7. Charlotte Ray
**File:** `agents/charlotte_ray.py`  
**Cost:** $0 — lookup table  
**Runs:** After Ida Wells

CDL law expert. Maps the violation category to federal consequences:

| Violation Category | CDL Points | Severity | FMCSA BASIC |
|-------------------|-----------|----------|-------------|
| Alcohol / Drug | 6 | Critical | Controlled Substances |
| Driver License Violation | 6 | Critical | Driver Fitness |
| Reckless Driving | 5 | Serious | Unsafe Driving |
| Speeding 15+ over | 4 | Serious | Unsafe Driving |
| Cell Phone | 4 | Serious | Unsafe Driving |
| Failure to Yield to Emergency Vehicle | 4 | Serious | Unsafe Driving |
| Following Too Close | 3 | Serious | Unsafe Driving |
| Careless Driving | 3 | Standard | Unsafe Driving |
| ELD / Logs | 3 | Standard | Hours of Service |
| Lane Violation | 2 | Standard | Unsafe Driving |
| Failure to Obey Traffic Device | 2 | Standard | Unsafe Driving |
| Speeding 1–14 over | 2 | Standard | Unsafe Driving |
| Equipment / Maintenance | 2 | Standard | Vehicle Maintenance |
| Seatbelt | 1 | Standard | Unsafe Driving |
| Registration Violations | 1 | Minor | Vehicle Maintenance |
| Overweight / Overlength | 1 | Minor | Vehicle Maintenance |
| Parking | 0 | Minor | Unsafe Driving |

**FMCSA disqualification thresholds applied automatically:**
- 2 serious violations in 3 years = 60-day CDL disqualification
- 3 serious violations in 3 years = 120-day disqualification
- DUI / suspended license / major violation = 1-year mandatory disqualification (no plea bargain escapes it)

**Output:** `cdl_point_impact` — attorneys see this on the case card and immediately understand what's at stake for the driver's livelihood before deciding whether to accept.

---

### 8. Jollof
**File:** `agents/jollof.py`  
**Cost:** $0 — one Firestore read  
**Runs:** After Charlotte Ray

Pulls the driver's Firestore profile and compares the CDL number on the ticket against what's stored on file.

| Result | Meaning |
|--------|---------|
| `match` | CDL numbers agree — driver identity confirmed |
| `mismatch` | Flagged for attorney review. Common causes: officer transposition error, CDL renewal, rare fraudulent filing |
| `not_found` | No Firestore profile exists for this driver yet |
| Skipped | No `driver_id` in the scan (manual staff scan) |

---

### 9. Stagecoach Mary
**File:** `agents/stagecoach_mary.py`  
**Cost:** $0 now — queues async request  
**Runs:** After Jollof

Queues a **Motor Vehicle Record** pull from the driver's CDL state DMV.

The MVR shows the driver's complete state driving history: every prior violation, suspension, revocation, and current point total. Attorneys need this before accepting any CDL case — a clean-record driver gets a completely different defense strategy than one with 10 prior violations.

**Current state:** Prepares and logs the request metadata with `status: "pending"`. Result flows back to Firestore asynchronously when the DMV/vendor responds. Skips cleanly if no CDL number was extracted.

---

### 10. Bass Reeves
**File:** `agents/bass_reeves.py`  
**Cost:** $0 now — queues async request  
**Runs:** After Stagecoach Mary

Queues a **Pre-employment Screening Program (PSP)** report from FMCSA — the federal driving record.

PSP provides 5 years of crash history and 3 years of inspection/violation history from FMCSA's national database. This is the first thing CDL defense attorneys reach for when building a mitigation argument — it shows the driver's complete federal safety record, not just what the state DMV sees.

**Compliance:** Rig Resolve collects driver consent during enrollment (required by 49 CFR 391.23). The `scan_id` ties each request back to that consent record.

**Current state:** Queues the request. Full FMCSA PSP API integration is Phase 2.

---

### 11. Banneker
**File:** `agents/banneker.py`  
**Cost:** $0 — local data files  
**Runs:** After Bass Reeves

Jurisdiction enrichment. Reads the ticket's state, county, and violation and packages court system context:

- Which court handles this violation type in this county
- Whether a CDL holder must appear in person or can handle remotely
- CDL-specific disqualification risk for this violation
- School zone / construction zone penalty multipliers
- Carrier safety statistics (when a DOT number is present)

**Data sources:**
- `data/court_rulebook.json` — court rules per state
- `data/violation_corpus.json` — defense patterns
- `data/inspection_national_stats.json` — national inspection baselines

**Phase 2 (pending):** Cross-reference against S3 corpus of 30,000+ real CDL tickets for pattern-based defense context by state/county/violation combination (ClickUp #86b9ryenz).

---

### 12. Madam Walker
**File:** `agents/madam_walker.py`  
**Cost:** $0 — SQLite query  
**Runs:** After Banneker

Finds the top 3 CDL defense attorneys for the ticket's state and county, ranked by:
1. County-level match over state-level match
2. Win rate (descending)
3. Total CDL cases handled (descending)
4. Average rating (descending)

**Attorney database:** SQLite `data/queue.db` — 75 attorneys across 37 states, baked into the container at build time.

**`no_attorney_flag`:** When zero attorneys cover a state, this flag triggers an outreach alert in Eniola's dashboard and fires the attorney discovery Cloud Run job.

---

### 13. Tubman
**File:** `agents/tubman.py`  
**Cost:** $0 — date calculation  
**Runs:** After Madam Walker

Calculates case priority from the court date:

| Level | Window | What Happens |
|-------|--------|-------------|
| **CRITICAL** | Court < 7 days away (or already passed) | Alert to attorney + Eniola. Court is this week |
| **HIGH** | 7–21 days | Case surfaces at top of attorney's queue |
| **STANDARD** | 21–60 days | Normal queue position |
| **LOW** | > 60 days or no court date | Routine — monitor |

Attorneys see the urgency badge on every case card. CRITICAL means someone needs to act today.

---

### 14. Douglass
**File:** `agents/douglass.py`  
**Cost:** $0 — pure logic  
**Runs:** After Tubman

Builds the dual-account brief that replaces 20–30 minutes of attorney intake work.

**Officer's account** (from ticket fields):  
What violation the officer cited, where it occurred, zone type, date, citation number.

**Driver's account** (from the 9-field intake form the driver fills at upload):  
Where they were, what they were doing, weather conditions, road signs visible, their speed, whether they had a dashcam, witnesses present, whether they dispute the ticket.

**Conflict map:**  
Field-by-field comparison. Where do the accounts agree? Where do they diverge? (Example: Officer says "school zone." Driver says "no zone signs visible.")

**Evidence index:**  
Driver-submitted files tagged to disputes. Dashcam footage → attached to speed dispute. Photo of road → attached to zone sign dispute.

All of this is pre-built and written to Firestore before any attorney sees the case.

---

### 15. Photo Analyst
**File:** `agents/photo_analyst.py`  
**Model:** `claude-opus-4-5`  
**Prompt:** `prompts/photo_v1.md`  
**Cost:** ~$0.01 per photo  
**Runs:** When Document Gate classifies submission as "photo"

When a driver submits accident scene photos, vehicle damage shots, or road/environment images, produces an attorney-ready brief:

**Photo types recognized:**
Vehicle Damage · Accident Scene · Person/Injury · Equipment Damage · Road/Environment · Driver Documentation · Repair Documentation · Other

**Output fields:**
- `Photo_Summary__c` — 2–5 sentence visual description written for an attorney who cannot see the image
- `Damage_Assessment__c` — location on vehicle, severity (minor/moderate/severe/totaled), fresh vs. pre-existing
- `Attorney_Notes__c` — defense-relevant observations (tire condition → maintenance defense, skid marks → speed calculation, road hazards → comparative fault, other vehicle positions → comparative fault)

---

## Cost Reference

| Submission Type | Claude Calls | Cost (cached) | Cost (no cache) |
|----------------|-------------|--------------|-----------------|
| Photo | Haiku + Opus-4-5 | ~$0.01 | ~$0.02 |
| Document — GREEN (1 pass) | Haiku + Sonnet×1 | ~$0.07 | ~$0.22 |
| Document — YELLOW/RED (2 pass) | Haiku + Sonnet×2 | ~$0.13 | ~$0.40 |
| Unknown document | Haiku only | ~$0.00004 | ~$0.00004 |

Prompt caching activates after the first request of a session. The 18,107-token system prompt costs $3.00/M uncached → $0.30/M cached (~75% savings).

---

## Firestore Write Paths

Every successful document scan writes to **two Firestore paths:**

```
tickets/{ticket_id}                     ← Attorney portal queue
drivers/{driver_id}/tickets/{ticket_id} ← Driver app real-time feed
```

**`attorney_status` lifecycle:**

```
AI Review  →  (reviewer approves)  →  New  →  Accepted  →  Ticket Closed
           →  (reviewer rejects)   →  Rejected
```

| Status | Set By | Attorneys See It |
|--------|--------|-----------------|
| `AI Review` | Manual/staff scan | No — hidden until reviewer approves |
| `New` | Driver upload, or after staff approval | Yes — available to claim |
| `Accepted` | Attorney claims the case | Only the assigned attorney |
| `Ticket Closed` | Attorney marks resolved | Archived |
| `Rejected` | Reviewer rejects the scan | Archived |

---

## Agent Event Log

Every agent writes structured events to `agent_events` in SQLite (`data/queue.db`):

```
scan_id | agent_name | event_type | payload_json | created_at
```

This is the full audit trail for every pipeline decision. To debug a case, filter by `scan_id` to see exactly what each agent saw, scored, and decided.

---

## Coming — Paralegal Agent System

A separate `paralegal-engine` Cloud Run service, built after the attorney portal rebuild. Reads and writes Firestore using the same shared data layer.

| Agent | Trigger | Replaces |
|-------|---------|---------|
| **Case Brief** | Attorney opens a case | Paralegal manually building pre-call summary |
| **Draft Writer** | Attorney natural-language request | Paralegal drafting continuance/motion letters |
| **Note Router** | Attorney adds a case note | Account manager forwarding updates manually |
| **Deadline Monitor** | Daily cron 6 AM | Account manager tracking court dates |
| **Account Digest** | Weekly + on demand | Manual performance spreadsheets |
| **Outreach Drafter** | New ticket in uncovered state | Eniola writing cold attorney outreach |
