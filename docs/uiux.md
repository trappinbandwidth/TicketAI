# Rig Resolve — UI/UX Documentation

## Platform Overview

There are four distinct user-facing interfaces, each targeting a different user type:

| Interface | Users | Technology | Deploy URL |
|-----------|-------|-----------|-----------|
| Driver App | CDL holders | Vite + React + TypeScript | rigresolve.web.app |
| Attorney Portal | CDL defense attorneys | Vite + React | rigresolve-attorney.web.app |
| Carrier Portal | Trucking company admins | Vite + React | rigresolve-carrier.web.app |
| Admin Dashboard (QA Tool) | Rig Resolve staff | Vite + React + TypeScript | Local only (not yet deployed) |

All frontends authenticate via Firebase Auth (email/password). Each backend verifies Firebase ID tokens.

---

## Driver App

**Path:** `/Users/digitalmercenary/CDL_Defense/driver-app-main/`  
**Auth:** Firebase Phone Auth (OTP) — phone number is the login, UID is the driver ID

### Core Screens

#### 1. Onboarding / Authentication
- Phone number entry → SMS OTP verification via Firebase Phone Auth
- On first login: driver profile creation (name, CDL number, CDL state, DOB)
- Plan selection: Core ($14.99/mo) vs. Pro ($24.99/mo) with optional safe driver discount

#### 2. Dashboard / Home
- Shows list of open cases with status badges
- Real-time updates via Firestore `onSnapshot` on `drivers/{uid}/tickets/`
- Status badges map to `attorney_status` field:
  - `AI Review` → "Submitted — Under Review" (gray)
  - `New` → "Processing" (blue)  
  - `Admin Assigned` → "Attorney Matched" (blue)
  - `Accepted` → "Attorney Accepted" (green)
  - `Ticket Closed` → "Case Closed" (slate, shows outcome)
  - `Rejected` → "Unable to Process" (red, shows reason)

#### 3. Ticket Submission
Upload flow for driver-submitted tickets (`source: "driver_upload"`):
1. Photo capture or gallery upload (JPEG/PNG/PDF)
2. Optional: Driver statement form (9 fields for Statement of Record)
   - Where stopped / what you were doing / weather / road signs / your speed
   - What the officer said / dashcam? / other witnesses / dispute details
3. Optional: Evidence upload (dashcam footage, receipts, photos)
4. Submit → ticket immediately appears as `New` in attorney queue (no review step for driver uploads)

#### 4. Case Detail
Per-ticket view showing:
- Violation extracted by AI
- Court date
- Assigned attorney name, phone, email
- Price estimate
- CDL impact (points, disqualification risk)
- Status timeline
- Case outcome when closed

#### 5. Notifications
- In-app notification bell — unread count badge
- Reads from `drivers/{uid}/notifications/` subcollection
- Notification types:
  - `case_update` — every status transition
  - `court_reminder` — 14 days, 7 days, and daily <7 days before court
- Tap to mark as read (updates `read: true` via client SDK)

### Firestore Real-Time Pattern
```
drivers/{uid}/tickets/   → onSnapshot → dashboard list
drivers/{uid}/notifications/ → onSnapshot → notification bell
```

---

## Attorney Portal

**Path:** `/Users/digitalmercenary/CDL_Defense/Attorney-Portal-main/frontend/`  
**Auth:** Firebase email/password, `role: "attorney"` auto-assigned  
**Backend:** `https://attorney-portal-626128667800.us-central1.run.app`  
**API prefix:** `/RigResolveAttorneyService/api/v1/`

### Core Screens

#### 1. Login
Standard email/password via Firebase Auth SDK.

#### 2. Available Cases
- Lists all tickets in `New` status (approved by admin, not yet assigned to attorney)
- Each card shows: driver name, violation, state/county, court date, price range, CDL impact
- "Claim" button → attorney submits claim → ticket moves to `Accepted`
- Filter by state, violation type, court date proximity

#### 3. My Cases
- Lists tickets the logged-in attorney has claimed (`attorney_id == auth.uid`)
- Status: `Accepted` → `Active` → `Outcome Logged`
- Each case card shows court date, driver, violation, days until court

#### 4. Case Detail
- Full ticket extraction: all extracted fields, confidence scores, court info
- Driver contact info
- Statement of Record (when driver submitted one)
- CDL impact analysis from Book Worm
- Jurisdiction context from Research Ron (appearance rules, court portal links)
- Outcome recording form: won / dismissed / reduced / lost / transferred

#### 5. Attorney Profile
- Personal info, states licensed, counties covered
- Payout method and details (self-editable via client SDK)
- Win rate and case count statistics

