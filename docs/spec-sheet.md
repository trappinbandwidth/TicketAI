# CDL Legal — AI Ticket Scanner
### Product Spec Sheet · June 2026

---

## What Is It?

The CDL Legal AI Ticket Scanner is an internal tool that reads traffic citations — uploaded as a photo, scan, or PDF — and automatically extracts every field a reviewer or case manager would need: ticket date, court date, violation type, citation number, court location, and more. It scores its own confidence on every field, flags anything uncertain, estimates what the driver will pay, and suggests the right attorneys to handle the case.

The goal is to cut manual data entry from minutes to seconds and feed clean, verified data directly into Salesforce.

---

## How It Works — High Level

```
Driver uploads ticket (JPG / PDF / PNG)
         ↓
  OCR + image prep
         ↓
 AI Agent — Lone Ranger (Pass 1, temp 1.0)
   Extracts all 13 fields + confidence scores
         ↓
   Referee Agent evaluates confidence
         ↓
  GREEN? ──────────────────────────────► Book Worm → CDL Impact → Done
  YELLOW / RED?
         ↓
 AI Agent — Lone Ranger (Pass 2, temp 0.4)
   Second extraction, lower temperature = more conservative
         ↓
   Consensus Agent merges both passes
   Fields where passes disagree → flagged as "Dual Conflict"
         ↓
   Referee Agent 2 re-evaluates
         ↓
  Book Worm → CDL Impact → Done
```

Results are saved to a SQLite review queue. A reviewer opens the portal, verifies or edits fields, and approves — which writes a Ticket record directly to Salesforce.

---

## Features

### 1. AI Extraction — 13 Fields Automatically

Every ticket scan extracts:

| Field | Description |
|---|---|
| Date of Ticket | Issue date of the citation |
| Violation Description | Raw text from the citation |
| Violation Category | Normalized to 18-value CDL picklist |
| Court Date | Appearance or response deadline |
| Accident Involved | Yes / No |
| License Type | CDL, CDL-A, CDL-B, etc. |
| Court Name | Name of the court |
| Court Phone | Direct court contact number |
| Ticket City | City where violation occurred |
| Ticket County | County for attorney matching |
| Ticket State | State — triggers state-specific rules |
| Inspection Report # | FMCSA/DOT report number if present |
| Citation Number | Unique citation identifier |

Each field includes a **confidence score (0–100%)** and an **AI reasoning explanation** visible on hover.

---

### 2. Multi-Pass Confidence Pipeline

- **GREEN** — All fields ≥ 85% confidence. Fast path: single AI pass, instant result.
- **YELLOW** — One or more fields between 60–84%. Triggers a second AI pass at lower temperature for more conservative extraction. Both results are merged by a Consensus agent.
- **RED** — One or more critical fields below 60%. Escalation required. Reviewer is shown detailed AI reasoning per field.

**Dual Conflict Detection:** When Pass 1 and Pass 2 both have high confidence but produce different values, the field is flagged with a purple "Conflict" badge and surfaced at the top of the review list.

---

### 3. State-Specific Court Date Rules

The AI knows that different states handle court dates differently:

- **Florida** — Civil infractions: court date calculated as 30 days from ticket date (per FL Statute). Criminal charges (DUI, suspended license, reckless): printed court date extracted directly.
- **Washington** — No court date printed on citation. Response deadline calculated as 30 days from issue date. Criminal charges use the printed court date.
- **Maryland** — Citation numbers not printed on MD tickets; AI confirms absence with 0.95 confidence rather than flagging as extraction failure.

---

### 4. Driver Price Estimator

Automatically calculates what the driver will likely pay CDL Legal, shown on every scan:

- **Formula:** Attorney avg cost + $400 CDL fee = base price ±15–20%
- **Color coded:** Green = standard risk, Orange = high risk violation
- **Data source labeled:** Historical (matched data) or Fallback (state average)
- Includes win rate % and sample size so reviewers know how reliable the estimate is

---

### 5. Attorney Matching (Team David V2)

After extraction, the system queries Salesforce for the top 3 attorneys to handle the ticket, ranked by:

1. **County match** beats state-only coverage
2. **Win rate** (closed ticket history)
3. **Total tickets** handled (experience)
4. **Average rating**

Each attorney card shows rank medal (🥇🥈🥉), coverage type (County / State), win rate, ticket count, rating, phone, and email — all clickable.

**No Coverage Alert:** If no attorney covers the state + county, a red warning flag appears and the team is notified to find coverage manually.

