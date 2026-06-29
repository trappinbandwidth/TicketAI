# Carrier Portal 2.0 — Product Requirements Document

**Last Updated:** 2026-06-28  
**Status:** Planning  
**Stack:** Firebase Auth · Firestore · Firebase Storage · React 18 + TypeScript + MUI · FastAPI or Flask backend · Cloud Run

---

## Overview

The Carrier Portal is a fleet compliance + legal defense command center for trucking companies. Carriers enroll their drivers into Rig Resolve coverage, manage their DOT compliance posture, submit and track traffic citations, and handle subscription billing. Some carriers pay for drivers; others use payroll deduction or pass the cost directly to drivers.

---

## Feature 1 — Self-Registration & Authentication

### 1A. Auth Methods
- Email + Password
- Google OAuth
- Microsoft / Microsoft Teams SSO
- All three must be wired to **Firebase Auth** (same as attorney portal — single IAM across all of Rig Resolve)

### 1B. Registration Flow
**Step 1 — Create Account**
- Email, password (confirm), first name, last name
- OR Google/Microsoft SSO (pulls name + email automatically)
- Phone number (required — used for OTP and case updates)
- Accept Terms of Service + Privacy Policy

**Step 2 — Verify Email / OTP**
- Email link or SMS OTP (6-digit)
- Cannot proceed to company setup until verified

**Step 3 — Account Holder PII**
- Legal first + last name
- Title / role at company (Owner, Fleet Manager, Safety Manager, Dispatch, Other)
- Direct phone
- Direct email
- Mailing address (street, city, state, zip)
- Date of birth (used for identity verification if disputed billing arises)

**Step 4 → Company Info** (see Feature 2)

### Firestore Schema
```
carriers/{uid}
  auth_uid (Firebase uid)
  account_holder {
    first_name, last_name, title, phone, email
    address { street, city, state, zip }
    dob
  }
  auth_methods: ["email", "google", "microsoft"]
  email_verified: bool
  status: "pending_setup" | "active" | "suspended" | "cancelled"
  created_at, updated_at
```

### Backend Routes
| Route | Method | Purpose |
|-------|--------|---------|
| `POST /carriers/register` | POST | Create Firebase Auth user + Firestore doc stub |
| `POST /carriers/verify-email` | POST | Confirm email OTP |
| `GET /carriers/me` | GET | Return carrier profile |

---

## Feature 2 — Company Information

### Fields
- **Legal Company Name** (as filed with FMCSA)
- **DBA Name(s)** — carriers may have one or more doing-business-as names
- **Company Address** (street, city, state, zip)
- **Mailing Address** (if different)
- **Main Company Phone**
- **Main Company Email**
- **Primary Point of Contact** (may be same as account holder or different person):
  - Name, title, direct phone, direct email
- **Emergency / After-Hours Contact** (for critical case updates)
- **Company Website** (optional)
- **Type of Carrier:**
  - For-Hire, Private, Exempt, Broker, Owner-Operator (sole proprietor)
- **Years in Business**
- **Number of Terminals / Locations** (for multi-terminal fleets)

### Firestore Schema
```
carriers/{uid}
  company {
    legal_name, dba_names: []
    address { street, city, state, zip }
    mailing_address { ... }
    phone, email, website
    contact { name, title, phone, email }
    emergency_contact { name, phone, email }
    carrier_type: "for_hire" | "private" | "exempt" | "broker" | "owner_operator"
    years_in_business
    terminal_count
  }
```

---

## Feature 3 — DOT Registration & Multi-DOT Support

### Core Problem
Many carriers own multiple companies or DOT numbers and rotate drivers between them. The portal must support:
- One carrier account → many DOT numbers
- Drivers can be associated with one or more DOTs at any time
- Tickets are filed under the correct DOT at time of violation

