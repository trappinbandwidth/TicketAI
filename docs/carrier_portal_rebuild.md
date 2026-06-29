# Carrier Portal — Existing Audit & Rebuild Plan

**Last Updated:** 2026-06-28  
**Goal:** Rebuild around FMCSA/SMS safety data and MVR tools. Keep what works, trash the Salesforce dependency.

---

## What Exists Today

### Tech Stack
- **Backend:** Flask + PyMongo + JWT auth
- **Database:** MongoDB (user accounts, column preferences) + Salesforce (all real data)
- **Frontend:** React 18 + TypeScript + Material UI + ApexCharts + React Query + Jotai
- **Auth:** Custom JWT (bcrypt, not Firebase)
- **File Storage:** AWS S3
- **External:** Salesforce API (SOQL), Stripe (payments), External MVR API

### Authentication
Custom JWT flow (NOT Firebase Auth):
- MongoDB stores: Email, bcrypt password, DriverId (Salesforce ID), UserType, IsMVR flag
- Login → JWT with email + DriverId in payload → sessionStorage
- Last login synced to Salesforce `Portal_Last_Login__c`

**Problem:** Incompatible with the rest of Rig Resolve (attorney portal + AI engine use Firebase Auth). Must migrate to Firebase Auth in rebuild.

---

## Full Inventory of Existing Routes

### Auth / User Management (Keep → Migrate to Firebase)
| Route | What It Does |
|-------|-------------|
| `RegisterUser` | Carrier/driver signup → MongoDB |
| `RegisterDriverUser` | Driver registration → MongoDB |
| `LoginUser` | bcrypt password check → JWT |
| `GetUserDetails` | Profile from MongoDB |
| `UpdateUserDetails` | Update MongoDB profile |
| `ChangePassword` | bcrypt password update |
| `SendOTP` / `VerifyOTP` | Phone OTP flow |
| `pinCarrier` | Set active carrier in session |

### Driver Management (Keep → Move to Firestore)
| Route | Current Source | Keep? |
|-------|---------------|-------|
| `GetDriversList` | Salesforce | ✅ Keep, move to Firestore `drivers/` |
| `getDriverDetailsById` | Salesforce | ✅ Keep |
| `SearchDriver` | Salesforce | ✅ Keep |
| `AddDriver` | Salesforce + MongoDB | ✅ Keep |
| `EditDriver` | Salesforce | ✅ Keep |
| `DeleteDriver` | Salesforce | ✅ Keep |

### SMS / FMCSA Data (Keep → Replace Salesforce with FMCSA API)
| Route | Current Source | Replace With |
|-------|---------------|-------------|
| `GetSMSDataInspectionsList` | Salesforce `SMS_Inspection_Data__c` | FMCSA SMS API |
| `GetSMSDataViolationsList` | Salesforce `SMS_Violation_Data__c` | FMCSA SMS API |
| `GetSMSDashboardSummary` | Salesforce | FMCSA API + own aggregation |
| `GetBasicsUnsafeDriving` | Salesforce | FMCSA API |
| `GetBasicsDriverFitness` | Salesforce | FMCSA API |
| `GetBasicsControlledSubstance` | Salesforce | FMCSA API |
| `GetBasicsVehicleMaintainance` | Salesforce | FMCSA API |
| `GetBasicsHoursOfService` | Salesforce | FMCSA API |
| `GetBasicsCrashIndicator` | Salesforce | FMCSA API |
| `GetSmsNotifyCount` | Salesforce | Firestore alerts collection |
| `GetSMSNotifyInspectionList` | Salesforce | FMCSA API + Firestore |
| `GetSMSNotifyCrashIndicators` | Salesforce | FMCSA API + Firestore |

### Dashboard Metrics (Keep → Recompute from own data)
| Route | Keep? |
|-------|-------|
| `GetOpenTicketsCount` | ✅ Keep — query `tickets/` Firestore |
| `GetComplianceChallengesCount` | ✅ Keep — DataQ challenges |
| `GetActiveMembershipCount` | ✅ Keep — query `subscriptions/` |
| `GetViolations60DaysCount` | ✅ Keep — query stored inspection data |
| `GetViolationsRollingOffCount` | ✅ Keep |
| `GetCleanInspection60DaysCount` | ✅ Keep |
| `GetISSScoreThisWeek` | ✅ Keep — compute from FMCSA data |

