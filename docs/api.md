# Rig Resolve — API Documentation

## AI Ticket Engine

**Base URL (Production):** `https://ai-ticket-engine-kajugdk3nq-uc.a.run.app`  
**Base URL (Local):** `http://localhost:8080`  
**API Prefix:** `/api/v1`  
**Framework:** FastAPI (Python)  
**Auth:** `x-api-key` header. Default dev key: `cdl-local-dev`. Cloud Run also requires an `Authorization: Bearer <identity_token>` for unauthenticated callers (use `gcloud auth print-identity-token`).

All endpoints return JSON. Timestamps use ISO 8601. All errors follow `{"detail": "..."}` FastAPI format.

---

## Authentication

Every endpoint checks the `x-api-key` header against the `API_KEY` environment variable (default: `cdl-local-dev`). Returns `401` if missing or wrong.

Production Cloud Run is deployed `--no-allow-unauthenticated` — callers must also provide a valid GCP identity token or service account token via `Authorization: Bearer`.

---

## Process Endpoint

### `POST /api/v1/process`

Runs the full AI agent pipeline on one or more ticket images. The primary endpoint.

**Auth:** `x-api-key` header  
**Content-Type:** `multipart/form-data`

**Form fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `files` | `UploadFile[]` | Yes | 1–10 files. JPEG, PNG, or PDF. Multiple files = multi-page ticket. |
| `driver_id` | string | Yes* | Firebase Auth UID. Required for Firestore write and enrollment gate. |
| `ticket_id` | string | Yes* | Pre-generated UUID. Required for Firestore write. |
| `driver_name` | string | No | Driver full name hint to help AI extraction. |
| `source` | string | No | `driver_upload` (default) or `manual`. Controls `attorney_status` on Firestore write. |
| `prompt_version` | string | No | `v2` (default). Selects which extraction prompt to use. |
| `driver_statement` | string | No | JSON-encoded driver intake form (9 fields for Statement of Record). |
| `evidence_files_json` | string | No | JSON-encoded array of `{url, caption, file_type, filename}` evidence items. |

*Required for Firestore dual-write. If omitted, scan runs but does not persist to Firestore.

**Source behavior:**
- `source: "manual"` → `attorney_status: "AI Review"` — hidden from attorneys until a reviewer approves
- `source: "driver_upload"` → `attorney_status: "New"` — immediately visible to attorneys

**Enrollment gate:**
The endpoint verifies the driver has an active subscription via `verify_enrollment(driver_id)`. Returns `403` if driver is not enrolled:
```json
{
  "error": "enrollment_required",
  "status": "lapsed",
  "message": "Subscription required to process tickets."
}
```

**Caching:**
Identical uploads (same image bytes) are detected via SHA-256 hash. If a cached result exists, it is returned immediately without re-running Claude.

