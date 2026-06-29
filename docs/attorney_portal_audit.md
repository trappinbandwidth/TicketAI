# Attorney Portal — Full Audit & Feature Build-Out Plan

**Last Updated:** 2026-06-28  
**Portal URL:** https://rigresolve-attorney.web.app  
**Backend URL:** https://attorney-portal-626128667800.us-central1.run.app  
**Stack:** Flask + Firestore backend · React 18 + TypeScript + Tailwind frontend · Firebase Auth

---

## What Exists Today

### Authentication ✅ COMPLETE
- Email/password via Firebase Auth
- Google OAuth, Microsoft OAuth, Apple OAuth
- Phone + OTP flow (mobile)
- Backend verifies Firebase ID tokens on every route
- Attorney registration flow (`registerAttorneyUser`)

### Backend Routes (All Firestore-backed)
Base: `/RigResolveAttorneyService/api/v1/`

| Route | Method | What It Does |
|-------|--------|-------------|
| `RegisterAttorneyUser` | POST | Create Firebase Auth user + Firestore profile |
| `LoginUser` | POST | Email/password login |
| `GoogleLogin` / `MicrosoftLogin` / `AppleLogin` | POST | Social auth |
| `SendOTP` / `VerifyOTP` / `VerifyEmailOTP` | POST | Phone/email OTP |
| `GetUserDetails` | GET | Logged-in attorney profile |
| `UpdateUserDetails` | POST | Update profile |
| `getTotalTicket` | GET | Count all tickets assigned to attorney |
| `getOpenTickets` | GET | Open (not closed) tickets |
| `getTicketsWating` | GET | Waiting status + past follow-up date |
| `getPostDueTickets` | GET | Past court date, still open |
| `getUpcomingTicket` | GET | Court dates in next 14 days |
| `getTicketWinLossDetails` | GET | Win/loss outcomes (closed tickets) |
| `getRevenue` | GET | Revenue by MONTH or YEAR |
| `getUnprocessedPayments` | GET | Unpaid invoices |
| `getFieldUpdateHistory/<id>` | GET | Audit trail for a ticket |
| `getRelatedPayment/<id>` | GET | Payments linked to a ticket |
| `getTicketDetailById/<id>` | GET | Full ticket record + unreviewed updates |
| `getTicketChatDetailById/<id>` | GET | Chat/note history for a ticket |
| `getTicketUpdateCategories` | GET | Hardcoded category list |
| `getAvailableCases` | GET | Tickets open for claiming (not Accepted/Closed/AI Review/Rejected) |
| `getReviewerQueue` | GET | Tickets in "Pending Review" with claimants |
| `updateTicketDetails` | POST | Update ticket fields + write audit trail |
| `updateTicketChatDetails` | POST | Add chat message/note |
| `uploadTicketUpdateDocument` | POST | Upload file to S3 |
| `claimTicket` | POST | Soft-claim: appends to claimants[], sets status "Pending Review" |
| `approveClaim` | POST | Reviewer picks winner, writes notifications to all claimants |

### Firestore Collections

| Collection | Purpose |
|-----------|---------|
| `tickets` | All case records — attorney_id, attorney_status, court_date, claimants[], violation data |
| `tickets/{id}/updates` | Chat messages and case notes |
| `tickets/{id}/field_history` | Audit trail of every field change |
| `tickets/{id}/notifications` | Win/lose notifications to claimants |
| `payments` | Attorney payment records |
| `cards` | Emburse virtual card data |

### Frontend Screens

| Screen | Route | Status |
|--------|-------|--------|
| Sign In | `/sign-in` | ✅ Complete (all auth methods) |
| Choose Onboarding | `/choose-onboarding` | ✅ Complete |
| Onboarding Details | `/onboarding-details` | ✅ Complete |
| Onboarding OTP | `/onboarding-otp` | ✅ Complete |
| Dashboard | `/dashboard` | ✅ Complete (metrics cards, agenda, activity — some dummy data) |
| Available Cases | `/available-cases` | ✅ Complete (search + claim button) |
| Reviewer Queue | `/reviewer-queue` | ✅ Complete (approve/reject with region filter) |
| Onboarding Ch. 1 | `/confirm-contact`, `/firm-details` | ✅ Complete |
| Onboarding Ch. 2 | `/credentials`, `/credentials-other-states` | ✅ Complete (doc upload not wired) |
| Onboarding Ch. 3 | `/coverage-area` | ✅ Complete |
| Onboarding Ch. 4 | `/rates`, `/rates-flat`, `/rates-per-ticket`, `/rates-tiered`, `/ready-to-bid` | ✅ Complete |