### Filtering Logic
`get_available_cases()` in `firebase_service.py` excludes statuses:
```
["Accepted", "Ticket Closed", "AI Review", "Rejected"]
```
So attorneys only see `New` and any other non-excluded statuses.

---

## Carrier Portal

**Path:** `/Users/digitalmercenary/CDL_Defense/carrier-portal-change-driver-tab-1 3/frontend/`  
**Auth:** Firebase email/password, `role: "carrier"` auto-assigned  
**Backend:** `https://carrier-portal-626128667800.us-central1.run.app`  
**API prefix:** `/RigResolveCarrierService/api/v1/`

### Core Screens

#### 1. Login
Standard email/password via Firebase Auth.

#### 2. Fleet Dashboard
- Total enrolled drivers, active drivers count
- Monthly invoice status (current, overdue, paid)
- Quick stats: tickets this month, cases open

#### 3. Drivers Tab
- List of all enrolled drivers
- Add/remove drivers from fleet
- View each driver's subscription status, plan, CDL class
- Can see driver's open cases (not full case details)

#### 4. Billing & Invoices
- Current monthly invoice
- Invoice history
- Payment status per invoice
- Per-driver rate display

#### 5. Carrier Profile
- Company info, billing contacts
- DOT number, MC number
- Billing type (invoice vs. payroll deduction)

---

## Admin Dashboard (QA Tool / Internal)

**Path:** `ai-ticket-engine-main/frontend-qa/`  
**Auth:** Firebase email/password — currently any authenticated user; role gating is a pending item  
**Dev server:** `npm run dev` in `frontend-qa/` → http://localhost:5173  
**API proxy:** `/api` → `localhost:8080` (AI engine local)

This is the internal staff tool. It combines AI quality monitoring, ticket review, case management, and operations monitoring into a single interface.

### Navigation

8 tabs across the top:

```
Review Queue | Cases | Operations | Overview | Fields | Agents | Scan Feed | Attorneys
```

---

### Tab: Review Queue

Primary workflow for staff reviewers. Shows all tickets in `AI Review` status.

**What appears here:**
- Manually scanned tickets (source: `manual`) waiting for a reviewer to approve before attorneys can see them
- Sorted: CRITICAL urgency first, then by court date (soonest first)

**Ticket card includes:**
- Driver name, violation, state, court date
- Urgency badge (CRITICAL / HIGH / STANDARD / LOW) with days until court
- Completeness score (0–100%) — how complete the AI extraction is
- CDL match status (match / mismatch / unverified) — PII check result
- Conflict count from Statement of Record
- MVR/PSP request status
- Low confidence fields list
- Pass status: GREEN / YELLOW / RED

**Reviewer actions:**
- **Approve** → ticket moves to `New`; enters attorney queue; driver notified
- **Reject** → ticket moves to `Rejected`; requires rejection reason; driver notified
- Can click a ticket to open full scan in the Scan Feed tab

**Key reviewer signals to watch:**
- CDL mismatch + CRITICAL urgency = investigate before approving
- Completeness score < 60% = attorney will need to gather info manually
- RED pass status = AI had low confidence; human must verify fields

---

### Tab: Cases

Case management for staff after tickets are approved.

**Sub-tabs:**

#### New Tickets
- All tickets in `New` status awaiting attorney assignment
- Sorted by urgency then court date
- Each ticket shows urgency, violation, state/county, court date, completeness score