**Success response `200`:**
```json
{
  "success": true,
  "mock": false,
  "filename": "ticket.jpg",
  "pages_processed": 1,
  "queue_id": "uuid",
  "pass_status": "green | yellow | red",
  "low_confidence_fields": ["Court_Date__c"],
  "referee_notes": "All fields high confidence. Avg score: 0.91",
  "cdl_point_impact": {
    "violation_category": "Speeding (15+)",
    "cdl_points": 4,
    "severity": "serious",
    "csa_category": "Unsafe Driving",
    "must_appear_in_court": false,
    "attorney_recommended": true
  },
  "doc_severity": null,
  "escalation_reason": null,
  "price_estimate": {
    "avg_attny_price": 850.0,
    "cdl_fee": 65,
    "driver_price_base": 915,
    "driver_price_low": 765,
    "driver_price_high": 1080,
    "win_rate_pct": 0.78,
    "sample_size": 142,
    "high_risk": false,
    "data_source": "historical",
    "display": "$765 – $1,080",
    "note": "Range based on 142 similar cases in Texas."
  },
  "dual_conflicts": ["Ticket_County__c"],
  "attorney_matches": [
    {
      "attorney_id": "atty-001",
      "name": "Marcus T. Williams",
      "email": "mwilliams@cdldefense.com",
      "phone": "+17135550101",
      "rating": null,
      "win_rate": 0.81,
      "total_tickets": 0,
      "match_type": "state"
    }
  ],
  "no_attorney_flag": false,
  "artificial_court_date": false,
  "court_info": {
    "state": "TX",
    "state_name": "Texas",
    "court_system": "Justice of the Peace / Municipal Court",
    "state_portal": "https://www.txcourts.gov",
    "online_payment_url": "",
    "scheduling_url": "",
    "cdl_info_url": "",
    "appear_required_for_serious": true,
    "appear_required": false,
    "notes": "CDL holders with serious violations must appear.",
    "county_court": {
      "county": "Harris",
      "court_name": "Harris County Justice Court",
      "website": "",
      "scheduling_url": "",
      "phone": "(713) 274-0300",
      "address": "301 Fannin St, Houston TX 77002",
      "notes": ""
    }
  },
  "cdl_point_estimate": {
    "state_points_display": "4 points",
    "disqualification_risk": "moderate"
  },
  "payment_options": {
    "base_amount": 915.0,
    "days_until_court": 47,
    "options": []
  },
  "urgency_level": "STANDARD",
  "urgency_reason": "Court date in 47 days.",
  "completeness_score": 0.9,
  "missing_fields": ["Court_Location__c"],
  "result": {
    "file_type": "Ticket",
    "Date_of_Ticket__c": {
      "value": "03/15/2024",
      "confidence_score": 0.98,
      "ai_reason": "Date clearly printed on citation."
    },
    "Violation_Description__c": {
      "value": "Speed 72/60 MPH",
      "confidence_score": 0.95,
      "ai_reason": "Speed clearly stated on ticket.",
      "items": ["Speed 72/60 MPH"]
    },
    "Violation_Category__c": {
      "value": "Speeding (15+)",
      "confidence_score": 0.92,
      "ai_reason": "Speed differential is 12 MPH over."
    },
    "Court_Date__c": { "value": "04/12/2024", "confidence_score": 0.87, "ai_reason": "..." },
    "Ticket_State__c": { "value": "Texas", "confidence_score": 0.99, "ai_reason": "..." },
    "Ticket_County__c": { "value": "Harris", "confidence_score": 0.88, "ai_reason": "..." },
    "Ticket_City__c": { "value": "Houston", "confidence_score": 0.91, "ai_reason": "..." },
    "Citation_Number__c": { "value": "TX-2024-88712", "confidence_score": 0.94, "ai_reason": "..." },
    "Driver_Name__c": { "value": "James T. Booker", "confidence_score": 0.97, "ai_reason": "..." },
    "CDL_License_Number__c": { "value": "TX12345678", "confidence_score": 0.93, "ai_reason": "..." },
    "CDL_Class__c": { "value": "Class A", "confidence_score": 0.95, "ai_reason": "..." }
  }
}
```

**Error responses:**
- `400` — No files provided, or >10 files
- `401` — Invalid API key
- `403` — Driver not enrolled
- `415` — Unsupported file type
- `422` — Extraction produced incomplete fields (rare)
- `500` — Pipeline failure

---

## Queue Endpoints

### `GET /api/v1/queue`
Returns the 50 most recent scans from the local SQLite queue.  
**Response:** `{"scans": [...], "total": N}`

### `GET /api/v1/queue/{item_id}`
Returns a single scan by queue ID (same as `queue_id` in process response).  
**Response:** Full scan object including `process_response`, `images_b64`, all extraction passes.  
**404** if not found.

### `PUT /api/v1/queue/{item_id}/approve`
Approves a scan in the local SQLite queue (distinct from Firestore approve).  
**Body:**
```json
{
  "edited_fields": {"Court_Date__c": "04/20/2024"},
  "reviewer_id": "quest"
}
```