---

## Gap Analysis — What's Missing

### Backend Gaps
| Gap | Impact |
|-----|--------|
| No `RejectTicket` route in `post_methods.py` | Reviewer Queue reject button silently fails |
| No onboarding data persistence endpoint | Attorney profile setup data lost on refresh |
| `get_attorney_notifications` is O(n) full collection scan | Will timeout at scale |
| No "bid" / "Thinking of You" case assignment route | Features 10 & 11 not implementable |
| No case acceptance/decline with reason endpoint | Feature 6 decline flow missing |
| No file request endpoint | Feature 8 missing entirely |
| No SMS integration for case updates | Feature 9 SMS path missing |
| No appointment scheduling endpoint | Feature 2 missing |

### Frontend Gaps
| Gap | Route Needed | Priority |
|-----|-------------|---------|
| Case Detail page (view ticket, evidence, contacts, chat) | `/cases/:id` | P0 |
| Chat / notes UI on case detail | Within `/cases/:id` | P0 |
| Notifications center (approved/rejected badges) | `/notifications` | P1 |
| Payment & earnings detail page | `/earnings` | P1 |
| Calendar / case dates view | `/calendar` | P1 |
| Win/loss report | `/performance` | P2 |
| Field update history viewer | Within `/cases/:id` | P2 |
| Document upload UI | Within `/cases/:id` | P2 |
| File request UI | Within `/cases/:id` | P2 |

---

## Feature Build-Out Plan (Per Your 11 Features)

### Feature 1 — Auth Signup / Self-Registration ⚡ PARTIALLY DONE

**What exists:** Name, email, phone — 4-chapter onboarding collects bar #, firm, coverage area, rates.

**What's missing:**
- PII fields (DOB, address) not in forms
- Firm address not saved to Firestore yet
- Bar number + state license saved in forms but no Firestore write wired
- Counties covered, travel distance — form exists but not persisted
- Violation types covered (Speeding, DUI, Inspection, Lane Violation) — not in forms
- Fees per violation / flat rate / tiered — forms exist but Firestore write missing
- Paralegal/assistant contact for price quotes — not in forms
- Email for estimates — not in forms

**Build:** Wire onboarding `POST /SaveAttorneyProfile` that writes a complete `attorneys/{uid}` Firestore doc with all fields on Ch. 4 completion.

---

### Feature 2 — Schedule Appointment to Register ❌ NOT STARTED

Attorney can book a call with Eniola before/during registration.

**Build:**
- Embed Calendly widget on onboarding select screen (`/choose-onboarding`)
- No backend needed — Calendly handles scheduling
- Pre-fill email/name from form state
- Show confirmation screen after booking

---

### Feature 3 — Auth Sign In ✅ COMPLETE

Email/password + Google Auth both work. Microsoft + Apple also implemented.

---

### Feature 4 — Profile Management ⚡ PARTIAL

**What exists:** `UpdateUserDetails` route, basic profile form.

**What's missing:**
- No screen to edit coverage area after onboarding
- No screen to update rates after onboarding
- No screen to update violation types, counties, travel distance
- No screen to update paralegal contact or estimate email

**Build:** `/profile` page with sections for each onboarding chapter, all wired to Firestore update.

---

### Feature 5 — KPI Dashboard ⚡ PARTIAL

**What exists:** Active cases, open tickets, monthly revenue, waiting count — all from real Firestore data.

**What's missing:**
- Agenda items are dummy data (hardcoded Garcia, Williams)
- Recent activity is dummy data
- No win rate displayed (backend route exists)
- No breakdown by violation type or state
- No earnings trend chart

**Build:** Wire `GetTicketWinLossRate`, real upcoming cases for agenda, real case activity feed from `tickets/{id}/updates`.

---

### Feature 6 — My Cases ❌ MISSING FRONTEND (backend ready)

This is the biggest gap. Backend routes exist; no page to consume them.

**Must build `/cases` list and `/cases/:id` detail page with:**
- Ticket fields: violation, citation, court info, driver info, contact info
- Evidence tab: documents uploaded to case
- Statement tab: AI-generated summary from ticket scan
- Case value: calculated from attorney's fee structure × violation type
- Accept / Decline actions with:
  - Accept → calls `claimTicket` flow
  - Decline → requires reason (new `POST /declineCase` endpoint needed)