### DOT Profile Fields (per DOT number)
- **USDOT Number** (required)
- **MC Number** (if applicable — interstate carriers)
- **State DOT / Intrastate number** (if applicable)
- **DBA Name** tied to this DOT (may differ from parent company)
- **Legal entity name** (LLC, Inc., Sole Proprietor, etc.)
- **EIN / Tax ID**
- **Operating authority status** (active, revoked, suspended)
- **FMCSA registered address** (may differ from company HQ)
- **Hazmat certification** (Y/N)
- **Insurance on file** (Y/N, expiration date)
- **Operations type:** Local, Regional, OTR, Dedicated
- **Fleet type:** Truckload, LTL, Intermodal, Tanker, Flatbed, Reefer, HazMat, Mixed

### FMCSA Auto-Fill
When a carrier enters a USDOT number:
1. Call FMCSA API `GET /carriers/{dot_number}`
2. Pre-fill: company name, address, authority status, insurance status, fleet size, HazMat flag
3. Carrier confirms or corrects — they own the record

### Multi-DOT Relationships
```
carriers/{carrier_uid}/dot_numbers/{dot_id}
  dot_number (USDOT)
  mc_number
  dba_name
  legal_name
  ein
  status: "active" | "inactive"
  authority_status (from FMCSA)
  is_primary: bool
  hazmat_certified: bool
  fmcsa_address { ... }
  operations_type
  fleet_type
  added_at
```

### UI: DOT Management Screen
- List of all DOTs under this carrier account
- Add DOT button → enter DOT # → FMCSA auto-fill → confirm
- Set primary DOT (default for new driver enrollments)
- Archive a DOT (keeps history, hides from active view)
- Click DOT → view its CSA scores, inspections, drivers assigned to it

---

## Feature 4 — Fleet Information

### Per DOT Number
- **Total power units** (trucks) — from FMCSA auto-fill, carrier can adjust
- **Total drivers** (CDL holders on payroll)
- **Owner-operators** (1099 drivers — have their own authority)
- **Leased drivers** (third-party lease arrangements)
- **Trailers owned** (optional)

### Operational Profile (drives attorney matching + pricing)
- **Operation radius:**
  - Local (within 100 miles of terminal)
  - Regional (100–500 miles)
  - OTR / Long-haul (500+ miles, multi-state)
  - Mixed (some local, some OTR)
- **Primary terminal state(s)**
- **States regularly operated in** (multi-select, see Feature 5)
- **Average miles per week per driver**
- **CDL classes in fleet:** A, B, C
- **Common endorsements:** HazMat (H), Tanker (N), Doubles/Triples (T), Passenger (P), School Bus (S)

### Firestore Schema
```
carriers/{uid}/dot_numbers/{dot_id}
  fleet {
    power_units, total_drivers, owner_operators, leased_drivers, trailers
    operation_radius: "local" | "regional" | "otr" | "mixed"
    primary_states: ["TX", "OK", "NM"]
    avg_miles_per_week
    cdl_classes: ["A", "B"]
    endorsements: ["H", "N", "T"]
  }
```

---

## Feature 5 — Operating States & Cargo

### States Operated In
- Multi-select of all 50 states (+ DC)
- Tag each state as: **Primary** (frequent) or **Occasional** (rare)
- This feeds attorney matching — we need attorneys in the states the fleet operates
- Alert carrier if they operate in a state where we have no attorney coverage

### Cargo Profile
- **Commodity types** (multi-select):
  - General Freight
  - Refrigerated Food
  - Livestock
  - Grain / Farm Supplies
  - Coal / Coke
  - Building Materials
  - Logs / Lumber
  - Machinery / Large Objects
  - Fresh Produce
  - Chemicals
  - Commodities requiring HazMat placards (opens HazMat sub-section)
  - Passengers (if applicable)
  - Other (free text)

- **HazMat details** (if applicable):
  - HazMat classes regularly transported (1–9)
  - Placard types
  - HazMat permit state(s)
  - Emergency contact (CHEMTREC or equivalent)