### `PUT /api/v1/queue/{item_id}/reject`
Rejects a scan in the local SQLite queue.  
**Body:** `{"reason": "Bad image quality"}`

### `GET /api/v1/queue/{item_id}/audit`
Returns the field-level edit audit trail for a scan.

---

## Pricing Endpoint

### `GET /api/v1/price-estimate`
Returns a price estimate for a given state + violation.

**Query params:**
- `state` — Full state name, e.g. `Florida`
- `violation` — Violation category from picklist (see Violation Categories below)

**Response:**
```json
{
  "state": "Florida",
  "violation_category": "Speeding (15+)",
  "avg_attny_price": 900.0,
  "cdl_fee": 75,
  "driver_price_base": 975,
  "driver_price_low": 800,
  "driver_price_high": 1150,
  "win_rate_pct": 0.74,
  "sample_size": 89,
  "high_risk": true,
  "data_source": "historical",
  "note": "Range based on 89 similar cases in Florida.",
  "display": "$800 – $1,150"
}
```

---

## Admin Endpoints

All admin endpoints require `x-api-key`.

### `GET /api/v1/admin/stats/overview`
Scan volume and pass rate analytics.  
**Query:** `?days=30` (default 30)  
**Response:** total, green_rate, yellow_rate, red_rate, attorney_match_rate, county_match_rate, price_estimate_rate, doc_type_breakdown, daily_volume

### `GET /api/v1/admin/stats/fields`
Per-field accuracy statistics sorted by accuracy ascending.  
**Query:** `?doc_type=Ticket` (optional filter)  
**Response:** Array of field stats with accuracy, avg_confidence, empty_rate, edit_rate, prompt_section.

### `GET /api/v1/admin/stats/fields/{field_key}`
Drill-down into all scan cases for a specific field.  
**Response:** Per-scan list with AI value, final value, confidence, AI reasoning, wrong/correct flag.

### `GET /api/v1/admin/stats/agents`
Agent health scorecard.  
**Query:** `?days=30`  
**Response:** Per-agent stats — events, errors, health score, agent-specific metrics.

### `GET /api/v1/admin/stats/feed`
Scan feed (most recent N scans).  
**Query:** `?limit=100`  
**Response:** `{"scans": [...], "total": N}` — lightweight list without full extraction data.

### `GET /api/v1/admin/stats/attorneys`
Attorney match rate by state. Sorted by match rate ascending (worst coverage first).

### `GET /api/v1/admin/stats/urgency`
Live urgency breakdown of the current AI Review queue in Firestore.  
Returns CRITICAL/HIGH/STANDARD/LOW buckets with ticket cards, CDL mismatch alerts, avg days until court.

### `GET /api/v1/admin/review-queue`
All tickets in `AI Review` status, sorted by urgency then court date.  
Each ticket includes a `reviewer_summary` map with completeness score, missing fields, CDL match, conflict count, MVR/PSP status.

### `POST /api/v1/admin/approve-ticket/{ticket_id}`
Approve an AI Review ticket → moves to `New`.  
**Query:** `?reviewer_id=quest`  
**Response:**
```json
{"success": true, "ticket_id": "...", "attorney_status": "New"}
```

### `POST /api/v1/admin/reject-ticket/{ticket_id}`
Reject an AI Review ticket → moves to `Rejected`.  
**Query:** `?reason=Bad+image`  
**Response:**
```json
{"success": true, "ticket_id": "...", "attorney_status": "Rejected"}
```

### `GET /api/v1/admin/training/export`
Downloads the JSONL training data file (all approved scans with corrections).  
**Response:** `Content-Type: application/x-ndjson` file download.

---

## Cases Endpoints

All cases endpoints require `x-api-key`.