### MVR Routes (Keep → Replace Salesforce with direct MVR vendor API)
| Route | Keep? |
|-------|-------|
| `GetMVRReportList` | ✅ Keep |
| `GetMVRBatchList` | ✅ Keep |
| `GetMVRRecord/<id>` | ✅ Keep |
| `GetMVRReportPDF` | ✅ Keep |
| `GetMVREpnList` | ✅ Keep (CA EPN tracking) |
| `RequestMVR` | ✅ Keep |
| `ReviewMVRAlert` | ✅ Keep |
| `getMVRWarningStatus` | ✅ Keep |

### Ticketing Routes (Keep → Already in Firestore)
| Route | Keep? |
|-------|-------|
| `GetOpenTicketsList` | ✅ Keep — Firestore `tickets/` |
| `CreateTicket` | ✅ Keep |
| `UpdateTicketDetails` | ✅ Keep |
| `GetComplianceChallengesList` | ✅ Keep |

### Payment Routes (Keep)
| Route | Keep? |
|-------|-------|
| `PaymentGateway/CreateCheckoutSession` | ✅ Keep (Stripe) |
| `PaymentGateway/GetSessionStatus/<id>` | ✅ Keep |

### Utility Routes
| Route | Keep? |
|-------|-------|
| `GlobalSearch` | ✅ Keep |
| `get-column-state` / `save-column-state` | ✅ Keep (MongoDB) |
| `upload-csv` | ✅ Keep |
| `uploadDocuments` | ✅ Keep (S3) |
| `GetMasterData` | ✅ Keep |
| `GetProductList` | ✅ Keep |
| `GuestUserLogin` | ❌ Remove (no clear use) |
| `EncryptData` / `DecryptData` | ❌ Remove or document use case |

### Attorney Portal Routes in Carrier Backend (inside carrier service)
These are duplicates of what's now in the attorney portal service.
- ❌ **Remove** — all attorney functionality moved to attorney portal service

---

## What to KEEP from Frontend

The React frontend is genuinely good. Keep:
- ✅ Table component with CSV export and column customization
- ✅ ApexCharts dashboard (6 BASICS charts are the right design)
- ✅ React Hook Form + Yup validation patterns
- ✅ React Query data fetching + caching
- ✅ Jotai state (carrier switcher, driver list atoms)
- ✅ Multi-carrier workspace switcher
- ✅ Responsive layout (desktop + mobile)
- ✅ Material UI component library
- ✅ All SMS/FMCSA page layouts (sms-dashboard, sms-inspections, sms-violations, sms-notify)
- ✅ MVR page (3-tab layout: Reports, Batches, CA EPN)
- ✅ Driver list table + driver detail page
- ✅ Open tickets + submitted tickets pages

---

## What to REMOVE / REPLACE

### Remove (Dead or Legacy)
- ❌ All Salesforce SOQL queries (`sf_query.py`, `SalesForceAPI`, `SalesForceAttorneyPortalAPI`)
- ❌ Salesforce OAuth token management (`salesforce_api_client.py`)
- ❌ Attorney portal routes inside carrier service
- ❌ MongoDB-based auth (replace with Firebase Auth)
- ❌ `Abenity_Status__c` references — Abenity integration dead
- ❌ `Enrolled_In_Samba_Monitoring__c` — Samba not integrated
- ❌ Marketing message fields (`Marketing_Message_Sent__pc`, etc.)
- ❌ Spouse contact fields
- ❌ Commented-out socket API route
- ❌ `GuestUserLogin` endpoint
- ❌ Fire-and-forget `threading.Thread` Salesforce sync calls — replace with proper task queue if needed