### Firestore Schema
```
carriers/{uid}/dot_numbers/{dot_id}
  operations {
    states_operated: [{ state: "TX", frequency: "primary" }, ...]
    cargo_types: ["general_freight", "refrigerated_food", ...]
    hazmat: bool
    hazmat_classes: ["1", "3", "8"]
    hazmat_permit_states: ["TX", "LA"]
  }
```

---

## Feature 6 — Driver Registration & Management

### Driver Enrollment Models
Three ways a driver gets into the system:

**A. Carrier-Sponsored (Carrier pays)**  
Carrier adds driver, selects plan, driver is enrolled. Driver may or may not have a portal login.

**B. CSV Bulk Upload**  
Carrier uploads a CSV with driver roster. System imports, matches/creates driver records, sends enrollment invites.

**C. Freemium / Self-Signup with Carrier Code**  
Carrier gets a referral code. Driver signs up independently in the driver app, enters carrier code, gets discounted or free coverage per the carrier's subscription agreement.

### CSV Upload Spec
Required columns: `first_name`, `last_name`, `cdl_number`, `cdl_state`, `cdl_class`, `dob`, `email`, `phone`  
Optional: `hire_date`, `dot_number` (for multi-DOT carriers), `employee_id`

- System validates each row: checks for duplicate CDL numbers, invalid states, missing required fields
- Shows import preview with error rows flagged before confirming
- Successful imports → driver profiles created in Firestore, enrollment invite SMS/email sent

### Per-Driver Profile
```
drivers/{driver_uid}
  carrier_id, dot_number_id
  first_name, last_name
  cdl_number, cdl_state, cdl_class
  cdl_expiration, cdl_restrictions, cdl_endorsements
  med_cert_expiration
  dob, ssn_last4 (for identity, encrypted at rest)
  email, phone
  hire_date
  employee_id (carrier's internal ID)
  employment_type: "employee" | "owner_operator" | "leased"
  status: "active" | "inactive" | "suspended"
  subscription_status: "active" | "freemium" | "paused" | "cancelled"
  subscription_plan: "basic" | "silver" | "gold" | "platinum"
  subscription_paid_by: "carrier" | "driver" | "payroll_deduction"
  dot_associations: [{ dot_id, from_date, to_date, active: bool }]
  created_at, updated_at
```

### Driver Activation / Deactivation

**The weekly swap problem:** Drivers rotate between DOTs week-to-week. The portal must handle:
- **Activate** a driver: flip `status = "active"`, resume their subscription coverage
- **Deactivate** a driver: flip `status = "inactive"`, pause subscription billing
- **Transfer to different DOT:** Change `dot_number_id`, log in `dot_associations[]` with from/to dates
- **Bulk activate/deactivate:** Checkbox select multiple drivers → bulk action

**Deactivation rules:**
- Deactivating a driver does not cancel open tickets — cases already in flight continue
- Billing pauses from the deactivation date (pro-rated)
- Driver's history is preserved and accessible to carrier
- Driver can be reactivated at any time

### UI: Driver Management Screen

**List View:**
- Table columns: Name, CDL#, CDL State, Class, Expiration, Status, Plan, DOT, Last Active
- Filter by: DOT, status (active/inactive), plan, state
- Sort by: any column
- Search: name, CDL#, email, phone
- Bulk select → Activate / Deactivate / Transfer DOT / Export CSV

**Driver Detail Drawer:**
- Profile: all fields above, edit button
- CDL status: expiration alert if <90 days
- Med cert: expiration alert if <90 days
- Subscription: plan, paid by, status, next billing date
- DOT history: which DOTs driver has been under, date ranges
- Open tickets: linked to `tickets/` collection
- Closed tickets: outcomes, final fines
- MVR: last run date, status, alerts
- Documents: uploaded files for this driver

---

## Feature 7 — Ticket Submission & Management

### Ticket Submission
Carriers can submit on behalf of a driver:
1. Select driver from roster (or add ad-hoc for non-enrolled drivers)
2. Upload ticket image(s) → AI engine scans and extracts all fields
3. AI pre-fills form; carrier reviews and corrects
4. Submit → ticket enters `attorney_status: "AI Review"` queue for Rig Resolve staff
5. Once approved → `attorney_status: "New"` → attorneys can claim