### `GET /api/v1/admin/attorneys/list`
Returns all active attorneys for the case assignment dropdown.  
**Response:**
```json
{
  "attorneys": [
    {
      "attorney_id": "atty-001",
      "full_name": "Marcus T. Williams",
      "firm_name": "Williams CDL Defense Group",
      "tier": "senior",
      "states_licensed": ["TX", "LA", "OK"],
      "counties_covered": ["TX:Harris", "TX:Dallas"],
      "win_rate": 0.81,
      "cases_active": 3,
      "max_active_cases": 999,
      "phone": "+17135550101",
      "email": "mwilliams@cdldefense.com",
      "preferred_contact_method": "phone"
    }
  ],
  "total": 5
}
```
Sorted by win rate descending. "Suggested" attorneys (licensed in ticket state) should be surfaced first in UI.

### `GET /api/v1/admin/cases/available`
Returns all tickets in `New` status awaiting attorney assignment.  
Sorted by urgency then court date.

**Response:**
```json
{
  "tickets": [
    {
      "ticket_id": "...",
      "driver_name": "James Booker",
      "driver_id": "...",
      "violation_category": "Speeding (15+)",
      "violation_description": "Speed 72/60 MPH",
      "ticket_state": "Texas",
      "ticket_county": "Harris",
      "court_date": "04/12/2024",
      "date_of_ticket": "03/15/2024",
      "citation_number": "TX-2024-88712",
      "urgency_level": "HIGH",
      "urgency_reason": "Court date in 14 days.",
      "completeness_score": 0.9,
      "price_display": "$765 – $1,080",
      "price_low": 765,
      "price_high": 1080,
      "pass_status": "green",
      "reviewed_by": "quest",
      "reviewed_at": "...",
      "created_at": "..."
    }
  ],
  "total": 1
}
```

### `GET /api/v1/admin/cases`
List cases, optionally filtered by status.  
**Query:** `?status=active`  
**Response:** `{"cases": [...], "total": N}`

### `POST /api/v1/admin/cases`
Create a case (assign an attorney to a ticket).  
**Body:**
```json
{
  "ticket_id": "...",
  "attorney_id": "atty-001",
  "assigned_by": "quest",
  "contact_method": "phone",
  "note": "Reached out by phone — attorney reviewing."
}
```
**Response:**
```json
{
  "success": true,
  "case_id": "...",
  "ticket_id": "...",
  "attorney_name": "Marcus T. Williams",
  "attorney_status": "Admin Assigned"
}
```
Side effects:
- Creates `cases/{case_id}` document
- Creates first `cases/{case_id}/activity/{id}` entry
- Updates `tickets/{ticket_id}` → `attorney_status: "Admin Assigned"`, sets attorney info
- Increments `attorneys/{attorney_id}.cases_active`

**Error 400:** Ticket is not in `New` status.  
**Error 404:** Ticket or attorney not found.

### `GET /api/v1/admin/cases/{case_id}`
Case detail including full activity log and linked ticket.  
**Response:**
```json
{
  "case_id": "...",
  "ticket_id": "...",
  "attorney_id": "atty-001",
  "attorney_name": "Marcus T. Williams",
  "driver_name": "James Booker",
  "violation": "Speeding (15+)",
  "ticket_state": "TX",
  "court_date": "04/12/2024",
  "status": "active",
  "contact_method": "phone",
  "contacted_at": "...",
  "assigned_at": "...",
  "activity": [
    {
      "activity_id": "...",
      "type": "assigned",
      "note": "Case created — Marcus T. Williams assigned by quest.",
      "old_status": "New",
      "new_status": "pending_approval",
      "created_by": "quest",
      "created_by_name": "quest",
      "created_at": "..."
    }
  ],
  "ticket": { /* full ticket document */ }
}
```

### `POST /api/v1/admin/cases/{case_id}/activity`
Log an activity entry on a case, optionally updating case status.  
**Body:**
```json
{
  "type": "contacted",
  "note": "Called Marcus at 2pm — he'll review case and confirm by EOD.",
  "new_status": "active",
  "created_by": "quest",
  "created_by_name": "Quest"
}
```

**Valid activity types:** `assigned | contacted | attorney_update | status_change | outcome_logged | payout_created | note_added`

**Valid case statuses:** `pending_approval | active | attorney_declined | outcome_logged | payout_sent | closed | rejected`