### Replace
- 🔄 JWT auth → Firebase Auth (match attorney portal + AI engine)
- 🔄 MongoDB user accounts → Firebase Auth + Firestore `carriers/` collection
- 🔄 Salesforce SMS data → FMCSA SMS API direct + Firestore cache
- 🔄 Salesforce MVR data → MVR vendor API (IntelliCheck, SambaSafety, or similar) + Firestore
- 🔄 AWS S3 → Firebase Storage (align with rest of system)
- 🔄 Background `threading.Thread` → Firebase Cloud Tasks or Cloud Run jobs

---

## Rebuild Plan: Carrier Portal 2.0

### Foundation (what the rebuild is built around)

**Core Value Proposition:**
Carriers need to see their fleet's safety exposure before it becomes a citation or DOT intervention. The portal is a compliance + legal defense dashboard, not just a driver roster.

**Primary Data Sources After Rebuild:**
1. **FMCSA API** (free, public) — CSA scores, inspections, violations, carrier profile
2. **MVR Vendor API** (paid) — Individual driver motor vehicle records
3. **Firestore** (ours) — Driver roster, subscriptions, tickets, alerts, case status
4. **AI Engine** (ours) — Ticket scans, attorney matching, case intake

---

### New Firestore Schema

```
carriers/{carrier_id}
  dot_number, company_name, address, state
  contact_name, contact_email, contact_phone
  subscription_plan (Silver/Gold/Platinum)
  subscription_status (active/suspended/cancelled)
  created_at, updated_at

carriers/{carrier_id}/drivers/{driver_id}
  first_name, last_name, cdl_number, cdl_state, cdl_class
  cdl_expiration, med_cert_expiration
  date_of_birth, hire_date
  subscription_status, subscription_plan
  enrollment_date
  mvr_status (current/alert/expired)
  last_mvr_date
  active

carriers/{carrier_id}/inspections/{inspection_id}
  inspection_date, report_state, inspection_level
  driver_id, driver_name
  violations[] { basic_category, code, description, points, oos }
  clean (boolean)
  source (fmcsa_api)
  synced_at

carriers/{carrier_id}/alerts/{alert_id}
  type (new_inspection, new_violation, mvr_alert, csas_change)
  severity (critical/warning/info)
  driver_id, driver_name
  description
  read (boolean)
  created_at

fmcsa_cache/{dot_number}
  carrier_profile { ... }
  csa_scores { unsafe_driving, hos, driver_fitness, controlled_substances, vehicle_maintenance, crash_indicator, hazmat }
  percentile_scores { ... }
  last_fetched
  inspections[] (last 24 months)
  violations[] (last 24 months)
```

---

### FMCSA API Integration

**Endpoint:** `https://mobile.fmcsa.dot.gov/qc/services/`  
**Auth:** Free API key from FMCSA

**Key calls to build:**

```python
# 1. Carrier safety profile
GET /carriers/{dot_number}?webKey={key}
→ carrier name, address, OOS status, insurance status

# 2. CSA BASIC scores
GET /carriers/{dot_number}/basics?webKey={key}
→ 6 BASIC scores + percentiles vs national average

# 3. Carrier inspections
GET /carriers/{dot_number}/inspections?webKey={key}
→ inspection date, state, level, violations

# 4. Carrier violations
GET /carriers/{dot_number}/violations?webKey={key}
→ violation code, description, BASIC category, points, weight

# 5. Crash data
GET /carriers/{dot_number}/crashes?webKey={key}
→ crash date, state, fatalities, injuries, recordable
```

**Caching strategy:** Write to `fmcsa_cache/{dot_number}` on first fetch. Refresh daily via Cloud Scheduler. Serve from cache to avoid rate limits.

---

### MVR Integration

**Recommended vendors (evaluate):**
- **SambaSafety** — continuous monitoring + alert on new violation (best for fleet)
- **IntelliCheck** — one-time MVR pull
- **CheckMVR** — affordable bulk pulls

**Build:**
1. `POST /requestMVR { driverId, consentSignature }` — Request single MVR
2. `POST /requestBatchMVR { driverIds[], consentSignatures[] }` — Bulk request
3. Webhook receiver for completed MVR delivery
4. Store MVR in Firestore + Firebase Storage (PDF)
5. Parse MVR for: violations, license status, suspensions, endorsements, restrictions
6. Alert carrier if MVR shows: suspension, new violation, expiring CDL

