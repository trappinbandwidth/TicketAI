# Rig Resolve — Master Build Plan
**Last Updated:** 2026-06-28  
**Prepared by:** Claude Code  
**Status:** Active — Use this to track what ships next

---

## System Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Firebase Auth (all portals)                  │
│                         Firestore (shared data layer)                │
│                         Firebase Storage (files + scan images)       │
└─────────────────────────────────────────────────────────────────────┘
         │                        │                        │
   ┌─────▼──────┐          ┌──────▼──────┐         ┌──────▼──────┐
   │ Driver App  │          │ Attorney    │         │  Carrier    │
   │ (Flutter/  │          │ Portal      │         │  Portal     │
   │  React PWA)│          │ React+Flask │         │  React+Flask│
   └────────────┘          └─────────────┘         └─────────────┘
         │                        │                        │
         └──────────┬─────────────┘                        │
                    │                                       │
             ┌──────▼──────────────────────────────────────▼──────┐
             │            AI Ticket Engine (FastAPI)               │
             │  scan → extract → enrich → match attorney → write   │
             └─────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
              FMCSA API          MVR Vendor      Twilio / SendGrid
```

---

## SECTION 1 — Attorney Portal

### Current State: What's Done

| Area | Status | Notes |
|------|--------|-------|
| Firebase Auth (email, Google, Microsoft, Apple) | ✅ Done | All 4 methods work |
| Attorney registration (4-chapter onboarding wizard) | ✅ Done | Forms complete; Firestore write not wired |
| Dashboard KPI cards | ✅ Done | Real data; some agenda items still dummy |
| Available Cases list + claim button | ✅ Done | Soft-claim flow works end-to-end |
| Reviewer Queue (approve/reject claimants) | ✅ Done | Approve works; reject endpoint missing |
| Backend routes for ticket detail, chat, history | ✅ Done | All routes exist in Flask |
| Firestore migration from Salesforce | ✅ Done | Complete |
| Cloud Run deploy | ✅ Done | Live at attorney-portal Cloud Run URL |
| Firebase Hosting frontend | ✅ Done | Live at rigresolve-attorney.web.app |

---

### Attorney Portal — Changes & Builds Needed

#### P0 — Blocking (Attorneys can't work cases without these)

---

**AP-01 | Case Detail Page**  
_The single biggest gap. Attorneys can claim a case but have nowhere to manage it._

Build `/cases` list and `/cases/:id` detail page.

List page:
- All tickets where `attorney_id == current_user`
- Columns: Citation #, Driver Name, Violation, State, Court Date, Status, Days Until Court
- Status filter pills: All / Active / Waiting / Past Due / Closed
- Color-coded urgency: red = past due, yellow = <7 days, green = OK

Detail page tabs:
- **Ticket** — All extracted fields: violation, citation #, state, county, city, court date/time, fine amount, statute code
- **Driver** — Driver name, CDL #, DOB, address, phone, email (contact info for attorney to reach driver)
- **Evidence** — Documents uploaded by Rig Resolve staff or carrier; AI scan images
- **Statement** — AI-generated case summary from ticket scan (stored in `process_response`)
- **Case Value** — Fee calculated from attorney's rate structure × violation type. e.g., if attorney charges $250 flat for speeding, show "$250 estimated"
- **Updates / Chat** — Chronological log of all case notes and updates
- **History** — Field-level audit trail of every change made to the ticket

Actions on detail page:
- **Update Case** — Quick update bar (category dropdown + text + submit)  
  Categories: Court Date Update, Status Update, Document Submitted, Resolution Update, Payment Update, Attorney Note, Other
- **Upload Document** — File picker → Firebase Storage → metadata in `tickets/{id}/updates`
- **Request File** — Modal: select file type + notes → writes to `tickets/{id}/file_requests/` → triggers email to driver
- **Accept / Decline** (for cases in claiming state)
  - Accept → `claimTicket` API call
  - Decline → modal with required reason → `POST /declineCase { ticketId, reason }`

_Files:_ New `frontend/src/pages/cases.tsx`, `frontend/src/pages/case-detail.tsx`, `frontend/src/sections/cases/`  
_API:_ `getTicketDetailById`, `getTicketChatDetailById`, `getFieldUpdateHistory` (already built)  
_New API:_ `POST /declineCase`, `POST /requestFile`

---

**AP-02 | Fix Reviewer Queue Reject**  
_Reject button currently calls a route that doesn't exist._

Add `POST /rejectClaim` to `routes/attorney_portal/post_methods.py`:
```python
@router.post("/rejectClaim")
def reject_claim():
    ticket_id = request.json.get("ticketId")
    reason = request.json.get("reason", "")
    reviewer_id = get_user_data(...)["DriverId"]
    # Update ticket: attorney_status = "New" (put back in pool), clear claimants
    # Write rejection notification to all claimants
