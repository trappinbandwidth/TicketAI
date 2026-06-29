# Rig Resolve — Future State Documentation

## Current State (as of 2026-06-26)

Rig Resolve is in early QA / pre-launch. The core infrastructure is built and deployed:

- AI ticket processing pipeline is live on Cloud Run
- Firestore schema v1 is deployed with 19 collections and security rules
- Admin dashboard (internal QA tool) runs locally with full Review Queue + Cases + Operations
- 5 attorneys, 3 test drivers, 3 staff users, and 1 carrier seeded in Firestore
- Firebase Auth accounts exist for all seeded users

**What's not live yet:**
- No real drivers have submitted tickets through the driver app
- Attorney portal frontend has not been deployed to `rigresolve-attorney.web.app`
- Carrier portal frontend has not been deployed to `rigresolve-carrier.web.app`
- Payment processing (Stripe/Rainforest) not yet integrated
- Admin dashboard is accessible only locally — not yet deployed for Quest, Eniola, Justin

---

## 90-Day Launch Plan

### Phase 0 — QA Completion (Now)
**Goal:** Close all blockers before real drivers use the product.

| Task | Priority | Owner | Notes |
|------|----------|-------|-------|
| Run end-to-end ticket scan with real ticket image | Must-have | Quest | Validates full pipeline + Firestore write |
| Test Review Queue approve/reject flow | Must-have | Quest/Eniola | Validate status transitions + driver notifications |
| Test Cases tab — assign attorney, log activity, record outcome | Must-have | Quest | Full case lifecycle |
| Deploy attorney portal frontend to rigresolve-attorney.web.app | Must-have | — | Create site in Firebase Console first |
| Deploy carrier portal frontend to rigresolve-carrier.web.app | Must-have | — | Create site in Firebase Console first |
| Deploy admin dashboard to Firebase Hosting | High | — | So Eniola and Justin can access without local setup |
| Create Firebase Hosting sites (attorney, carrier) | Must-have | Quest | Firebase Console → Hosting → Add site |
| Regenerate Firebase service account key `3c82463f` | Critical security | Quest | Prior session exposed this key in logs |
| Replace `cdl-local-dev` API key | Medium | Quest | Change before any external exposure |
| Attorney role-based access on `/review-queue` | Medium | — | Add custom claims; currently any authenticated user can access |

---

### Phase 1 — First Real Drivers (Days 1–30)
**Goal:** Process real tickets from 2 pilot drivers. Validate accuracy and attorney workflow.

**Milestone: First Ticket Scanned by a Real Driver**
1. Enroll pilot driver in Firestore (create `drivers/` doc, Firebase Auth account)
2. Driver scans their ticket in the driver app
3. AI pipeline processes it → ticket appears in Admin Review Queue
4. Staff reviewer approves → ticket moves to `New`
5. Staff assigns attorney → attorney contacts driver
6. Case resolves → outcome recorded → driver notified

**Required before this milestone:**
- Driver app live on `rigresolve.web.app`
- Firebase Phone Auth (OTP) tested end-to-end for new driver account creation
- Driver account creation flow: phone OTP → CDL number entry → plan selection
- At minimum 1 real attorney with active portal access

**Subscription collection:**
- Today subscription records are created by the seed script
- Need: subscription creation flow when a real driver signs up
- Interim: staff creates subscription docs manually
- Future: Stripe webhook creates subscription doc automatically

---

### Phase 2 — Attorney Network Live (Days 30–60)
**Goal:** 5+ active attorneys using the attorney portal. Real case throughput.

**Attorney Onboarding Pipeline:**
1. Attorney submits application via `attorney_applications/` (form not yet built)
2. Staff reviews application → interview if junior/law_student tier
3. Staff approves → creates `attorneys/` Firestore doc
4. Creates Firebase Auth account → attorney gets portal login
5. Attorney sees available cases → claims → works case

**Required for attorney portal to be useful:**
- Attorney portal frontend deployed with live Firebase Auth
- Available cases visible and filterable by state
- Case detail view shows full ticket extraction, court info, jurisdiction context
- Outcome recording form sends to `/operations/record-outcome/`

**Attorney Payment — Manual MVP:**
- Admin records outcome in Cases tab
- Admin manually processes payment (check/Venmo/Zelle)
- Admin logs payout in `attorney_payouts/` Firestore collection
- No automation yet (Phase 3)

---

### Phase 3 — Carrier Enrollment (Days 60–90)
**Goal:** 1 carrier company enrolled with 5+ drivers.