**Manual data entry fallback** (if ticket image is unreadable):
- Carrier enters: citation number, violation, date, state, county, city, court date, fine amount
- Flags it as "manually entered" for extra review

### DataQ Challenge Request
For FMCSA inspection violations that the driver or carrier believes are inaccurate:
1. Carrier selects an inspection from the FMCSA violations list
2. Clicks "Challenge this Inspection"
3. Form: reason for challenge, supporting documentation upload
4. Submits to Rig Resolve → staff processes DataQ filing
5. Carrier tracks status: Submitted → In Review → Accepted / Rejected

**Firestore:**
```
dataq_challenges/{challenge_id}
  carrier_id, dot_id, driver_id
  inspection_id (FMCSA inspection reference)
  inspection_date, state, violation_description
  reason_for_challenge
  documents: [storage_urls]
  status: "submitted" | "in_review" | "accepted" | "rejected"
  submitted_at, resolved_at
  fmcsa_case_number (filled in by staff)
```

### Ticket Tracking (Carrier View)
Carrier sees all tickets across all drivers and DOTs:
- Status: AI Review → New → Accepted → Closed
- Attorney name and contact (once assigned)
- Court date
- Fine amount (initial vs. final)
- Outcome: Dismissed, Reduced, No Change, Guilty
- Win/Loss

**Filters:** Driver, DOT, status, state, violation type, date range  
**Actions:** View details, view AI scan, view evidence, view case updates

### Case Updates (Carrier Visibility)
Carrier receives:
- Email notification when attorney accepts case
- SMS notification when court date is set or changed
- Email notification when case is resolved (outcome + final fine)
- Can view case chat/notes from attorney in portal (read-only)

---

## Feature 8 — Driver Subscription Management

### Payment Models

**Model A — Carrier Pays (Full)**
- Carrier is billed monthly for all active enrolled drivers
- Rate: per driver, per month (varies by plan tier)
- Invoice sent at start of each billing period
- Carrier pays via Stripe (card on file or ACH)

**Model B — Payroll Deduction**
- Carrier deducts premium from driver paycheck
- Driver's subscription is active as long as carrier deducts
- Carrier is still billed by Rig Resolve; the mechanism for recovering cost is internal to carrier
- Portal shows: amount deducted per driver, per period

**Model C — Driver Pays (with Carrier Discount)**
- Carrier has a group discount code
- Driver signs up independently in driver app using carrier's code
- Driver's credit card is billed directly
- Carrier can see which of their drivers are enrolled but doesn't control billing

**Model D — Mixed**
- Carrier may use different models for different driver segments (employees vs. owner-operators)
- Per-driver setting: `subscription_paid_by: "carrier" | "driver" | "payroll_deduction"`

### Plan Tiers (from existing pricing data)
- **Freemium** — Basic coverage, limited attorney matching
- **Silver** — Standard CDL defense
- **Gold** — Enhanced coverage, priority attorney matching
- **Platinum** — Full coverage, preferred attorneys, proactive FMCSA monitoring

### Subscription Management UI
- Overview: total enrolled drivers, total monthly cost, payment model breakdown
- Per-driver row: plan, paid by, status, next billing date, pause/cancel button
- Bulk upgrade/downgrade selected drivers
- Add payment method (Stripe): card or ACH bank account
- Invoice history: download PDF invoices
- Grace period handling: if payment fails, 7-day grace → driver status moves to "paused"

### Firestore Schema
```
subscriptions/{sub_id}
  carrier_id, driver_id
  plan: "freemium" | "silver" | "gold" | "platinum"
  paid_by: "carrier" | "driver" | "payroll_deduction"
  status: "active" | "paused" | "cancelled" | "grace_period"
  monthly_rate (cents)
  billing_day (day of month)
  stripe_subscription_id
  stripe_customer_id
  started_at, paused_at, cancelled_at, next_billing_date
```

---

## Feature 9 — Fine Payment Management