```

_Files:_ `backend/.../routes/attorney_portal/post_methods.py`

---

**AP-03 | Wire Onboarding Persistence**  
_Attorneys complete 4-chapter onboarding but none of it saves to Firestore. Profile is empty after setup._

Add `POST /attorney/profile/complete` that accepts the full onboarding payload:
```json
{
  "firm_name": "Holloway Transport Law",
  "bar_number": "FL12345",
  "practice_states": ["FL", "GA"],
  "counties_covered": ["Miami-Dade", "Broward"],
  "travel_distance_miles": 75,
  "violation_types": ["speeding", "inspection", "lane_violation"],
  "rate_model": "flat",
  "flat_rate_cents": 25000,
  "estimate_email": "quotes@hollowaytransportlaw.com",
  "paralegal_name": "Jane Smith",
  "paralegal_phone": "8505550199"
}
```
Writes to `attorneys/{uid}` in Firestore. Used by `team_quest.py` in AI engine for attorney matching.

_Files:_ New backend route, `frontend/src/sections/onboarding/chapter-4/ready-to-bid-view.tsx` (trigger on final submit)

---

#### P1 — High Priority (Quality of life, revenue-critical)

---

**AP-04 | Notifications Center**  
_Attorneys are notified when a claim is approved/rejected but have no UI to see those notifications._

- Bell icon in nav header with unread badge count
- `/notifications` page: list of notifications, mark as read, click → navigate to case
- Reads from `tickets/{id}/notifications` via `getAttorneyNotifications()` (backend exists; O(n) issue — see AP-07)

_Files:_ New `frontend/src/pages/notifications.tsx`, header bell component

---

**AP-05 | Calendar / Case Dates View**  
_Dashboard links to "View Calendar" but page doesn't exist. Missed court dates are a critical failure mode._

- `/calendar` page: monthly calendar view of all open cases
- Each day: case badge showing number of cases with court dates that day
- Click day → list of cases
- Color codes: red = past due, orange = <7 days, green = 14+ days
- Add to Google Calendar / iCal export button per case

_New API:_ `GET /attorney/calendar` returns attorney's open cases sorted by `court_date` with full date, location, driver name, violation

---

**AP-06 | Dashboard Real Activity + Agenda**  
_Dashboard agenda and recent activity are hardcoded placeholder data._

- Agenda: wire to `GET /attorney/calendar` — show next 5 court dates
- Recent activity: read last 10 `tickets/{id}/updates` across attorney's cases (Firestore collection group query)
- Win/loss card: wire to existing `getTicketWinLossDetails` endpoint

---

**AP-07 | Fix O(n) Notification Query**  
_`get_attorney_notifications` scans every ticket in Firestore to find notifications. Will time out at scale._

Create a top-level `attorney_notifications/{attorney_id}/items/{notif_id}` collection.  
Write to it at claim approval/rejection time instead of (or in addition to) the ticket subcollection.  
Read becomes a single indexed query.

_Files:_ `backend/.../service/utils/firebase_service.py` — update `approve_claim` and `reject_claim` to dual-write notifications

---

#### P2 — Medium Priority (Important, not blocking)

---

**AP-08 | Bid on Cases**  
_Feature 10: Rig Resolve staff sends case invitations → attorneys bid → winner notified._

New Firestore collection:
```
bids/{bid_id}
  ticket_id, attorney_id, attorney_name
  bid_amount_cents, notes, estimated_timeline
  status: "pending" | "won" | "lost" | "outbid"
  submitted_at, awarded_at