- Case status banner with next steps
- Update Rig Resolve section (feeds driver + carrier status)
- "Keep driver off attorney back" — contact info visibility toggle

---

### Feature 7 — Case Dates ❌ MISSING

**Build:**
- Calendar view at `/calendar` showing all court dates for attorney's open cases
- Court date, driver name, violation, city/state per entry
- Color-coded: red = past due, yellow = within 7 days, green = 14+ days
- Email + SMS reminder integration (send reminder 7 days before, 1 day before)
- Driver reminder also triggered (via Driver Concierge in AI engine)

**Backend:** Add `GET /calendar` that returns attorney's open cases ordered by court_date with ISO datetime, location, driver name, violation.

---

### Feature 8 — Request Files ❌ NOT STARTED

Attorney needs to request additional documents from driver or Rig Resolve staff.

**Build:**
- "Request File" button on case detail page
- Modal: file type (CDL front/back, insurance card, police report, witness statement, other), notes
- `POST /requestFile { ticketId, fileType, notes }` → writes to `tickets/{id}/file_requests/`
- Triggers email to driver + account manager via Driver Concierge
- File request appears in case timeline with status (Requested → Received)

---

### Feature 9 — Case Updates ❌ PARTIAL

**What exists:** Backend `updateTicketChatDetails` route works. No frontend form yet.

**Build:**
- Quick update bar on case detail: category dropdown + text + submit
- Categories: Court Date Update, Status Update, Document Submitted, Resolution Update, Payment Update, Attorney Note, Other
- SMS path: `POST /updateTicketChatDetails` triggers SMS to driver via Twilio when category is not "Attorney Note"
- Email path: same trigger, sends case update email template
- Push notification: via Firebase Cloud Messaging if driver app is installed
- **No roadblocks rule:** One-tap predefined updates ("Hearing rescheduled", "Waiting on court", "Matter resolved") + free text

---

### Feature 10 — Bid on Cases ❌ NOT STARTED

Rig Resolve sends cases matching attorney profile → attorneys bid → winner notified.

**Build:**

**Backend:**
- `POST /sendBidRequest { ticketId, attorneyIds[] }` — Rig Resolve staff sends bid invitations
- `POST /submitBid { ticketId, bidAmount, notes }` — Attorney submits bid
- `GET /myBids` — Attorney sees all active bids and their status
- `POST /awardBid { ticketId, winningAttorneyId }` — Staff awards case
- Auto-notify all bidders: winner gets "You won", others get "You are no longer lowest bidder"

**Frontend:**
- Bid invitations appear in notification center
- `/bid/:ticketId` page: case details + bid form (amount, notes, estimated timeline)
- `/my-bids` list: active, won, lost
- Real-time outbid alert: Jotai atom updated via Firestore snapshot listener on `bids/{id}`

**Firestore schema:**
```
bids/{bidId}
  ticket_id, attorney_id, attorney_name
  bid_amount, notes, status (pending/won/lost/outbid)
  submitted_at, awarded_at
```

---

### Feature 11 — Thinking of You (Direct Assignment) ❌ NOT STARTED

Eniola assigns a case directly to a specific attorney without a bidding/claiming process.

**Build:**
- `POST /directAssign { ticketId, attorneyId, message }` — Staff-only route (requires reviewer/admin claim on Firebase custom claims)
- Sets `attorney_status = "Accepted"`, `attorney_id = attorneyId` immediately
- Sends personalized notification to attorney: "Eniola has selected you for this case: [details]"
- Attorney sees case in `/cases` with "Directly Assigned" badge
- No claim or approval step; attorney can still decline with a reason

---

## Recommended Build Sequence

| Sprint | Features | Deliverable |
|--------|---------|------------|
| 1 | F6 case list + detail page (view only) | Attorney can see their cases + all ticket info |
| 1 | F9 quick update bar + chat UI | Attorney can update cases from detail page |
| 2 | F6 accept/decline + F5 real activity feed | Cases flow from claim → accept → active |
| 2 | Notifications center + F7 calendar | Attorney never misses a date |
| 3 | F8 file request + document upload UI | Complete document workflow |
| 3 | F1 onboarding persistence + F4 profile edit | Attorney can update rates, coverage, info |
| 4 | F10 bid system | Bid flow end-to-end |
| 4 | F11 direct assignment | Eniola's "Thinking of You" feature |
| 5 | F2 appointment scheduling (Calendly embed) | Pre-registration calls |
| 5 | F9 SMS/email triggers | Twilio + SendGrid wired to case updates |