**Carrier Onboarding Flow:**
1. Quest/Eniola creates carrier record in Firestore manually
2. Carrier portal login created for billing contact
3. Carrier admin adds drivers via carrier portal
4. Driver notifications go out; drivers create app accounts
5. Monthly invoice generated manually by staff

**Carrier pricing negotiation:**
- Starting rate: $9.00/driver/month for 50+ drivers
- Smaller fleets: negotiate above $9.00
- Document agreed rate in `carriers.per_driver_rate`

---

## Feature Roadmap

### Now (v1 — QA)
- Multi-agent AI ticket extraction pipeline
- Review Queue → Cases → Outcome lifecycle
- Urgency routing and court deadline monitoring
- Payment alert monitoring
- Driver notifications (in-app via Firestore)
- Attorney matching by state/county
- Admin dashboard (internal only)

### Near-Term (v1.5 — 60 days)
- Attorney portal live on web
- Carrier portal live on web
- Driver app full flow (upload, track, notifications)
- Manual payout tracking (staff-entered)
- One real carrier enrolled

### Medium-Term (v2 — 6 months)
- **Payment automation:** Stripe or Rainforest Payments for driver subscriptions
- **Attorney payment automation:** Stripe Connect or Rainforest Payouts
- **MVR pull integration:** SambaSafety or equivalent API
- **PSP pull integration:** FMCSA PSP API with driver consent workflow
- **Research Ron Phase 2:** Violation corpus from Kaggle CDL dataset (ClickUp #86b9ryenz)
- **SMS notifications:** Twilio for court reminders and case updates (replaces in-app only)
- **Email notifications:** SendGrid for attorney outreach confirmations
- **Cloud Scheduler:** Automate court deadline monitor (daily 8am) and payment alerts (daily)

### Long-Term (v3 — 12 months)
- **Court research agent:** Auto-populate `courts/` collection from public court websites
- **Document classification:** Pre-filter to route by doc type before Lone Ranger
- **Attorney match learning:** Outcome-based attorney selection (best attorney per violation+state)
- **Driver mobile app:** Dedicated iOS/Android app (current is PWA/web)
- **Carrier self-serve:** Carriers add/remove drivers without staff involvement
- **Attorney self-serve:** Attorneys manage their own profile, states, counties
- **API product:** `courts/` and `violations/` collections exposed as a commercial API for other CDL defense platforms
- **PreX (Pre-Existing Ticket) flow:** Handle tickets that predate driver's subscription enrollment
- **Multi-ticket cases:** One case for a driver with multiple simultaneous tickets

---

## Architecture Future State

### Current Architecture
```
Driver App (Firebase Hosting)
    ↓ uploads
AI Ticket Engine (Cloud Run / FastAPI)
    ↓ Claude API (multimodal)
    ↓ LangGraph pipeline (14 agents)
    ↓ writes
Firestore (Firebase)
    ← reads
Attorney Portal (Cloud Run / Flask + React)
Carrier Portal (Cloud Run / Flask + React)
Admin Dashboard (local only today)
```

### Target Architecture (12 months)
```
Driver App (Firebase Hosting / Future: React Native)
    ↓ OTP auth + upload
AI Ticket Engine (Cloud Run / FastAPI)
    ↓ Claude API
    ↓ LangGraph pipeline
    ↓ Firestore dual-write
    ↓ Stripe webhook events
    ↓ Twilio SMS / SendGrid email
    ↓ MVR API / PSP API (async)
Firestore + Firebase Storage
    ← reads
Attorney Portal (Cloud Run / React)
Carrier Portal (Cloud Run / React)
Admin Dashboard (Firebase Hosting / internal)
Cloud Scheduler
    → Court Deadline Monitor (daily 8am)
    → Payment Alert (daily)
    → MVR/PSP result polling (as needed)
    → Attorney assignment follow-up (3 days post-assign)
```

---

## Data Model Future State

### Collections to Build Out

**`courts/` — Court Reference Database**  
Currently: empty, populated manually  
Target: 3,000+ county court records covering all states where CDL tickets are common  
Method: Attorney network contributes records; staff verifies; Research Ron queries on every scan  
Future: API product for CDL defense platforms

**`violations/` — CDL Violation Code Reference**  
Currently: empty  
Target: All state-specific violation codes mapped to FMCSA categories  
Method: FMCSA data imports + attorney-contributed state-specific codes  
Future: Powers Research Ron corpus analysis

**`ai_scans/` — Full Scan Archive**  
Currently: Schema defined but not yet written to (Lone Ranger outputs go to SQLite only)  
Target: Every scan writes full pass-1, pass-2, consensus to Firestore for long-term training data retention

**`ticket_corrections/` — Training Signal**  
Currently: Schema defined but correction UI not yet built  
Target: Every human correction in the Review Queue writes a correction record  
Powers: Automated prompt improvement analysis, fine-tuning dataset

### New Collections (Future)
- `attorney_calendar/` — Court dates attorneys have scheduled
- `notifications_log/` — Audit trail of all Twilio/SendGrid sends (not just Firestore notifications)
- `api_customers/` — If courts/ and violations/ are exposed as API products
- `webhooks/` — Stripe webhook event log for debugging

---

## Security Roadmap

### Immediate (Before Any External Users)
1. **Regenerate Firebase service account key** `3c82463f` — exposed in session logs
2. **Rotate `cdl-local-dev` API key** — set a production key in GCP Secret Manager
3. **Firebase App Check** — require app attestation to block unauthorized API calls
4. **Role-based access on admin dashboard** — currently any Firebase Auth user can access; add custom claims for `staff` role check

### Short-Term (Before First Real Carriers)
5. **Rate limiting** on `/api/v1/process` — prevent abuse; each driver gets N scans per day
6. **Audit logging** — all admin actions (approve, reject, assign, outcome) logged to `staff_audit/` collection
7. **Driver consent record** — explicit consent for PSP pull required before MVR/PSP Request agents activate

### Long-Term
8. **SOC 2 Type I** — when carrier contracts require it (~12 months)
9. **PCI compliance scope reduction** — minimize card data scope by routing payment collection through Stripe.js (no card data touches our servers)
10. **FMCSA compliance** — document driver consent process for MVR/PSP pulls per 49 CFR 391.23

---

## Business Metrics to Track

### Early (Now → 60 days)
- Tickets processed per week
- GREEN / YELLOW / RED pass rate distribution
- Attorney match rate by state
- Time from ticket scan to attorney assignment (target: < 24 hours)
- Driver notification delivery rate

### Growth (60 days → 6 months)
- Monthly recurring revenue (drivers × plan price + carrier × per_driver_rate)
- Subscription churn rate
- Case outcome distribution (won / dismissed / reduced / lost / transferred)
- Attorney win rate by state and violation type
- Average time from case assignment to outcome

### Scale (6 months+)
- Revenue per attorney in network
- Carrier retention rate
- CDL disqualification avoided (the metric that matters most to drivers)
- Attorney network coverage gap (states with <80% match rate)

---

## Open Decisions

| Decision | Options | Timeline |
|----------|---------|----------|
| Payment processor | Stripe vs. Rainforest Payments | Before Phase 2 |
| Safe driver rate timing | Verify before card capture (provisional rate) vs. after (guaranteed rate) | Before public launch |
| Attorney payout frequency | Weekly vs. monthly vs. per-case | Before first payout |
| Driver app: web vs. native | Current PWA vs. React Native | 6-month decision |
| MVR pull provider | SambaSafety, Verisk, Motorists | Before v2 |
| SMS provider | Twilio, Amazon SNS, Plivo | Before v2 |
| Competitive claim review | Legal review of "vs. CDL Legal" copy | Before public marketing |
| Carrier portal git repo | Initialize and push to GitHub | Now |

---

## Known Technical Debt

| Item | Location | Impact | Priority |
|------|----------|--------|---------|
| CDL Legal → Rig Resolve branding | All code comments, class names | Low (internal) | Low |
| `cdl-local-dev` API key | `.env`, `deploy/cloud_run_deploy.sh` | Security | Medium |
| Service account key `3c82463f` | Prior session logs | Security | Critical |
| Admin dashboard not deployed | `frontend-qa/` | Only Quest has access | High |
| `ai_scans/` collection not written to | `app/services/firebase_service.py` | Training data gap | Medium |
| `ticket_corrections/` UI not built | Admin dashboard | Training signal lost | Medium |
| Research Ron Phase 2 corpus | `agents/research_ron.py` | Defense intelligence not firing | Medium |
| Attorney role claim check on `/review-queue` | `app/routes/admin.py` | Any auth'd user can access | Medium |
| Carrier portal not in git | `/carrier-portal-*/` | Not versioned | High |
| SQLite queue vs. Firestore `ai_scans/` | Dual storage of scan data | Sync risk | Medium |

---

*Last updated: 2026-06-26*