### The Problem
When a case is resolved with a guilty verdict or reduced plea, a fine is owed. Who pays depends on the carrier's agreement with the driver.

### Payment Scenarios

**Scenario A — Carrier Pays Fine**
- Rig Resolve sends invoice to carrier for fine amount
- Carrier pays via portal (Stripe) or ACH
- Payment confirmation sent to attorney to confirm with court

**Scenario B — Driver Pays Fine**
- Driver is notified of fine amount via driver app
- Driver pays via driver app (Stripe)
- Carrier can see status: "Driver payment pending", "Driver paid"

**Scenario C — Court Payment (carrier or driver pays court directly)**
- Fine paid directly to court, outside of Rig Resolve
- Carrier or attorney marks as "Paid Externally" in portal
- Receipt uploaded as document

### Fine Tracking UI
Per case/ticket:
- Initial fine (what was on the ticket)
- Negotiated/final fine (outcome of attorney's work)
- Fine due date
- Payment status: Pending / Paid / Disputed / Waived
- Who pays: Carrier / Driver / Court Direct
- Payment confirmation receipt

### Firestore Schema
```
fines/{fine_id}
  ticket_id, carrier_id, driver_id
  initial_fine_cents, final_fine_cents
  due_date
  paid_by: "carrier" | "driver" | "external"
  status: "pending" | "paid" | "disputed" | "waived"
  stripe_payment_intent_id (if paid via portal)
  paid_at, receipt_url
```

---

## Feature 10 — Document Management

### Scope
Documents at two levels:
1. **Company-level documents** (apply to entire carrier account)
2. **Driver-level documents** (tied to a specific driver)

### Company Documents
- FMCSA operating authority certificate
- Insurance certificates (liability, cargo)
- DOT safety rating letter
- Drug & alcohol consortium enrollment
- Clearinghouse registration
- Custom uploads (labeled by carrier)

### Driver Documents
- CDL (front + back)
- Medical certificate
- Drug test results (pre-employment, random, post-accident)
- Clearinghouse query results
- Employment/lease agreement
- MVR report (auto-stored when pulled)
- Accident report
- Training certificates
- Citation copies
- Attorney correspondence

### Document Upload
- Drag-and-drop or file picker
- Accepted types: PDF, JPG, PNG, DOCX
- Max file size: 25 MB per file
- Stored in Firebase Storage at:
  - `carrier_docs/{carrier_id}/{doc_type}/{filename}`
  - `driver_docs/{driver_id}/{doc_type}/{filename}`
- Metadata in Firestore:
  ```
  documents/{doc_id}
    owner_type: "carrier" | "driver"
    owner_id: carrier_id or driver_id
    carrier_id
    doc_type (e.g., "cdl", "insurance", "mvr_report")
    filename, storage_path, content_type, size_bytes
    label (user-provided description)
    expiration_date (optional — for CDL, med cert, insurance)
    uploaded_by, uploaded_at
    visible_to: ["carrier", "attorney", "driver"]  (access control)
  ```

### Document Expiration Alerts
- CDL expiration: alert at 90 days, 60 days, 30 days, on expiration
- Med cert expiration: same cadence
- Insurance expiration: same cadence
- Alert appears in portal + sent via email

### UI
- Folder-style view: Company Docs, then per-driver folders
- Filter by: doc type, driver, DOT, expiration status
- Download, rename, delete (soft delete — keeps audit trail)
- Share link (time-limited, for sending to attorney or court)

---

## Feature 11 — Automations & Integrations

### 11A. TenStreet Integration

**What TenStreet is:** Driver applicant tracking and onboarding system used by many carriers.

**Integration goal:** When a driver is hired and onboarded in TenStreet, they are automatically added to Rig Resolve with the correct plan and DOT association. When a driver is terminated in TenStreet, they are automatically deactivated.

**Integration type:** Webhook receiver (TenStreet sends events to Rig Resolve)

**Events to handle:**

| TenStreet Event | Rig Resolve Action |
|----------------|-------------------|
| `driver.hired` | Create driver profile, enroll with carrier's default plan, send welcome SMS |
| `driver.terminated` | Deactivate driver, pause subscription billing |
| `driver.rehired` | Reactivate driver, resume subscription |
| `driver.dot_transfer` | Update driver's DOT association |
| `driver.updated` | Sync CDL number, expiration, contact info |

**Setup UI in Carrier Portal:**
1. Carrier navigates to Settings → Integrations → TenStreet
2. Enters TenStreet company key + API key
3. Rig Resolve generates a webhook URL for the carrier
4. Carrier configures TenStreet to send events to that URL
5. Test button: sends a mock `driver.hired` event and shows what Rig Resolve would do

**Firestore:**
```
integrations/{carrier_id}/tenstreet
  enabled: bool
  company_key, api_key (encrypted)
  webhook_url (unique per carrier)
  default_plan: "silver"
  default_paid_by: "carrier"
  last_sync_at
  sync_log: [{ event, driver_id, action_taken, timestamp }]
```

### 11B. Workday Integration

**What Workday is:** HR and payroll system used by larger trucking companies.

**Integration goal:** Sync Workday's active employee roster with Rig Resolve driver list. Payroll deduction amounts are exported back to Workday for automatic deduction processing.

**Direction:** Bi-directional
- Workday → Rig Resolve: New hires, terminations, LOA (leave of absence)
- Rig Resolve → Workday: Deduction amounts per driver per pay period

**Integration type:** Workday REST API (RAAS reports or Integration System)

**Events/syncs:**

| Direction | Event | Action |
|-----------|-------|--------|
| Workday → RR | Worker hire | Create/activate driver, set `paid_by: "payroll_deduction"` |
| Workday → RR | Worker terminate | Deactivate driver |
| Workday → RR | Worker LOA | Pause subscription |
| RR → Workday | Monthly deduction export | CSV or API call with driver ID + deduction amount + period |

**Setup UI:**
1. Settings → Integrations → Workday
2. Enter Workday tenant URL, client ID, client secret
3. Map Workday worker type → Rig Resolve employment type
4. Map Workday cost center / department → DOT number
5. Set deduction paycode (Workday-side earning code for Rig Resolve deductions)
6. Set sync frequency (real-time webhook vs. nightly batch)

**Deduction export format:**
```csv
workday_worker_id, driver_name, period_start, period_end, deduction_amount, plan_code
W-12345, John Smith, 2026-06-01, 2026-06-15, 29.99, SILVER
```

### 11C. Future Integrations (Phase 2)

| Integration | Purpose | Priority |
|------------|---------|---------|
| KeepTruckin / Motive ELD | HOS violations, location data | P2 |
| Samsara ELD | HOS violations, driver behavior scores | P2 |
| Clearinghouse API | Auto-pull drug/alcohol violation queries | P2 |
| SambaSafety | Continuous MVR monitoring alerts | P1 |
| AtoB / Trucking payment cards | Fine payment via fleet cards | P3 |
| DAT / Loadboard | Owner-operator identification | P3 |

---

## Full Screen Inventory

| Screen | Route | Priority |
|--------|-------|---------|
| Sign Up | `/register` | P0 |
| Verify Email/OTP | `/verify` | P0 |
| Account Holder PII | `/setup/account` | P0 |
| Company Info | `/setup/company` | P0 |
| DOT Registration | `/setup/dot` | P0 |
| Fleet Info | `/setup/fleet` | P0 |
| Operating States & Cargo | `/setup/operations` | P0 |
| Sign In | `/sign-in` | P0 |
| Dashboard Home | `/dashboard` | P0 |
| DOT Management | `/dot` | P0 |
| Driver List | `/drivers` | P0 |
| Add Driver (single) | `/drivers/add` | P0 |
| CSV Upload | `/drivers/import` | P0 |
| Driver Detail | `/drivers/:id` | P0 |
| Open Tickets | `/tickets` | P0 |
| Ticket Detail | `/tickets/:id` | P0 |
| Submit Ticket | `/tickets/submit` | P0 |
| Subscription Overview | `/subscriptions` | P1 |
| Per-Driver Plan Management | `/subscriptions/drivers` | P1 |
| Invoice History | `/subscriptions/invoices` | P1 |
| Fine Tracker | `/fines` | P1 |
| Company Documents | `/documents/company` | P1 |
| Driver Documents | `/documents/drivers/:id` | P1 |
| SMS / FMCSA Dashboard | `/safety/sms` | P1 |
| Safety Inspections | `/safety/inspections` | P1 |
| Safety Violations | `/safety/violations` | P1 |
| DataQ Challenges | `/safety/dataq` | P1 |
| MVR Management | `/mvr` | P1 |
| Account Profile | `/profile` | P1 |
| Integrations Settings | `/settings/integrations` | P2 |
| TenStreet Setup | `/settings/integrations/tenstreet` | P2 |
| Workday Setup | `/settings/integrations/workday` | P2 |
| Notifications Settings | `/settings/notifications` | P2 |
| User Management (sub-users) | `/settings/users` | P2 |

---

## Data Model Summary (Firestore)

```
carriers/{uid}                          — Account holder PII, company info, status
carriers/{uid}/dot_numbers/{dot_id}     — Per-DOT: FMCSA data, fleet info, operations, cargo
carriers/{uid}/dot_numbers/{dot_id}/inspections/{id}  — Cached FMCSA inspections
carriers/{uid}/dot_numbers/{dot_id}/violations/{id}   — Cached FMCSA violations
carriers/{uid}/alerts/{alert_id}        — Unread safety + compliance alerts
carriers/{uid}/integration_configs/{type}  — TenStreet, Workday, etc.

drivers/{uid}                           — Driver profile (CDL, DOB, contact, DOT history)
drivers/{uid}/tickets/{ticket_id}       — Mirror of AI engine dual-write
drivers/{uid}/documents/{doc_id}        — Document metadata

tickets/{ticket_id}                     — Attorney queue (shared with attorney portal)
subscriptions/{sub_id}                  — Per-driver subscription record
fines/{fine_id}                         — Fine tracking per case
dataq_challenges/{challenge_id}         — DataQ filing status
documents/{doc_id}                      — Company and driver document metadata

fmcsa_cache/{dot_number}               — FMCSA API cache (refreshed daily)
```

---

## API Routes (New Backend)

### Carrier Onboarding
```
POST /carriers/register                 Create Firebase Auth + Firestore stub
POST /carriers/verify-otp              Verify email/SMS OTP
PUT  /carriers/setup/account           Save account holder PII
PUT  /carriers/setup/company           Save company info
POST /carriers/dot                     Add DOT number (FMCSA auto-fill)
PUT  /carriers/dot/:dot_id             Update DOT info
DELETE /carriers/dot/:dot_id           Archive DOT
PUT  /carriers/setup/fleet             Save fleet info per DOT
PUT  /carriers/setup/operations        Save operating states + cargo
```

### Driver Management
```
GET    /carriers/drivers                List all drivers (with filters, pagination)
POST   /carriers/drivers                Add single driver
POST   /carriers/drivers/import         CSV bulk import
GET    /carriers/drivers/:id            Driver detail
PUT    /carriers/drivers/:id            Update driver profile
POST   /carriers/drivers/:id/activate   Activate driver
POST   /carriers/drivers/:id/deactivate Deactivate driver
POST   /carriers/drivers/:id/transfer   Transfer to different DOT
DELETE /carriers/drivers/:id            Soft delete
POST   /carriers/drivers/bulk-action    Bulk activate/deactivate/transfer/export
```

### Tickets
```
GET  /carriers/tickets                  List all tickets across all drivers
POST /carriers/tickets/submit           Submit new ticket (triggers AI scan)
GET  /carriers/tickets/:id              Ticket detail + updates
POST /carriers/tickets/:id/update       Post case update note (carrier side)
```

### DataQ
```
GET  /carriers/dataq                    List DataQ challenges
POST /carriers/dataq                    Submit new DataQ challenge
GET  /carriers/dataq/:id                Challenge detail + status
PUT  /carriers/dataq/:id               Update challenge (staff only)
```

### Subscriptions & Billing
```
GET  /carriers/subscriptions            Subscription overview + per-driver list
PUT  /carriers/subscriptions/:id        Change plan or payment model for driver
POST /carriers/subscriptions/bulk       Bulk plan change
POST /carriers/payment-method           Add Stripe card or ACH
GET  /carriers/invoices                 Invoice history
GET  /carriers/invoices/:id/pdf         Download invoice PDF
```

### Fines
```
GET  /carriers/fines                    All fines (all drivers, filterable)
PUT  /carriers/fines/:id               Update payment status / mark paid externally
POST /carriers/fines/:id/pay           Initiate Stripe payment for fine
```

### Documents
```
POST /carriers/documents                Upload document (company or driver)
GET  /carriers/documents                List company documents
GET  /carriers/drivers/:id/documents    List driver documents
DELETE /carriers/documents/:id          Soft delete document
GET  /carriers/documents/:id/download   Signed download URL
```

### Safety / FMCSA
```
GET  /carriers/safety/profile/:dot      FMCSA carrier profile (from cache)
GET  /carriers/safety/csa/:dot          CSA BASIC scores
GET  /carriers/safety/inspections/:dot  Inspection list
GET  /carriers/safety/violations/:dot   Violation list
POST /carriers/safety/refresh/:dot      Force refresh FMCSA cache
```

### MVR
```
GET  /carriers/mvr                      List MVR reports (all drivers)
POST /carriers/mvr/request              Request single MVR
POST /carriers/mvr/batch                Request batch MVR
GET  /carriers/mvr/:id                  MVR detail + PDF link
```

### Integrations
```
GET  /carriers/integrations/tenstreet         Current TenStreet config
PUT  /carriers/integrations/tenstreet         Save TenStreet config
POST /carriers/integrations/tenstreet/test    Send test webhook
POST /webhooks/tenstreet/:carrier_uid         Receive TenStreet events (no auth, HMAC verified)
GET  /carriers/integrations/workday           Current Workday config
PUT  /carriers/integrations/workday           Save Workday config
GET  /carriers/integrations/workday/export    Download deduction export CSV
POST /carriers/integrations/workday/sync      Trigger manual roster sync
```

---

## Build Sequence

### Phase 0 — Auth & Skeleton (Week 1–2)
- Firebase Auth (email + Google + Microsoft)
- Carrier registration wizard (5 steps: account → company → DOT → fleet → operations)
- Firebase ADC on Cloud Run (match attorney portal pattern)
- Basic dashboard shell

### Phase 1 — Core Operations (Week 3–5)
- Driver list + add/edit/activate/deactivate
- CSV import with validation preview
- DOT management + FMCSA auto-fill
- Ticket submission (wire AI engine scan endpoint)
- Ticket tracking list + detail

### Phase 2 — Billing & Documents (Week 6–8)
- Subscription management (Stripe)
- Invoice generation + PDF
- Fine tracker
- Document upload + expiration alerts
- Notification center

### Phase 3 — Safety Intelligence (Week 9–11)
- FMCSA API integration + daily cache refresh
- SMS dashboard (powered by own cache, no Salesforce)
- DataQ challenge submission + tracking
- MVR request + delivery webhook
- CDL/med cert expiration alerts

### Phase 4 — Automations (Week 12–14)
- TenStreet webhook receiver + setup UI
- Workday API sync + deduction export
- SambaSafety continuous MVR monitoring

### Phase 5 — Polish & Scale (Week 15+)
- Multi-user sub-accounts (dispatcher, safety manager can log in under carrier)
- Fleet safety map (violations by state heat map)
- Per-driver risk scoring
- Mobile-responsive PWA polish
- Notification preferences (email, SMS, in-app toggles per alert type)