Side effects when `new_status` provided:
- Updates `cases/{case_id}.status`
- Updates linked `tickets/{ticket_id}.attorney_status` via `_TICKET_STATUS_MAP`
- Sets `contacted_at` if type is `contacted`
- Sets `closed_at` if new_status is `closed`

---

## Operations Endpoints

Designed to be called by Cloud Scheduler (cron) or manually from the admin dashboard. All require `x-api-key`.

### `POST /api/v1/operations/court-deadlines`

Scans all open tickets for approaching court dates. Generates the daily priority work queue. Optionally sends driver court reminder notifications.

**Query:** `?send_driver_reminders=true` (default true)

**Open statuses scanned:** `New`, `Accepted`, `AI Review`

**Urgency buckets:**
- `CRITICAL` — court date in < 7 days OR past
- `HIGH` — 7–21 days
- `STANDARD` — 21–60 days
- `LOW` — > 60 days
- `NO_DATE` — no court date on file

**Response:**
```json
{
  "run_at": "2024-03-15T08:00:00+00:00",
  "total_open": 12,
  "critical_count": 2,
  "high_count": 4,
  "no_date_count": 1,
  "driver_reminders_sent": 3,
  "work_queue": {
    "CRITICAL": [
      {
        "ticket_id": "...",
        "driver_id": "...",
        "driver_name": "James Booker",
        "violation": "Speeding (15+)",
        "state": "TX",
        "court_date": "03/20/2024",
        "days_until_court": 5,
        "attorney_status": "Accepted",
        "attorney_name": "Marcus T. Williams",
        "urgency_level": "CRITICAL"
      }
    ],
    "HIGH": [...],
    "STANDARD": [...],
    "LOW": [...],
    "NO_DATE": [...]
  }
}
```

Driver reminder notifications sent at:
- `days_until_court < 7` — every time endpoint is called (daily)
- `days_until_court == 7` or `== 14` — milestone reminders

**Recommended cron:** Daily at 8am Central.

---

### `POST /api/v1/operations/record-outcome/{ticket_id}`

Records the final case outcome. Called by admin or attorney portal when a case resolves.

**Body:**
```json
{
  "outcome": "won",
  "outcome_notes": "Judge dismissed on procedural grounds.",
  "final_charge": null,
  "attorney_id": "atty-001",
  "attorney_name": "Marcus T. Williams"
}
```

**Valid outcomes:** `won | dismissed | reduced | lost | transferred`

- `reduced` → use `final_charge` to capture what the charge was reduced to

**Side effects:**
- Updates `tickets/{ticket_id}` with outcome fields and `attorney_status: "Ticket Closed"`
- Updates `drivers/{driver_id}/tickets/{ticket_id}` with outcome fields
- Sends driver notification via Driver Concierge

**Response:**
```json
{
  "success": true,
  "ticket_id": "...",
  "outcome": "won",
  "attorney_status": "Ticket Closed",
  "driver_notified": true
}
```

---

### `GET /api/v1/operations/payment-alerts`

Scans all driver profiles for subscription issues.

**Alert types:**
- `OPEN_CASE_LAPSED` — driver has an active case but subscription is lapsed/cancelled → critical
- `EXPIRING_SOON` — subscription expires within 7 days
- `LAPSED` — lapsed with no open case

**Response:**
```json
{
  "run_at": "...",
  "critical_count": 1,
  "lapsed_count": 3,
  "expiring_soon_count": 2,
  "critical": [
    {
      "driver_id": "...",
      "name": "Maria Gutierrez",
      "email": "mgutierrez@email.com",
      "subscription_status": "lapsed",
      "plan": "pro",
      "expires": "02/28/2024",
      "days_left": -15,
      "open_cases": ["ticket-id-1"],
      "alert_type": "OPEN_CASE_LAPSED"
    }
  ],
  "lapsed": [...],
  "expiring_soon": [...]
}
```

---

### `GET /api/v1/operations/case-status`