> Attorney data is live-queried from Salesforce and cached for 4 hours per state/county pair.

---

### 6. Salesforce Integration

When a reviewer approves a ticket:

1. A **Ticket__c** record is created in Salesforce with all extracted (and reviewer-corrected) fields
2. The Salesforce ticket ID is stored locally
3. A **"View in Salesforce"** link appears in the confirmation screen for immediate case access

---

### 7. QA Reviewer Portal

A browser-based review interface at `localhost:3456`:

**Upload & Scan**
- Drag-and-drop or click-to-browse for JPG, PNG, PDF
- Optional driver name field
- Prompt version selector (v1 / v2)

**Review Screen**
- Side-by-side: document image (sticky) + extracted fields (scrollable)
- Every field is inline-editable with edit tracking ("3 edits pending")
- Confidence bar under each field, color-coded green/yellow/red
- AI reasoning visible on hover (or always shown for low-confidence fields)
- Conflict fields shown in purple at the top of the list
- "Problems only" toggle hides all high-confidence fields to focus review time

**Action Bar**
- ✓ Approve & Save → creates Salesforce record, saves to training dataset
- ✗ Reject → optional rejection reason
- ↩ New Scan → reset and start over

**Keyboard Shortcuts** (when not typing in a field):

| Key | Action |
|---|---|
| `G` | Approve |
| `R` | Reject |
| `P` | Toggle Problems Only |
| `B` | Bulk approve all GREEN pending |

---

### 8. Recent Scans Sidebar

Always visible alongside the review panel:

- Live list of all scans, auto-refreshes every 15 seconds
- **Filter by pass status:** All / 🟢 Green / 🟡 Yellow / 🔴 Red
- **Filter by review status:** All / Pending / Approved / Rejected
- Pending RED tickets sorted to the top
- Click any row to load that scan immediately
- **⚡ Bulk approve greens** — one click approves all pending GREEN scans with no edits

---

### 9. Training Data Export

Every approved ticket (with any reviewer corrections applied) is appended to a local JSONL training file:

```json
{
  "id": "...",
  "filename": "FL_Ticket_001.jpg",
  "approved_at": "2026-06-12T14:32:00",
  "original_extraction": { "Court_Date__c": { "value": "05/21/2024", "confidence_score": 0.95 } },
  "final_values": { "Court_Date__c": "05/21/2024" },
  "was_edited": false,
  "pass_status": "green"
}
```

`GET /api/v1/training/export` downloads the full dataset as a `.jsonl` attachment — ready for model fine-tuning.

---

## Supported File Types

| Format | Notes |
|---|---|
| JPG / JPEG | Phone photos work — no flatbed scan required |
| PNG | Screenshots of digital citations |
| PDF | Multi-page supported; first page shown in preview |

---

## System Architecture

| Layer | Technology |
|---|---|
| AI Backend | Python · FastAPI · LangGraph |
| AI Model | Claude Sonnet 4.6 (Anthropic) — multimodal |
| OCR Pre-processing | pdf2image + pytesseract |
| Queue / Storage | SQLite (local) |
| Salesforce | simple-salesforce REST API |
| Frontend | Vanilla HTML/JS · Tailwind CSS |
| Hosting | Local dev server (FastAPI uvicorn + static file server) |

---

## States Currently Tested

| State | Court Date Rule | Mock Attorneys |
|---|---|---|
| Florida | 30-day payment window (civil) / printed date (criminal) | 3 |
| Maryland | Standard extraction (citation # not on ticket) | 3 |
| Washington | 30-day response deadline (civil) / printed date (criminal) | 5 |

---

## Roadmap

| Feature | Status |
|---|---|
| Dual extraction pipeline (YELLOW/RED) | ✅ Live |
| State-specific court date rules (FL, WA) | ✅ Live |
| Driver price estimator | ✅ Live |
| Attorney matching (Team David V2) | ✅ Live |
| Salesforce case creation on approval | ✅ Live |
| QA portal — keyboard shortcuts | ✅ Live |
| QA portal — bulk approve greens | ✅ Live |
| QA portal — sidebar filters | ✅ Live |
| Dual conflict field highlighting | ✅ Live |
| Prompt v2 (improved extraction accuracy) | ✅ Live |
| S3 batch processor | 🔲 Pending (server engineers) |
| Additional state rules | 🔲 In progress |

---

*CDL Legal — Internal Use Only · ai-ticket-engine · github.com/CDL-Legal/ai-ticket-engine*
