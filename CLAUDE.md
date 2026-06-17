# Rig Resolve — Claude Code Onboarding

## What this product is

**Rig Resolve** is a legal benefit platform for commercial truck drivers (CDL holders). Drivers pay a monthly subscription to get attorney representation when they receive traffic citations. There are three user types:

- **Drivers** — CDL holders who submit tickets and track case status
- **Attorneys** — CDL defense lawyers who claim and work cases
- **Carriers** — Trucking companies that enroll their drivers and deduct premiums from payroll

**Important language:**
- "Tickets" = traffic citations, not support tickets
- "Carriers" = trucking companies, not insurance carriers
- "Members" / "subscribers" / "drivers" all refer to enrolled CDL holders
- The brand is **Rig Resolve**. The legal benefit product is inherited from CDL Legal (the old org). Code still has CDL Legal references that are being migrated.

---

## Repositories

| Repo | GitHub | Local path |
|------|--------|------------|
| AI Ticket Engine | `git@github.com:trappinbandwidth/TicketAI.git` | `/Users/digitalmercenary/CDL_Defense/AI_Ticket_Scanner/ai-ticket-engine-main/` |
| Attorney Portal | `git@github.com:trappinbandwidth/RigResolveAttorney.git` | `/Users/digitalmercenary/CDL_Defense/Attorney-Portal-main/` |
| Driver App | same as TicketAI (branch: main) | `/Users/digitalmercenary/CDL_Defense/driver-app-main/` |
| Carrier Portal | not yet a git repo | `/Users/digitalmercenary/CDL_Defense/carrier-portal-change-driver-tab-1 3/` |

> The carrier portal directory name has a space — always quote it in shell commands.

---

## Infrastructure

**GCP Project:** `rigresolve`  
**Firebase Project:** `rigresolve` (same project — ADC works seamlessly)  
**Region:** `us-central1`

### Deployed services (Cloud Run)

| Service | URL |
|---------|-----|
| AI Ticket Engine | `https://ai-ticket-engine-kajugdk3nq-uc.a.run.app` |
| Attorney Portal Backend | `https://attorney-portal-626128667800.us-central1.run.app` |
| Carrier Portal Backend | `https://carrier-portal-626128667800.us-central1.run.app` |

### Firebase Hosting (frontends — deploy pending as of session end)

| Site | URL |
|------|-----|
| Driver App | `https://rigresolve.web.app` |
| Attorney Portal Frontend | `https://rigresolve-attorney.web.app` |
| Carrier Portal Frontend | `https://rigresolve-carrier.web.app` |

### GCP Secrets (Secret Manager)
- `ANTHROPIC_API_KEY` — injected into AI engine at runtime
- No service account JSON in containers — all services use Application Default Credentials (ADC)

---

## Authentication

All three portals use **Firebase Auth** (email/password). Every backend verifies Firebase ID tokens via `firebase_admin.auth.verify_id_token()`. The old system used custom JWTs + Salesforce — that migration is complete.

**Token flow:**
1. Frontend signs in via Firebase SDK → gets ID token
2. Frontend attaches `Authorization: Bearer <id_token>` to every API request
3. Backend calls `verify_id_token()` in `service/utils/utils.py` → returns `{DriverId, Email, Name, Role}`

**Default role assignment:**
- Attorney portal: `role = "attorney"`
- Carrier portal: `role = "carrier"`
- Driver app: Firebase Phone Auth (OTP) — `uid` is the driver ID

---

## AI Ticket Engine — Architecture

FastAPI app. Entry point: `app/main.py`. Routes mounted at `/api/v1`.

### Routes
| File | Endpoints |
|------|-----------|
| `app/routes/process.py` | `POST /process` — main scan endpoint |
| `app/routes/queue.py` | Queue management |
| `app/routes/pricing.py` | Price estimates |
| `app/routes/admin.py` | Training export + reviewer queue (`/admin/review-queue`, `/admin/approve-ticket/{id}`, `/admin/reject-ticket/{id}`) |

### LangGraph Agent Pipeline (`orchestrator/graph.py`)

```
Lone Ranger (pass 1, temp=1.0)
  → Referee (score extraction)
      GREEN  → Book Worm → Research Ron → Team Quest → assemble_green
      YELLOW → Lone Ranger 2 (pass 2, temp=0.4)
             → Consensus (merge passes, flag conflicts)
             → Referee 2 (re-score)
             → Book Worm → Research Ron → Team Quest → assemble_yellow
      RED    → Lone Ranger 2 → Consensus → Referee 2 → escalate_red
```