Unified case manager work queue across all active statuses.

**Query params:**
- `?state=TX` — filter by ticket state
- `?urgency=CRITICAL` — filter by urgency level

**Response:**
```json
{
  "run_at": "...",
  "filters": {"state": null, "urgency": null},
  "total_active": 12,
  "urgency_breakdown": {"CRITICAL": 2, "HIGH": 4, "STANDARD": 5, "LOW": 1},
  "needs_action_count": 6,
  "needs_action": [...],
  "by_status": {
    "AI Review": [...],
    "New": [...],
    "Accepted": [...]
  }
}
```

`needs_action` includes cases where: urgency is CRITICAL or HIGH, OR CDL mismatch detected, OR completeness score < 60%.

---

## Training Endpoints

### `GET /api/v1/training/export`
Downloads the JSONL training file containing all human-approved corrections.  
**Response:** `application/x-ndjson` file download named `approved_tickets.jsonl`.

---

## Violation Categories (Picklist)

All extraction and API calls use these exact strings for `Violation_Category__c`:

```
Driver license violation
Alcohol / Drug related violation
Reckless Driving
Speeding (15+)
Cell Phone
Failure to yield to emergency vehicle
Following too close
Careless Driving
Lane Violation
Failure to Obey Traffic Control Device
Too Fast for Conditions
Speeding (1-14)
Seatbelt
ELD/Logs
Equipment/Maintenance
Registration Violations
Overweight/Overlength
Parking
```

---

## Ticket Status Lifecycle

```
(manual scan)   → AI Review → (approve) → New
(driver upload) →                         New

New → (assign attorney) → Admin Assigned
Admin Assigned → (contact attorney) → Atty Contacted (optional)
Atty Contacted → (attorney confirms) → Accepted
Accepted → Active
Active → (outcome recorded) → Outcome Logged
Outcome Logged → (payout sent) → Payout Sent
Payout Sent → Closed

(at any point) → Atty Declined → (reassign) → Admin Assigned

AI Review → (reject) → Rejected
```

**`cases.status` ↔ `tickets.attorney_status` mapping:**

| Case Status | Ticket Attorney Status |
|-------------|----------------------|
| `pending_approval` | `Admin Assigned` |
| `active` | `Accepted` |
| `attorney_declined` | `Atty Declined` |
| `outcome_logged` | `Outcome Logged` |
| `payout_sent` | `Payout Sent` |
| `closed` | `Closed` |
| `rejected` | `Rejected` |

---

## Attorney Portal Backend

**Base URL:** `https://attorney-portal-626128667800.us-central1.run.app`  
**API Prefix:** `/RigResolveAttorneyService/api/v1/`  
**Auth:** Firebase ID token in `Authorization: Bearer <token>` header  
**Framework:** Flask (Python)

All endpoints call `verify_id_token()` which returns `{DriverId, Email, Name, Role}`.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/RigResolveAttorneyService/HealthCheck` | GET | Health check |
| `/RigResolveAttorneyService/api/v1/available-cases` | GET | New tickets |
| `/RigResolveAttorneyService/api/v1/my-cases` | GET | Logged-in attorney's cases |
| `/RigResolveAttorneyService/api/v1/cases/{id}` | GET | Case detail |
| `/RigResolveAttorneyService/api/v1/cases/{id}/claim` | POST | Claim a case |

---

## Carrier Portal Backend

**Base URL:** `https://carrier-portal-626128667800.us-central1.run.app`  
**API Prefix:** `/RigResolveCarrierService/api/v1/`  
**Auth:** Firebase ID token  
**Framework:** Flask (Python)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/RigResolveCarrierService/HealthCheck` | GET | Health check |
| `/RigResolveCarrierService/api/v1/drivers` | GET | Fleet drivers list |
| `/RigResolveCarrierService/api/v1/drivers` | POST | Add driver to fleet |
| `/RigResolveCarrierService/api/v1/invoices` | GET | Invoice history |

---

*Last updated: 2026-06-26*