```

Backend routes:
- `POST /sendBidRequest` (staff only) — invite attorneys to bid on a case
- `POST /submitBid { ticketId, bidAmount, notes }` — attorney places bid
- `GET /myBids` — attorney sees their active bids
- `POST /awardBid { ticketId, winningAttorneyId }` — staff awards case

Frontend:
- Bid invitation appears in notification center
- `/bid/:ticketId` — case details + bid form
- `/my-bids` — list of active/won/lost bids
- Real-time outbid alert via Firestore snapshot listener

---

**AP-09 | Direct Assignment ("Thinking of You")**  
_Feature 11: Eniola sends a case to a specific attorney, bypassing claim/bid flow._

- `POST /directAssign { ticketId, attorneyId, message }` — staff route (requires custom Firebase claim `role: "reviewer"`)
- Sets `attorney_status = "Accepted"`, `attorney_id`, and `direct_assignment: true` in one write
- Attorney notified: "Eniola has selected you for this case"
- Shows "Directly Assigned" badge on case detail

---

**AP-10 | Profile Management Screen**  
_Feature 4: No screen to edit rates, coverage area, or violation types after onboarding._

- `/profile` page with editable sections for each onboarding chapter
- All fields wire to `PUT /attorney/profile/update`
- Rate structure editable: switch between flat / per-ticket / tiered at any time

---

**AP-11 | Appointment Scheduling (Feature 2)**  
_Attorneys can book a call with Eniola during onboarding._

- Embed Calendly widget on `/choose-onboarding` screen
- Pre-fill name + email from registration state
- No backend required — Calendly handles booking
- Confirmation screen shown after booking

---

**AP-12 | SMS + Email Case Update Triggers (Feature 9)**  
_Case updates should notify driver and carrier automatically._

When attorney posts an update via `updateTicketChatDetails`:
- If category ≠ "Attorney Note": trigger SMS to driver via Twilio with summary
- Email to driver + carrier contact via SendGrid
- If category = "Court Date Update": also trigger reminder scheduling (7 days before, 1 day before)

_Integration:_ Twilio (SMS), SendGrid (email), or Firebase Extensions for both  
_Files:_ New `app/services/notification_service.py` in AI engine, or backend notification hook in attorney portal

---

### Attorney Portal — Summary Checklist

| ID | Feature | Priority | Status |
|----|---------|---------|--------|
| AP-01 | Case Detail Page (view ticket, evidence, chat, request files) | P0 | ✅ Done |
| AP-02 | Fix reviewer queue reject endpoint | P0 | ✅ Done |
| AP-03 | Wire onboarding persistence to Firestore | P0 | ✅ Done |
| AP-04 | Notifications center (bell + page) | P1 | ✅ Done |
| AP-05 | Calendar / case dates view | P1 | ✅ Done |
| AP-06 | Wire dashboard agenda + activity to real data | P1 | ✅ Done |
| AP-07 | Fix O(n) notification query (top-level collection) | P1 | ✅ Done |
| AP-08 | Bid on cases (full flow) | P2 | ✅ Done |
| AP-09 | Direct assignment ("Thinking of You") | P2 | ✅ Done |
| AP-10 | Profile management screen | P2 | ✅ Done (was pre-built) |
| AP-11 | Calendly appointment scheduling embed | P2 | ✅ Done (was pre-built) |
| AP-12 | SMS + email triggers on case updates | P2 | ✅ Done |

---

## SECTION 2 — Carrier Portal

### Current State: What's Done (Old System)

| Area | Status | Keep? |
|------|--------|-------|
| React frontend (MUI + ApexCharts + React Query + Jotai) | ✅ Done | ✅ Keep — it's good |
| SMS/FMCSA dashboard screens (6 BASICS charts) | ✅ Done | ✅ Keep UI, replace backend |
| MVR 3-tab screen (Reports, Batches, CA EPN) | ✅ Done | ✅ Keep UI, replace backend |
| Driver list table + CSV export | ✅ Done | ✅ Keep |
| Driver detail page | ✅ Done | ✅ Keep + extend |
| Open tickets + submitted tickets screens | ✅ Done | ✅ Keep |
| Salesforce SOQL backend | ✅ Done | ❌ Remove entirely |
| MongoDB + JWT custom auth | ✅ Done | ❌ Replace with Firebase Auth |
| Attorney portal routes (inside carrier service) | ✅ Done | ❌ Remove (duplicate) |
| Abenity, Samba, marketing dead code | ✅ Done | ❌ Remove |

---

### Carrier Portal — Full Rebuild Scope

The carrier portal is a **backend swap with frontend extensions**. The React UI is kept and extended; Salesforce is removed and replaced with Firebase Auth + Firestore + direct FMCSA API.

#### CP-01 | Auth Migration — JWT → Firebase Auth (P0)

**Remove:** Custom JWT, bcrypt MongoDB auth, `LoginUser`/`RegisterUser` MongoDB endpoints  
**Add:** Firebase Auth (email + password, Google, Microsoft)  
**Migrate:** User accounts from MongoDB → Firebase Auth + `carriers/{uid}` Firestore doc  

Backend: Replace `get_user_data(jwt_token)` with `firebase_admin.auth.verify_id_token(id_token)`  
Frontend: Replace `apiSetUp` JWT header with Firebase `getIdToken()` — same pattern as attorney portal

---

#### CP-02 | Carrier Registration Wizard (P0)

5-step onboarding, all writes to Firestore:

| Step | Fields | Firestore Path |
|------|--------|----------------|
| 1 — Account | Name, title, phone, DOB, address | `carriers/{uid}.account_holder` |
| 2 — Company | Legal name, DBA, address, contact, type | `carriers/{uid}.company` |
| 3 — DOT | USDOT#, MC#, FMCSA auto-fill, DBA per DOT | `carriers/{uid}/dot_numbers/{dot_id}` |
| 4 — Fleet | Truck count, driver count, owner-ops, operation radius | `carriers/{uid}/dot_numbers/{dot_id}.fleet` |
| 5 — Operations | States operated, cargo types, HazMat | `carriers/{uid}/dot_numbers/{dot_id}.operations` |

FMCSA auto-fill on DOT entry: call `GET /carriers/{dot_number}` from FMCSA API, pre-fill company name, address, authority status, fleet size, HazMat flag.

---

#### CP-03 | Multi-DOT Management (P0)

- List of all DOTs under carrier account
- Add DOT → FMCSA auto-fill → confirm
- Set primary DOT (default for new driver enrollments)
- Archive DOT (history preserved)
- Click DOT → scoped view: its CSA scores, drivers, inspections, tickets

Firestore: `carriers/{uid}/dot_numbers/{dot_id}`

---

#### CP-04 | Driver Management Rebuild (P0)

Keep existing driver list UI. Replace Salesforce backend with Firestore.

**New capabilities:**
- Activate / Deactivate individual driver (weekly swap support)
- Transfer driver to different DOT with date logging
- Bulk activate/deactivate/transfer via checkbox select
- Driver `dot_associations[]` array tracks full DOT history with date ranges
- Freemium coverage toggle
- Subscription plan + paid_by setting per driver

**CSV Import:**
- Required: `first_name`, `last_name`, `cdl_number`, `cdl_state`, `cdl_class`, `dob`, `email`, `phone`
- Optional: `hire_date`, `dot_number`, `employee_id`
- Preview page shows: valid rows (green), error rows (red) with reason
- Confirm → batch write to Firestore + send enrollment SMS to drivers

Firestore: `drivers/{uid}` (existing schema, extend with `dot_associations`, `subscription_paid_by`)

---

#### CP-05 | Ticket Submission & Tracking (P0)

**Submit ticket on behalf of driver:**
1. Select driver from roster
2. Upload ticket image → AI engine `POST /api/v1/process` with `source=carrier_upload`
3. AI extracts fields → pre-fill review form
4. Carrier confirms → submitted with `attorney_status: "AI Review"`
5. Manual fallback: enter citation fields manually if image unreadable

**DataQ Challenge:**
- Select inspection from FMCSA violation list
- Form: reason, supporting docs
- Status tracking: Submitted → In Review → Accepted / Rejected
- Firestore: `dataq_challenges/{id}`

**Ticket tracking:**
- Same list/detail as attorney portal (carrier view: read-only on attorney actions)
- Carrier sees: attorney name, court date, status, updates, outcome, final fine

---

#### CP-06 | Subscription & Billing (P1)

**Three carrier billing models:**
- **Carrier pays:** Monthly Stripe invoice per active driver
- **Payroll deduction:** Carrier billed; marks drivers as deduction; exports deduction CSV to payroll
- **Driver pays:** Carrier generates discount code; driver signs up independently

**UI:**
- Subscription overview: total enrolled, monthly cost breakdown
- Per-driver plan + billing model
- Bulk plan change (select multiple → change tier)
- Payment method management (Stripe card or ACH)
- Invoice history + PDF download
- Grace period: 7 days after failed payment → `status: "paused"`

Firestore: `subscriptions/{sub_id}` linked to Stripe customer/subscription IDs

---

#### CP-07 | Fine Payment Management (P1)

Per ticket, track:
- Initial fine vs. final fine (negotiated by attorney)
- Fine due date
- Who pays: Carrier / Driver / Court direct
- Payment status: Pending / Paid / Disputed / Waived
- Carrier can pay via Stripe in portal
- Driver pays via driver app (carrier sees status update)
- "Paid externally" option: upload receipt, mark closed

Firestore: `fines/{fine_id}` linked to `tickets/{ticket_id}`

---

#### CP-08 | Document Management (P1)

**Company-level docs:**
- FMCSA operating authority, insurance certs, safety rating letters, drug consortium enrollment

**Driver-level docs:**
- CDL front/back, med cert, drug test results, MVR reports, employment agreement, citations, training certs

**Features:**
- Drag-and-drop upload → Firebase Storage → Firestore metadata
- Expiration alerts (CDL, med cert, insurance) at 90/60/30 days
- Shareable time-limited download links
- Visible-to access control: carrier only / also visible to attorney / also visible to driver
- Soft delete with audit trail

Storage paths:
- `carrier_docs/{carrier_id}/{doc_type}/{filename}`
- `driver_docs/{driver_id}/{doc_type}/{filename}`

---

#### CP-09 | FMCSA / SMS Dashboard Rebuild (P1)

Keep the existing 6-chart ApexCharts UI. Replace Salesforce backend with direct FMCSA API.

**FMCSA API endpoints to wire:**
```
GET https://mobile.fmcsa.dot.gov/qc/services/carriers/{dot}          → carrier profile
GET https://mobile.fmcsa.dot.gov/qc/services/carriers/{dot}/basics   → CSA scores + percentiles
GET https://mobile.fmcsa.dot.gov/qc/services/carriers/{dot}/inspections → inspection records
GET https://mobile.fmcsa.dot.gov/qc/services/carriers/{dot}/violations  → violation records
GET https://mobile.fmcsa.dot.gov/qc/services/carriers/{dot}/crashes  → crash data
```

**Cache strategy:**
- Cloud Scheduler job runs nightly at 2 AM
- Pulls all 5 endpoints per active carrier DOT
- Writes to `fmcsa_cache/{dot_number}` in Firestore
- All dashboard reads serve from cache (no rate limit risk)
- Force-refresh button available to carrier for on-demand pull

**New dashboard additions (didn't exist in old system):**
- CSA percentile gauges (where does carrier rank vs. national average per BASIC)
- Alert threshold line (e.g., Unsafe Driving flags at 65th percentile)
- Trend arrows: is each BASIC score improving or worsening month-over-month?

---

#### CP-10 | MVR Rebuild (P1)

Keep the 3-tab MVR UI. Replace Salesforce backend.

**MVR Vendor:** Evaluate SambaSafety (continuous monitoring — preferred for fleets) vs. CheckMVR (one-time pulls — cheaper for small fleets)

**New capabilities:**
- Continuous monitoring alerts (SambaSafety): carrier is notified when a driver's MVR changes (new violation, suspension, license status change)
- MVR results stored in Firestore + Firebase Storage (PDF)
- Parse MVR on receipt: flag suspensions, new violations, CDL class changes, endorsement changes, restrictions added
- Alert carrier immediately on any adverse MVR event

Firestore: `mvr_reports/{report_id}` → mirrors existing Salesforce MVR_Report__c structure

---

#### CP-11 | TenStreet Integration (P2)

**What it does:** When a driver is hired in TenStreet → auto-activate in Rig Resolve. Termination → auto-deactivate.

**Backend:**
- `POST /webhooks/tenstreet/:carrier_uid` — receives HMAC-signed TenStreet events
- Handles: `driver.hired`, `driver.terminated`, `driver.rehired`, `driver.dot_transfer`, `driver.updated`
- Logs all events to Firestore for carrier audit trail

**UI:**
- Settings → Integrations → TenStreet
- Enter company key + API key
- Rig Resolve generates unique webhook URL for carrier
- Test button: sends mock `driver.hired` event + shows preview
- Sync log: last 30 events with action taken

---

#### CP-12 | Workday Integration (P2)

**What it does:** Bi-directional sync with Workday HCM for enterprise carriers.

- Workday → Rig Resolve: new hires, terminations, LOA
- Rig Resolve → Workday: monthly deduction CSV export (driver ID, amount, period, plan code)

**UI:**
- Settings → Integrations → Workday
- Workday tenant URL, client ID, client secret
- Map: Workday worker type → Rig Resolve employment type
- Map: Workday cost center → DOT number
- Set deduction paycode
- Download deduction export CSV button

---

### Carrier Portal — Summary Checklist

| ID | Feature | Priority | Status |
|----|---------|---------|--------|
| CP-01 | Migrate auth to Firebase (remove JWT/MongoDB auth) | P0 | ✅ Done |
| CP-02 | Carrier registration wizard (5-step onboarding) | P0 | ✅ Done |
| CP-03 | Multi-DOT management screen | P0 | ✅ Done |
| CP-04 | Driver management rebuild (Firestore, activate/deactivate, CSV import) | P0 | ✅ Done |
| CP-05 | Ticket submission + DataQ challenge + tracking | P0 | ✅ Done |
| CP-06 | Subscription & billing (Stripe, 3 payment models) | P1 | ✅ Done |
| CP-07 | Fine payment management | P1 | ✅ Done |
| CP-08 | Document management (company + driver, expiration alerts) | P1 | ✅ Done |
| CP-09 | FMCSA/SMS dashboard (replace Salesforce with FMCSA API + cache) | P1 | ✅ Done |
| CP-10 | MVR rebuild (vendor API + continuous monitoring) | P1 | ✅ Done |
| CP-11 | TenStreet integration (webhook, auto activate/deactivate) | P2 | ✅ Done |
| CP-12 | Workday integration (roster sync + deduction export) | P2 | ✅ Done |

---

## SECTION 3 — AI Engine Changes Needed

These are changes to the existing FastAPI AI Ticket Engine needed to support attorney and carrier features.

| ID | Change | Priority |
|----|--------|---------|
| AE-01 | Add `source=carrier_upload` handling | P0 | ✅ Done |
| AE-02 | `POST /api/v1/process` accept `carrier_id` param | P0 | ✅ Done |
| AE-03 | Wire real attorney profiles into team_quest matching | P1 | ✅ Done |
| AE-04 | `POST /api/v1/decline-case` route | P1 | ✅ Done |
| AE-05 | Twilio SMS + SendGrid email on ticket status change | P1 | ✅ Done |
| AE-06 | `POST /api/v1/file-request` route | P2 | ✅ Done |
| AE-07 | Firestore scheduled backup (Cloud Scheduler → GCS) | P1 | ❌ Needs human setup (GCS bucket + Cloud Scheduler) |
| AE-08 | Composite Firestore indexes for scan_queue + training_records | P1 | ❌ Needs firestore.indexes.json deploy |
| AE-09 | `document_cache` TTL + Cloud Scheduler cleanup | P2 | ❌ Build |

---

## SECTION 4 — Infrastructure & Data Changes

| ID | Change | Priority |
|----|--------|---------|
| INF-01 | Firestore daily export to GCS (backup) | P0 | ❌ Needs human setup — GCS bucket + Cloud Scheduler |
| INF-02 | Add missing composite indexes to `firestore.indexes.json` and deploy | P0 | ❌ Needs `firebase deploy --only firestore:indexes` |
| INF-03 | FMCSA API key setup | P1 | ✅ Done — key hardcoded from registration wizard |
| INF-04 | MVR vendor contract + API credentials | P1 | ❌ Awaiting human (SambaSafety vs CheckMVR decision — Q1) |
| INF-05 | Twilio account + phone number for SMS | P1 | ✅ Code done — needs human account setup + env vars |
| INF-06 | SendGrid for transactional email | P1 | ✅ Code done — needs human account setup + env vars |
| INF-07 | Stripe webhook endpoint in AI engine | P1 | ✅ Done |
| INF-08 | Firebase Storage lifecycle rules | P2 | ❌ Needs `gsutil lifecycle set` — human setup |
| INF-09 | Carrier portal git repo initialization | P0 | ✅ Done |
| INF-10 | Firebase custom claims for reviewer/staff/admin roles | P1 | ❌ Needs human setup via Firebase Admin SDK script |
| INF-11 | Replace `cdl-local-dev` API key in Secret Manager | P0 | ❌ Needs human — rotate secret in GCP Secret Manager |

---

## SECTION 5 — Master Build Sequence

### Phase 1 — Core Gaps (Weeks 1–3)
_Things that are broken or blocking usage right now_

1. **INF-09** — Git init carrier portal
2. **INF-01** — Firestore daily backup (15 min setup, critical)
3. **INF-02** — Deploy missing Firestore indexes
4. **INF-11** — Rotate production API key
5. **AP-02** — Fix reviewer queue reject endpoint
6. **AP-01** — Case detail page (attorney's #1 need)
7. **AP-03** — Wire onboarding persistence to Firestore
8. **AE-01 + AE-02** — Carrier ticket submission support in AI engine

### Phase 2 — Attorney Portal Completion (Weeks 4–6)
_Close all attorney portal gaps_

9. **AP-04** — Notifications center
10. **AP-05** — Calendar / case dates
11. **AP-06** — Wire dashboard real data
12. **AP-07** — Fix O(n) notification query
13. **INF-05 + INF-06** — Twilio + SendGrid setup
14. **AP-12** — SMS + email case update triggers
15. **AE-03** — Wire real attorney profiles into team_quest matching
16. **INF-10** — Firebase custom claims for reviewer/staff roles

### Phase 3 — Carrier Portal Foundation (Weeks 7–10)
_New carrier portal core_

17. **CP-01** — Firebase Auth migration
18. **CP-02** — Carrier registration wizard
19. **CP-03** — Multi-DOT management
20. **CP-04** — Driver management rebuild
21. **CP-05** — Ticket submission + DataQ

### Phase 4 — Carrier Billing & Documents (Weeks 11–13)

22. **CP-06** — Subscription & billing (Stripe)
23. **CP-07** — Fine payment management
24. **CP-08** — Document management

### Phase 5 — Safety Intelligence (Weeks 14–16)

25. **INF-03** — FMCSA API key
26. **CP-09** — SMS/FMCSA dashboard rebuild (FMCSA API + Firestore cache)
27. **INF-04** — MVR vendor contract
28. **CP-10** — MVR rebuild

### Phase 6 — Attorney Portal Extensions (Weeks 17–19)

29. **AP-08** — Bid on cases
30. **AP-09** — Direct assignment
31. **AP-10** — Profile management screen
32. **AP-11** — Calendly scheduling embed
33. **AE-04** — Decline case route

### Phase 7 — Automations (Weeks 20–22)

34. **CP-11** — TenStreet integration
35. **CP-12** — Workday integration
36. **AE-05** — SMS triggers on ticket status change
37. **AE-06** — File request route

---

## Quick Reference — What to Build First

If you're starting a work session and want to know what to pick up next, in order:

```
1. Fix: Firestore backup (INF-01)                  ~1 hour
2. Fix: Reviewer queue reject endpoint (AP-02)      ~1 hour  
3. Fix: Missing Firestore indexes (INF-02)          ~30 min
4. Fix: Rotate AI engine API key (INF-11)           ~15 min
5. Build: Attorney case detail page (AP-01)         ~2–3 days
6. Build: Wire attorney onboarding to Firestore     ~4 hours
7. Build: Attorney notifications (AP-04)            ~1 day
8. Build: Attorney calendar (AP-05)                 ~1 day
9. Build: Carrier auth migration (CP-01)            ~1 day
10. Build: Carrier registration wizard (CP-02)      ~2 days
```

---

## Open Questions (Decisions Needed)

| # | Question | Needed For |
|---|---------|-----------|
| Q1 | MVR vendor: SambaSafety continuous monitoring vs. CheckMVR one-time pulls? SambaSafety is better for fleet compliance but costs more per driver. | CP-10 |
| Q2 | Which states should be attorney coverage priority? Drives onboarding outreach order. | AP-03, team_quest |
| Q3 | Carrier subscription pricing: What are the Silver/Gold/Platinum per-driver monthly rates? | CP-06 |
| Q4 | Fine payment: Does Rig Resolve take a processing fee when paying a fine through the portal, or is it pass-through? | CP-07 |
| Q5 | TenStreet: Do you have an existing TenStreet account we can test with, or is this net-new? | CP-11 |
| Q6 | Reviewer role: Who currently has reviewer access to the attorney portal queue, and how should that be gated (custom Firebase claims vs. hardcoded email list)? | INF-10, AP-09 |
| Q7 | Payroll deduction: Does Rig Resolve need to generate pay stub entries, or does the carrier handle that internally after receiving the deduction CSV? | CP-12 |

---

_This document is the single source of truth for what's built, what's planned, and what's next. Update it as items ship._