### Agents (`agents/`)
| Agent | Role |
|-------|------|
| `lone_ranger.py` | Primary OCR extraction via Claude — pulls all ticket fields |
| `referee.py` | Scores extraction quality → GREEN / YELLOW / RED |
| `consensus.py` | Merges two extraction passes, flags `dual_conflicts` |
| `book_worm.py` | CDL-specific enrichment (points, disqualification risk) |
| `research_ron.py` | Jurisdiction research — court system, appearance rules, attorney timelines. Phase 2: S3 corpus lookup (not yet wired) |
| `team_quest.py` | Attorney matching — finds top 3 CDL attorneys by state/county from local DB |

### Firestore dual-write (`app/services/firebase_service.py`)

Every scan writes to **two paths**:

```
drivers/{driver_id}/tickets/{ticket_id}   ← driver app real-time feed
tickets/{ticket_id}                        ← attorney portal queue
```

`source` param controls `attorney_status`:
- `source="manual"` (Rig Resolve staff scan) → `attorney_status: "AI Review"` — hidden from attorneys until a reviewer approves
- `source="driver_upload"` (driver submitted) → `attorney_status: "New"` — immediately available to attorneys

### Ticket status lifecycle
```
AI Review → (reviewer approves) → New → Accepted → Ticket Closed
         → (reviewer rejects)  → Rejected
```

### API key
The engine is protected by `x-api-key` header. Default dev key: `cdl-local-dev`. Change before production.

---

## Attorney Portal

**Backend:** Flask, Python 3.11, gunicorn. `backend/cdl-legal-attorney-service/`

Key files:
- `app.py` — Flask app, Firebase Admin init, Blueprint registration. URL prefix: `/RigResolveAttorneyService/api/v1/`
- `service/utils/utils.py` — Firebase ID token verification (replaces old JWT/Salesforce auth)
- `service/utils/firebase_service.py` — `get_available_cases()` reads `tickets/` collection, excludes `["Accepted", "Ticket Closed", "AI Review", "Rejected"]`
- `database_configuration/database.py` — MongoDB optional (graceful fallback when not configured)

Health check: `GET /RigResolveAttorneyService/HealthCheck`

**Frontend:** Vite + React. `frontend/`
- API base: `${VITE_REACT_APP_BASE_URL}/RigResolveAttorneyService/api/v1/`
- Firebase config via `VITE_FIREBASE_*` env vars (in `.env`, gitignored)
- Firebase Hosting config: `frontend/firebase.json` (site: `rigresolve-attorney`)

---

## Carrier Portal