---

### New Screens to Build

#### Screen: Carrier Safety Dashboard (home)
Replace generic dashboard with FMCSA-first view:
- **DOT Profile Card:** Company name, DOT#, MC#, OOS status, authority status
- **CSA Score Gauges:** 6 BASIC scores, each with:
  - Current percentile
  - ALERT threshold line (red at 65th percentile for unsafe driving, 80th for others)
  - Trend arrow (improving / worsening)
- **Recent Activity:** Last 5 inspections, last 5 violations
- **Action Items:** Violations expiring, CDLs expiring, MVRs due, open tickets

#### Screen: Fleet Safety Map
- Heat map of where violations occurred (by state)
- Click state → filter inspections/violations to that state
- Useful for seeing where fleet is getting hit

#### Screen: Driver Safety Profiles
Replace simple driver list with safety-first view:
- Per driver: CDL status, MVR status, open violations, inspection history
- Risk score: green/yellow/red based on recent violations
- Alert badge if MVR shows a new suspension or adverse event

#### Screen: Compliance Coaching (new)
- Per driver, show their contribution to carrier's BASIC scores
- Surface DataQ challenge opportunities (inspections that can be contested)
- Link to Rig Resolve legal for each eligible citation

---

### Rebuild Sequence

| Phase | Work | Output |
|-------|------|--------|
| **Phase 1** | Migrate auth from JWT → Firebase Auth | Carriers can log in via Firebase (same as attorneys) |
| **Phase 1** | Migrate carrier + driver data from MongoDB/Salesforce → Firestore | Single source of truth |
| **Phase 2** | Wire FMCSA API + build `fmcsa_cache` sync | Real CSA scores, inspections, violations from public API |
| **Phase 2** | Rebuild SMS dashboard consuming Firestore cache | Same UI, no Salesforce dependency |
| **Phase 3** | MVR vendor integration + webhook receiver | Request and receive MVRs in-system |
| **Phase 3** | Alert system (new violations, expiring CDLs, MVR alerts) | Proactive notifications |
| **Phase 4** | Fleet Safety Map | Visual safety exposure |
| **Phase 4** | Per-driver risk scores + coaching view | DataQ, violations, CDL expiration |
| **Phase 5** | Carrier ↔ AI Engine integration | Carrier submits ticket → AI scans → attorney matched |
| **Phase 5** | Case tracking for carrier | Carrier sees status of all driver tickets |

---

## What the Carrier Portal Becomes

Before: A Salesforce data viewer bolted onto a driver roster.

After: A proactive fleet safety + legal defense command center:

1. **Know before FMCSA acts** — See CSA scores, percentiles, and which violations are pulling scores up before an alert or intervention
2. **Protect every driver automatically** — When a driver gets a citation, it flows into Rig Resolve, gets scanned, matched to an attorney, and the carrier sees status in real time
3. **MVR on demand** — Request MVRs for new hires or annual reviews; get alerted when continuous monitoring catches something
4. **DataQ challenges** — Surface incorrect inspections that the carrier can contest through FMCSA
5. **Attorney visibility** — Carrier can see which cases are open, which attorney is working them, and what the outcome was

---

## Key Technical Decisions for Rebuild

| Decision | Choice | Reason |
|----------|--------|--------|
| Auth | Firebase Auth | Aligns with attorney portal + AI engine; single IAM |
| Driver data | Firestore `carriers/{id}/drivers/` | Real-time, no Salesforce dependency |
| SMS/FMCSA data | Direct FMCSA API + Firestore cache | Free, official, no intermediary |
| MVR vendor | Evaluate SambaSafety (continuous) vs. CheckMVR (one-time) | SambaSafety preferred for fleet |
| File storage | Firebase Storage | Aligns with AI engine (already used for scan images) |
| Column preferences | Keep MongoDB for this only | Low priority to migrate; minor feature |
| Frontend | Keep React + MUI + ApexCharts | It's good; rebuild = backend swap, not UI rewrite |
| Background jobs | Cloud Tasks or Cloud Scheduler | Replace fire-and-forget threads |