**Assign Attorney modal:**
1. Select ticket
2. Attorney dropdown (populated from `/admin/attorneys/list`)
   - Attorneys grouped: suggested (licensed in ticket's state) vs. other
   - Shows win rate, active case count, preferred contact method
3. Select contact method (phone / email / text)
4. Optional note
5. Submit → creates `cases/` document; ticket → `Admin Assigned`

#### Active Cases
- All cases with status beyond `pending_approval`
- Case card shows: attorney name, driver, violation, status badge, days until court
- Click → Case Drawer (slide-in panel)

**Case Drawer:**
- Top: case metadata (attorney, driver, violation, court date, status)
- Activity timeline (newest first): all logged actions with timestamps and notes
- **Log Update form:**
  - Type dropdown: contacted / attorney_update / status_change / note_added
  - Optional: new status transition (from CASE_STATUS_NEXT map)
  - Note text area
  - Submit → logs activity entry; optionally updates case + ticket status
- **Record Outcome button** (shown for active cases):
  - Opens Outcome modal

**Outcome modal:**
- Outcome buttons: Won / Dismissed / Charge Reduced / Lost / Transferred
- Final charge input (shown when "Charge Reduced" selected)
- Notes field
- Submit → calls `/operations/record-outcome/{ticket_id}`; ticket → `Ticket Closed`; driver notified

**Case status progression:**

```
pending_approval → (contact attorney) → active
active → (outcome logged) → outcome_logged
outcome_logged → (payout processed) → payout_sent
payout_sent → closed
(any point) → attorney_declined → reassign
```

Ticket `attorney_status` mirrors case status via `_TICKET_STATUS_MAP`.

---

### Tab: Operations

Two panels for continuous operational monitoring.

#### Court Deadlines Panel
- "Run Now" button → `POST /operations/court-deadlines`
- Returns work queue bucketed by urgency:
  - **CRITICAL** (< 7 days) — red table, attorney must act today
  - **HIGH** (7–21 days) — amber table, assign within 24 hours
  - **STANDARD** (21–60 days) — blue table
  - **LOW** (> 60 days) — gray table
  - **NO_DATE** — tickets with no court date on file
- Each row: driver, violation, state, current status, attorney, days until court
- Also triggers court reminder notifications to drivers when run

#### Payment Alerts Panel
- "Load Alerts" button → `GET /operations/payment-alerts`
- Returns three alert categories:
  - **OPEN_CASE_LAPSED** (red) — driver has open case but subscription lapsed; most urgent
  - **EXPIRING_SOON** (amber) — subscription expires within 7 days
  - **LAPSED** (gray) — lapsed with no open case
- Each card: driver name, email, plan, days left, expiry date

Both panels start empty with instructional text; button changes to "Refresh" after first load.

---

### Tab: Overview

Scan volume analytics. Shows stats from the local SQLite queue database.

- **Total scans** over N days (default 30)
- **Pass rate breakdown**: GREEN / YELLOW / RED as percentages and counts
- **Daily volume** chart: bar chart grouped by pass status
- **Attorney match rate**: % of tickets with attorney matches
- **Price estimate rate**: % of tickets with pricing data
- **Doc type breakdown**: Ticket vs. Inspection Report vs. Crash vs. other

Filter: `?days=7|14|30|90`

---

### Tab: Fields

Per-field AI extraction accuracy tracking. Primary tool for prompt improvement.

**Summary table** (worst accuracy first):
- Field name and which prompt step it belongs to
- Accuracy (% AI value matched human-corrected value)
- Average confidence score
- Empty rate (% of scans where field was blank)
- Edit rate (% of scans where human changed the value)
- Pass 1 fill rate / Pass 2 improvement rate

**Drill-down view** (click any field):
- Shows every scan where this field appeared
- Wrong cases first
- Per-scan: AI value, final human value, confidence score, AI reasoning, pass 1 vs. pass 2 values
- Links to prompt section responsible for this field

Filter by doc type: Ticket / Inspection Report / Crash / Civil Penalty

---

### Tab: Agents

Agent-level health monitoring and per-agent performance stats.

**Sorted by health score ascending (worst first).** Each agent card shows:
- Total events, error count, health score
- Agent-specific stats:
  - **Lone Ranger**: avg fields filled per pass, top empty fields, top low-confidence fields
  - **Referee**: avg confidence score, top critical failures, low-confidence field frequency
  - **Consensus**: avg improvements per scan, top dual-conflict fields
  - **Book Worm**: unknown category count, zero-point tickets, attorney-recommended count
  - **Case Intake**: pass/fail counts, top intake errors
  - **Document Completeness**: avg completeness score, top missing fields
  - **PII Match**: match/mismatch/unverified counts, mismatch rate
  - **MVR Request**: queued vs. skipped counts
  - **PSP Request**: queued vs. skipped counts
  - **Urgency Router**: CRITICAL/HIGH/STANDARD/LOW distribution, avg days until court

Filter by time window: 7 / 14 / 30 days

---

### Tab: Scan Feed

Real-time feed of all scans from the queue database.

- Table: filename, pass status, doc type, attorney match, has price, created at
- Click row → opens full scan detail (all extracted fields, images, agent outputs)
- Limit: last 100 scans

---

### Tab: Attorneys

Attorney coverage analysis by state.

- Table sorted by match rate ascending (states with worst coverage first)
- Per state: total tickets, # matched, # no match, match rate, county match rate, avg win rate
- "No attorney cases" list — specific tickets where no attorney was found (for network expansion targeting)

---

## Design Principles

### Information Density
The admin dashboard is dense by design — staff users are power users. Driver and attorney UIs prioritize clarity over density.

### Real-Time First
Wherever Firestore supports it, use `onSnapshot` rather than polling. Driver app case status and notifications update instantly.

### Urgency Signaling
CRITICAL = red, HIGH = amber, STANDARD = blue, LOW = gray/slate. This mapping is consistent across all urgency surfaces in all portals.

### Empty State over Spinner
If data fails to load, show an empty state with instructional text rather than leaving the user with an infinite spinner. All data-fetching components catch errors and reset state to `[]`.

---

*Last updated: 2026-06-26*