**Backend:** Flask, Python 3.11. `backend/cdl-legal-carrier-service/`
- URL prefix: `/RigResolveCarrierService/api/v1/`
- Same auth pattern as attorney portal
- `database_configuration/db_initializer.py` — guards against `None` MongoDB URI (won't crash when MongoDB not configured)
- Deploy script: `deploy/cloud_run_deploy.sh`

Health check: `GET /RigResolveCarrierService/HealthCheck`

**Frontend:** Vite + React. `frontend/`
- Firebase config in `frontend/.env` (gitignored)
- Firebase Hosting config: `frontend/firebase.json` (site: `rigresolve-carrier`)

> The carrier portal directory is NOT a git repo yet. Initialize one before pushing.

---

## Driver App

Vite + React + TypeScript. `/Users/digitalmercenary/CDL_Defense/driver-app-main/`

Key files:
- `src/lib/firebase.ts` — initializes Firebase app, exports `auth`, `db` (Firestore), `storage`
- `src/lib/phone-auth-state.ts` — Firebase Phone Auth (OTP) state
- Firebase Hosting config: `firebase.json` (site: default `rigresolve`)
- Firestore rules: `firestore.rules` — drivers read their own subtree; authenticated users read top-level `tickets/`

Firestore real-time: drivers watch `drivers/{uid}/tickets/` for status updates.

---

## Firestore Data Model

```
tickets/{ticket_id}
  attorney_status: "New" | "AI Review" | "Accepted" | "Ticket Closed" | "Rejected"
  driver_id, driver_full_name, driver_cdl, driver_dob
  violation_category, violation_description
  ticket_state, ticket_county, ticket_city, ticket_city_state
  court_date, date_of_ticket, citation_number
  region, source, ai_scan_id, pass_status
  price_display, price_low, price_high
  created_at, last_modified_date
  reviewed_by, reviewed_at  (set on approve)
  rejection_reason          (set on reject)

drivers/{driver_id}/tickets/{ticket_id}
  status, pass_status, ai_scan_id
  all extracted fields (violation, court, driver info)
  attorney_name, attorney_phone, attorney_email
  price_display, price_low, price_high
  low_confidence_fields[], dual_conflicts[]
  updated_at
```

---

## Deploying

### Master deploy script (all 4 services)
```bash
bash /Users/digitalmercenary/CDL_Defense/deploy_all_mvp.sh
```

### Individual deploys
```bash
# AI engine
cd /Users/digitalmercenary/CDL_Defense/AI_Ticket_Scanner/ai-ticket-engine-main
bash deploy/cloud_run_deploy.sh

# Attorney backend
cd /Users/digitalmercenary/CDL_Defense/Attorney-Portal-main/backend/cdl-legal-attorney-service
gcloud run deploy attorney-portal --source . --region us-central1 --project rigresolve --set-env-vars FIREBASE_PROJECT_ID=rigresolve --quiet

# Carrier backend
cd "/Users/digitalmercenary/CDL_Defense/carrier-portal-change-driver-tab-1 3/backend/cdl-legal-carrier-service"
bash deploy/cloud_run_deploy.sh

# Driver app (hosting + Firestore rules)
cd /Users/digitalmercenary/CDL_Defense/driver-app-main
yarn build && npx firebase deploy --only hosting,firestore:rules --project rigresolve

# Attorney portal frontend
cd /Users/digitalmercenary/CDL_Defense/Attorney-Portal-main/frontend
yarn build && npx firebase deploy --only hosting --project rigresolve

# Carrier portal frontend
cd "/Users/digitalmercenary/CDL_Defense/carrier-portal-change-driver-tab-1 3/frontend"
yarn build && npx firebase deploy --only hosting --project rigresolve
```

---

## Security constraints (non-negotiable)

- `.env` files are gitignored — **never commit credentials**
- Firebase service account private keys must never be logged or printed
- Anthropic API key must not be logged or committed
- A Firebase service account key (private_key_id: `3c82463f`) was exposed in prior conversation history — **regenerate it** in the Firebase Console before going to production

---

## Known pending items

| Item | Priority | Notes |
|------|----------|-------|
| Create Firebase Auth users | Must-have | Console → Authentication → Add users for test driver, attorney, carrier |
| Firebase Hosting sites creation | Must-have | Create `rigresolve-attorney` and `rigresolve-carrier` sites in Firebase Console before first deploy |
| Carrier portal → git init | High | Directory is not versioned; initialize and push to GitHub |
| Research Ron Phase 2 | Medium | Wire S3 corpus lookup for jurisdiction research (ClickUp #86b9ryenz) |
| Attorney role-based access | Medium | `/review-queue` accessible to any authenticated user; add custom claims for role gating |
| Replace `cdl-local-dev` API key | Medium | Change default AI engine API key before any external exposure |
| Driver app env var validation | Low | Add startup check that `VITE_FIREBASE_*` vars are present |

---

## Environment variables reference

### AI Engine (`.env`)
```
ANTHROPIC_API_KEY=          # injected from Secret Manager in Cloud Run
FIREBASE_PROJECT_ID=rigresolve
USE_MOCK=false              # set true to skip Claude calls during local dev
PROMPT_VERSION=v2
API_KEY=cdl-local-dev       # x-api-key header value — change for production
```

### Attorney / Carrier Portal Backend
```
FIREBASE_PROJECT_ID=rigresolve
FIREBASE_SERVICE_ACCOUNT_JSON=  # leave blank on Cloud Run (uses ADC)
# MongoDB vars optional — portals degrade gracefully when absent
```

### Frontend apps (all three)
```
VITE_REACT_APP_BASE_URL=<backend Cloud Run URL>
VITE_FIREBASE_API_KEY=AIzaSyBoTr6la_kvM6KsRHeHrMa_KujM0hQOrMY
VITE_FIREBASE_AUTH_DOMAIN=rigresolve.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=rigresolve
VITE_FIREBASE_STORAGE_BUCKET=rigresolve.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=626128667800
VITE_FIREBASE_APP_ID=1:626128667800:web:faefb0c387f7b9d3c8bced
```
