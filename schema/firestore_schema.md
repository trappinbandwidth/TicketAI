# Rig Resolve — Firestore Schema (v1 — QA Reference)

**Status:** Finalized for QA  
**Platform:** GCP / Firebase `rigresolve` project  
**Admins:** Quest (super_admin), Eniola (super_admin), Justin (admin)

---

## Status Enums

### `tickets.attorney_status`
```
AI Review       — manual scan pending admin review; hidden from attorneys
New             — approved and available for admin to assign
Admin Assigned  — admin has selected an attorney, pending contact
Atty Contacted  — admin has reached out to attorney externally
Accepted        — attorney confirmed they will take the case
Active          — case in progress
Atty Declined   — attorney declined; admin must reassign
Outcome Logged  — attorney has reported the result
Payout Sent     — admin has processed attorney payment
Closed          — case fully complete
Rejected        — ticket rejected at review stage (bad image, wrong doc, etc.)
```

### `cases.status`
```
pending_approval  — attorney clicked claim; awaiting RR admin approval
active            — admin approved; attorney working the case
attorney_declined — attorney declined after being assigned
outcome_logged    — attorney reported result; awaiting payout
payout_sent       — manual payment processed
closed            — fully complete
rejected          — admin rejected the claim request
```

### `cases.outcome`
```
won | lost | dismissed | reduced_points | guilty | appeal |
pay_reduced_fine | donation_for_points | driving_school
```
> Note: available outcomes vary by state and court — `outcome_state` field captures which state the outcome was in.

### `attorneys.tier`
```
senior    — 5+ years experience; fast-tracked; unlimited cases
junior    — under 5 years; interview required; max 5 active cases
law_student — supervised by licensed attorney; max 2 active cases; nonprofit eligible
```

### `drivers.driver_type`
```
carrier        — enrolled through a carrier; carrier pays bulk invoice
independent    — self-pay; Core or Pro at standard or safe_driver rate
owner_operator — runs own truck/authority; self-pay same as independent
```

### `attorney_applications.status`
```
pending | interview_scheduled | under_review | approved | rejected
```

### `staff.role`
```
super_admin — full access including payouts and staff management
admin       — case management, attorney assignment, ticket review; no payout access
reviewer    — ticket review only (approve/reject AI Review queue)
```

### `attorney_payouts.status`
```
pending | paid | failed
```

### `subscriptions.billing_type`
```
carrier     — covered under carrier bulk invoice
self        — individual Stripe subscription
payroll     — carrier deducts from driver paycheck and remits to RR
```

### `tickets.urgency_level` (written by urgency_router agent)
```
CRITICAL | HIGH | STANDARD | LOW
```

---

## Collections

---

### `staff/{staff_id}`
> Rig Resolve internal users. Seed on launch: Quest, Eniola, Justin.

| Field | Type | Notes |
|-------|------|-------|
| firebase_uid | string | from Firebase Auth |
| full_name | string | |
| email | string | |
| role | string | super_admin \| admin \| reviewer |
| can_assign_cases | boolean | |
| can_approve_tickets | boolean | |
| can_process_payouts | boolean | super_admin only |
| status | string | active \| inactive |
| created_at | timestamp | |
| last_login | timestamp | |

---

### `carriers/{carrier_id}`
> Trucking companies that enroll drivers and receive bulk invoices.

| Field | Type | Notes |
|-------|------|-------|
| company_name | string | |
| dot_number | string | |
| mc_number | string | nullable |
| billing_contact_name | string | |
| billing_contact_email | string | |
| billing_type | string | invoice \| payroll |
| active_driver_count | number | updated on subscription changes |
| per_driver_rate | number | $/driver/mo; starting $9.00 for 50+ fleets; negotiated |
| status | string | active \| suspended \| inactive |
| created_at | timestamp | |
| created_by | string | staff_id |

---

### `drivers/{driver_id}`
> CDL holders. `driver_id` = Firebase Auth UID for driver-app users.

| Field | Type | Notes |
|-------|------|-------|
| firebase_uid | string | nullable — null until driver creates app account |
| full_name | string | |
| cdl_number | string | |
| cdl_state | string | 2-letter state code |
| dob | string | MM/DD/YYYY |
| phone | string | |
| email | string | nullable |
| driver_type | string | carrier \| independent \| owner_operator |
| carrier_id | string | FK → carriers; null if independent or owner_operator |
| billing_type | string | carrier \| self \| payroll |
| subscription_status | string | active \| cancelled \| lapsed \| pending |
| subscription_end_date | timestamp | when current subscription period ends |
| plan_id | string | FK → plans; core \| pro |
| safe_driver_verified | boolean | verified via PSP/MVR pull at signup |
| safe_driver_rate_applied | boolean | true = paying safe driver price |
| tickets_used_this_year | number | default 0 |
| tickets_allowed_per_year | number | from plan |
| status | string | active \| inactive |
| created_at | timestamp | |
| created_by | string | staff_id — who enrolled this driver |
| **owner_operator only** | | |
| oo_dot_number | string | nullable |
| oo_mc_number | string | nullable |
| oo_company_name | string | nullable |
| oo_num_trucks | number | nullable |

**Subcollections:**
- `drivers/{driver_id}/tickets/{ticket_id}` — real-time driver app feed (see below)
- `drivers/{driver_id}/notifications/{notif_id}` — in-app notifications (see below)

---

### `drivers/{driver_id}/tickets/{ticket_id}` ← EXISTING
> Real-time feed for the driver app. Written by the AI engine on every scan.

| Field | Type | Notes |
|-------|------|-------|
| status | string | needs_review (currently always this) |
| pass_status | string | green \| yellow \| red |
| ai_scan_id | string | |
| cached | boolean | |
| violation_category | string | |
| violation_description | string | |
| ticket_state | string | |
| ticket_county | string | |
| ticket_city | string | |
| court_date | string | |
| date_of_ticket | string | |
| citation_number | string | |
| drivers_license_type | string | |
| driver_first_name | string | |
| driver_last_name | string | |
| driver_dob | string | |
| driver_address | string | |
| cdl_license_number | string | |
| cdl_class | string | |
| attorney_name | string | from top attorney match |
| attorney_phone | string | |
| attorney_email | string | |
| attorney_match_type | string | county \| state |
| price_display | string | formatted string e.g. "$299–$499" |
| price_low | number | |
| price_high | number | |
| referee_notes | string | |
| low_confidence_fields | array | field names the AI flagged |
| dual_conflicts | array | fields where pass 1 and pass 2 disagreed |
| outcome | string | won \| dismissed \| reduced \| lost \| transferred; set on case close |
| outcome_notes | string | |
| final_charge | string | if reduced — final charge description |
| updated_at | timestamp | |

---

### `drivers/{driver_id}/notifications/{notif_id}`
> In-app notifications written by Driver Concierge on every case status transition.  
> Driver app listens via `onSnapshot` and surfaces messages in real-time.  
> Same payload structured for future SMS/email via Twilio/SendGrid.

| Field | Type | Notes |
|-------|------|-------|
| notif_id | string | UUID |
| ticket_id | string | FK → tickets |
| attorney_status | string | the status transition that triggered this notification; "court_reminder" for deadline alerts |
| message | string | full rendered message shown to driver |
| type | string | case_update \| court_reminder |
| read | boolean | false on create; driver app marks true on view |
| days_until_court | number | court_reminder type only |
| court_date | string | court_reminder type only |
| created_at | timestamp | |

**Triggered on status transitions:** AI Review → New → Accepted → Ticket Closed → Rejected  
**Court reminders sent:** when court date is < 7 days away (daily) or exactly 7 or 14 days away

---

### `tickets/{ticket_id}` ← EXISTING + EXTENDED
> Attorney portal queue. Written by AI engine; extended by agents and admin actions.

| Field | Type | Notes |
|-------|------|-------|
| attorney_status | string | see status enum above |
| driver_id | string | FK → drivers |
| driver_full_name | string | denormalized |
| driver_cdl | string | denormalized |
| driver_dob | string | denormalized |
| driver_address | string | denormalized |
| violation_category | string | |
| violation_description | string | |
| ticket_state | string | |
| ticket_county | string | |
| ticket_city | string | |
| ticket_city_state | string | "City, ST" formatted |
| court_date | string | |
| date_of_ticket | string | |
| citation_number | string | |
| name | string | citation_number or ticket_id |
| region | string | ticket_state |
| source | string | manual \| driver_upload |
| ai_scan_id | string | FK → ai_scans |
| pass_status | string | green \| yellow \| red |
| price_display | string | |
| price_low | number | |
| price_high | number | |
| reviewed_by | string | staff_id — set on approve |
| reviewed_at | timestamp | set on approve |
| rejection_reason | string | set on reject |
| created_at | timestamp | |
| last_modified_date | timestamp | |
| **Agent outputs** | | written by pipeline agents after every scan |
| urgency_level | string | CRITICAL \| HIGH \| STANDARD \| LOW (urgency_router) |
| urgency_reason | string | human-readable explanation of urgency |
| completeness_score | number | 0.0–1.0 (document_completeness agent) |
| missing_fields | array | field names missing from extraction |
| driver_profile | map | see sub-fields below (pii_match agent) |
| driver_profile.driver_id | string | |
| driver_profile.status | string | active \| inactive \| not_found |
| driver_profile.cdl_match | string | match \| mismatch \| unverified |
| driver_profile.profile_cdl | string | CDL on file in drivers/ |
| driver_profile.ticket_cdl | string | CDL extracted from ticket image |
| driver_profile.driver_name_on_file | string | |
| statement_of_record | map | see sub-fields below (statement_of_record agent) |
| statement_of_record.officer_account | map | extracted ticket fields as officer's stated account |
| statement_of_record.driver_account | map | 9-field driver statement from upload form |
| statement_of_record.driver_account.location_when_stopped | string | |
| statement_of_record.driver_account.action_at_time | string | |
| statement_of_record.driver_account.weather_conditions | string | |
| statement_of_record.driver_account.road_signs_visible | string | |
| statement_of_record.driver_account.your_speed | string | |
| statement_of_record.driver_account.officer_stated_violation | string | |
| statement_of_record.driver_account.had_dashcam | string | |
| statement_of_record.driver_account.other_witnesses | string | |
| statement_of_record.driver_account.dispute_ticket_details | string | |
| statement_of_record.conflict_map | array | list of field-level conflict objects |
| statement_of_record.evidence_index | array | evidence files tagged to conflicts |
| statement_of_record.conflict_count | number | |
| statement_of_record.evidence_count | number | |
| statement_of_record.uncategorized_evidence | number | evidence files not linked to a conflict |
| mvr_request | map | Motor Vehicle Record pull metadata (mvr_request agent) |
| mvr_request.status | string | pending \| complete \| skipped |
| mvr_request.driver_name | string | |
| mvr_request.cdl_number | string | |
| mvr_request.cdl_state | string | |
| mvr_request.requested_at | string | ISO timestamp |
| mvr_request.scan_id | string | |
| mvr_request.note | string | |
| psp_request | map | FMCSA PSP report pull metadata (psp_request agent) |
| psp_request.status | string | pending \| complete \| skipped |
| psp_request.driver_name | string | |
| psp_request.cdl_number | string | |
| psp_request.driver_dob | string | |
| psp_request.requested_at | string | ISO timestamp |
| psp_request.scan_id | string | |
| psp_request.report_type | string | "PSP" |
| psp_request.fmcsa_dataset | string | "MCMIS" |
| psp_request.covers | map | {crash_history_years: 5, inspection_violation_years: 3} |
| psp_request.consent_required | boolean | always true per 49 CFR 391.23 |
| psp_request.note | string | |
| **Outcome fields** | | written by /operations/record-outcome |
| outcome | string | won \| dismissed \| reduced \| lost \| transferred |
| outcome_notes | string | free text from attorney |
| final_charge | string | if reduced — what the final charge was |
| closed_by_attorney_id | string | |
| closed_by_attorney_name | string | |
| closed_at | timestamp | |

---

### `attorneys/{attorney_id}`
> CDL defense attorneys. `firebase_uid` is null until attorney portal is activated.

| Field | Type | Notes |
|-------|------|-------|
| firebase_uid | string | null until attorney gets portal login |
| application_id | string | FK → attorney_applications |
| full_name | string | |
| bar_number | string | null for law students |
| bar_state | string | primary state of licensure |
| firm_name | string | nullable |
| institution | string | law school name — law_student tier only |
| phone | string | |
| email | string | |
| states_licensed | array | 2-letter codes |
| counties_covered | array | "State:County" format e.g. "TX:Harris" |
| years_experience | number | |
| tier | string | senior \| junior \| law_student |
| supervising_attorney_id | string | FK → attorneys; required for law_student |
| nonprofit_eligible | boolean | true for law_student tier |
| max_active_cases | number | senior: 999, junior: 5, law_student: 2 |
| cases_active | number | current count |
| cases_total | number | lifetime count |
| win_rate | number | 0.0–1.0; updated on case close |
| preferred_contact_method | string | phone \| email \| text |
| payout_method | string | check \| ach \| venmo \| zelle |
| payout_details | string | routing info, handle, or mailing address |
| verified_at | timestamp | when RR verified credentials |
| verified_by | string | staff_id |
| status | string | active \| suspended \| inactive |
| created_at | timestamp | |

---

### `attorney_applications/{application_id}`
> Tracks attorney onboarding pipeline before an attorneys/ doc is created.

| Field | Type | Notes |
|-------|------|-------|
| applicant_name | string | |
| email | string | |
| phone | string | |
| years_experience | number | |
| bar_number | string | null if law student |
| states_applying_for | array | |
| tier_track | string | senior \| junior \| law_student |
| institution | string | law school — law_student only |
| supervising_attorney_id | string | law_student only |
| resume_url | string | Firebase Storage URL |
| bar_cert_url | string | Firebase Storage URL; nullable |
| interview_date | timestamp | nullable |
| interviewed_by | string | staff_id |
| interview_notes | string | |
| status | string | pending \| interview_scheduled \| under_review \| approved \| rejected |
| rejection_reason | string | nullable |
| attorney_id | string | FK → attorneys; set when approved |
| created_at | timestamp | |
| updated_at | timestamp | |

---

### `cases/{case_id}`
> One case per ticket. Created by admin when assigning to attorney.

| Field | Type | Notes |
|-------|------|-------|
| ticket_id | string | FK → tickets |
| attorney_id | string | FK → attorneys |
| assigned_by | string | staff_id |
| assigned_at | timestamp | |
| status | string | see cases.status enum |
| contact_method | string | phone \| email \| text |
| contacted_at | timestamp | |
| attorney_response_at | timestamp | |
| next_followup_date | timestamp | admin sets after each contact |
| outcome | string | see cases.outcome enum |
| outcome_notes | string | free text |
| outcome_state | string | state where outcome was rendered |
| closed_at | timestamp | |
| last_updated_by | string | staff_id |
| last_updated_at | timestamp | |
| created_at | timestamp | |
| **Denormalized for display** | | |
| attorney_name | string | copied from attorneys/ |
| attorney_phone | string | copied from attorneys/ |
| driver_name | string | copied from tickets/ |
| violation | string | copied from tickets/ |
| ticket_state | string | copied from tickets/ |
| court_date | string | copied from tickets/ |

**Subcollection:** `cases/{case_id}/activity/{activity_id}`

---

### `cases/{case_id}/activity/{activity_id}`
> Full audit log of every admin action on a case. Never deleted.

| Field | Type | Notes |
|-------|------|-------|
| type | string | assigned \| contacted \| attorney_update \| status_change \| outcome_logged \| payout_created \| note_added |
| note | string | free text — what happened, what attorney said |
| old_status | string | on status_change type |
| new_status | string | on status_change type |
| created_by | string | staff_id |
| created_by_name | string | denormalized for display |
| created_at | timestamp | |

---

### `ai_scans/{scan_id}`
> Full AI pipeline output per scan. `scan_id` = `ai_scan_id` on tickets/.

| Field | Type | Notes |
|-------|------|-------|
| ticket_id | string | FK → tickets |
| raw_ocr_text | string | Cloud Vision output (phase 2; null for now) |
| pass_1_result | map | full Lone Ranger pass 1 extraction |
| pass_2_result | map | full Lone Ranger pass 2 extraction; null if GREEN |
| consensus_result | map | merged output; null if GREEN |
| referee_1_score | string | green \| yellow \| red |
| referee_2_score | string | after consensus; null if GREEN |
| dual_conflicts | array | field names where passes disagreed |
| low_confidence_fields | array | fields Referee flagged |
| final_pass_status | string | green \| yellow \| red |
| prompt_version | string | e.g. "v2" |
| model_version | string | Claude model used |
| processing_time_ms | number | |
| created_at | timestamp | |

---

### `ticket_corrections/{correction_id}`
> Human corrections to AI extractions. Primary training signal.

| Field | Type | Notes |
|-------|------|-------|
| scan_id | string | FK → ai_scans |
| ticket_id | string | FK → tickets |
| field_name | string | Salesforce-style field key e.g. "Court_Date__c" |
| ai_value | string | what the AI extracted |
| corrected_value | string | what the human set it to |
| correction_source | string | staff \| attorney \| driver |
| corrected_by | string | staff_id or attorney_id |
| referee_score_at_time | string | GREEN \| YELLOW \| RED |
| corrected_at | timestamp | |

---

### `subscriptions/{subscription_id}`

| Field | Type | Notes |
|-------|------|-------|
| driver_id | string | FK → drivers |
| plan_id | string | FK → plans |
| carrier_id | string | FK → carriers; null if self-pay |
| billing_type | string | carrier \| self \| payroll |
| status | string | active \| cancelled \| past_due |
| monthly_amount | number | snapshot of price at signup |
| safe_driver_rate_applied | boolean | true = paying discounted safe driver price |
| tickets_used | number | current year count |
| tickets_allowed | number | from plan |
| started_at | timestamp | |
| cancelled_at | timestamp | nullable |
| next_billing_date | timestamp | |
| stripe_subscription_id | string | null until Stripe wired |
| created_at | timestamp | |

---

### `plans/{plan_id}`
> Subscription tiers. Two driver plans. Carrier pricing is quoted, not tiered.

| Field | Type | Notes |
|-------|------|-------|
| name | string | "RigResolve Core" \| "RigResolve Pro" |
| tag | string | "$0 DEDUCTIBLE" \| "MOST COVERAGE" |
| monthly_price | number | standard monthly rate USD |
| safe_driver_price | number | 20% off — verified via PSP/MVR at signup |
| tickets_per_year | number | 999 = unlimited |
| features | array | list of included features |
| eligible_driver_types | array | carrier \| independent \| owner_operator |
| featured | boolean | true for Pro card UI highlight |
| active | boolean | |
| created_at | timestamp | |

**Seed data:**

| plan_id | name | monthly_price | safe_driver_price |
|---------|------|--------------|-------------------|
| `core` | RigResolve Core | $14.99 | $11.99 |
| `pro` | RigResolve Pro | $24.99 | $19.99 |

---

### `carrier_invoices/{invoice_id}`
> Monthly invoices sent to carriers. Managed manually by admins.

| Field | Type | Notes |
|-------|------|-------|
| carrier_id | string | FK → carriers |
| billing_period_start | timestamp | |
| billing_period_end | timestamp | |
| active_driver_count | number | snapshot at billing time |
| amount_due | number | USD |
| amount_paid | number | USD; 0 until paid |
| status | string | pending \| paid \| overdue \| voided |
| due_date | timestamp | |
| paid_at | timestamp | nullable |
| payment_method | string | check \| ach \| wire |
| reference_number | string | check # or transfer ID |
| notes | string | |
| created_by | string | staff_id |
| created_at | timestamp | |

---

### `attorney_payouts/{payout_id}`
> Manual payment records to attorneys. Created by admin after outcome is logged.

| Field | Type | Notes |
|-------|------|-------|
| case_id | string | FK → cases |
| attorney_id | string | FK → attorneys |
| amount | number | USD |
| method | string | check \| ach \| venmo \| zelle |
| reference_number | string | check #, transfer ID, or transaction ref |
| status | string | pending \| paid \| failed |
| notes | string | |
| created_by | string | staff_id who created the payout |
| created_at | timestamp | |
| paid_at | timestamp | nullable |
| paid_by | string | staff_id who confirmed payment sent |

> **Future:** add `stripe_transfer_id` or `rainforest_payment_id` when payment automation is added.

---

### `one_time_charges/{charge_id}`
> Non-member and PreX ticket handling. Driver does not have an active subscription.

| Field | Type | Notes |
|-------|------|-------|
| driver_id | string | FK → drivers; may be newly created |
| ticket_id | string | FK → tickets |
| charge_type | string | standalone \| join_and_save \| prex_negotiated \| prex_trial |
| amount | number | standalone: $299 \| join_and_save: $249 \| prex_negotiated: $399 \| prex_trial: $599 |
| prex_hours_included | number | 4 for prex_trial; null otherwise |
| prex_hourly_overage | number | $150/hr beyond included hours for prex_trial |
| converted_to_member | boolean | true if driver signed up for Core or Pro same day |
| subscription_id | string | FK → subscriptions; set if converted_to_member |
| status | string | pending \| paid \| refunded |
| paid_at | timestamp | nullable |
| stripe_payment_intent_id | string | null until Stripe wired |
| notes | string | |
| created_by | string | staff_id |
| created_at | timestamp | |

**Charge type rates:**
| charge_type | amount | description |
|-------------|--------|-------------|
| `standalone` | $299 | One-time, no membership |
| `join_and_save` | $249 | Joins Core or Pro same day |
| `prex_negotiated` | $399 | Pre-existing ticket, negotiated resolution |
| `prex_trial` | $599 | Pre-existing ticket, goes to trial; 4 hrs included, $150/hr beyond |

---

### `courts/{court_id}`
> Court/jurisdiction reference data. Built case-by-case. Future API product.

| Field | Type | Notes |
|-------|------|-------|
| state | string | 2-letter code |
| county | string | |
| court_name | string | |
| address | string | |
| phone | string | |
| appearance_required | boolean | CDL holders must appear in person |
| filing_deadline_days | number | days before court date to file |
| cdl_friendly | boolean | court is known to be favorable to CDL defense |
| notes | string | free text — procedures, quirks, contacts |
| data_source | string | staff \| attorney_contributed \| purchased |
| last_verified_at | timestamp | |
| verified_by | string | staff_id or attorney_id |
| confidence_score | number | 0.0–1.0 |
| created_at | timestamp | |

---

### `violations/{violation_id}`
> CDL violation code reference. Built case-by-case. Future API product.

| Field | Type | Notes |
|-------|------|-------|
| state | string | 2-letter code |
| code | string | state violation code |
| description | string | |
| category | string | matches Violation_Category__c values |
| cdl_points | number | points assessed against CDL |
| disqualification_risk | boolean | can trigger CDL disqualification |
| severity | string | low \| medium \| high |
| federal_code | string | FMCSA code if applicable |
| state_statute_ref | string | e.g. "TX TRC 545.351" |
| data_source | string | staff \| attorney_contributed \| purchased |
| last_verified_at | timestamp | |
| confidence_score | number | 0.0–1.0 |
| created_at | timestamp | |

---

## Collection Summary

| # | Collection | Status | Notes |
|---|-----------|--------|-------|
| 1 | `tickets/` | Existing | Extended with agent outputs + outcome fields |
| 2 | `drivers/{id}/tickets/` | Existing | Extended with outcome fields |
| 3 | `drivers/{id}/notifications/` | New subcollection | Driver Concierge in-app messages |
| 4 | `staff/` | New — seed 3 docs | Quest, Eniola, Justin |
| 5 | `carriers/` | New | per_driver_rate starts $9.00 |
| 6 | `drivers/` | New | safe_driver_verified, subscription_end_date |
| 7 | `attorneys/` | New | firebase_uid null until portal live |
| 8 | `attorney_applications/` | New | |
| 9 | `cases/` | New | |
| 10 | `cases/{id}/activity/` | New subcollection | Audit log, never deleted |
| 11 | `ai_scans/` | New | |
| 12 | `ticket_corrections/` | New | Primary AI training signal |
| 13 | `subscriptions/` | New | safe_driver_rate_applied field added |
| 14 | `plans/` | New — seed 2 docs | Core $14.99/$11.99 · Pro $24.99/$19.99 |
| 15 | `carrier_invoices/` | New | per_driver_rate × active_driver_count |
| 16 | `attorney_payouts/` | New | Manual MVP; automate later |
| 17 | `one_time_charges/` | New | Standalone $299, join+save $249, PreX $399–$599 |
| 18 | `courts/` | New — build over time | Future API product |
| 19 | `violations/` | New — build over time | Future API product |

**Total: 19 collections (2 existing extended, 17 new)**

---

## Open Items

| Item | Status |
|------|--------|
| Firebase Auth accounts for Quest, Eniola, Justin | Must create before seeding staff/ |
| CTA destinations for "Start Core" / "Start Pro" | Pricing page — signup flow TBD |
| CTA destination for "Request your fleet quote" | Form, Calendly, or email TBD |
| Safe Driver PSP/MVR pull timing (before or after card capture) | Affects provisional vs. guaranteed rate display |
| Legal review of "VS. CDL LEGAL" competitive claim | Required before pricing page goes live publicly |
| Payment processor (Stripe vs. Rainforest Payments) | Affects stripe_* fields — add rainforest_* equivalent when decided |

---

## AI Pipeline — Agent Outputs on `tickets/{ticket_id}`

Pipeline order per scan:
```
case_intake → lone_ranger → referee →
  document_completeness → book_worm → pii_match →
  mvr_agent → psp_agent → research_ron → team_quest →
  urgency_router → sor_agent → assemble
```

### `jurisdiction_context` map — written by Research Ron

**Court + CDL fields**

| Field | Type | Notes |
|-------|------|-------|
| state | string | ticket state |
| county | string | |
| violation | string | violation category |
| is_serious_violation | boolean | CDL disqualification risk |
| is_major_violation | boolean | mandatory 1-year disqualification |
| disqualification_rule | string | null for minor violations |
| zone_notes | array | school/construction zone penalty notes |
| appearance_note | string | whether CDL holder must appear |
| attorney_timeline | string | deadline guidance from court date |
| court_system | string | from court_rulebook.json |
| state_portal | string | state court portal URL |
| county_court_name | string | |
| county_court_phone | string | |
| county_court_address | string | |
| county_scheduling_url | string | |
| state_notes | string | CDL-specific notes for this state |

**Carrier validation (FMCSA — motus_carriers.json)**

| Field | Type | Notes |
|-------|------|-------|
| carrier_dot_number | string | DOT# extracted from ticket |
| carrier_legal_name | string | |
| carrier_dba_name | string | |
| carrier_status | string | Active \| Inactive \| Revoked |
| carrier_active | boolean | |
| carrier_state | string | carrier home state |
| carrier_crash_count | number | crashes since 2000 (crash_by_dot.json) |
| carrier_fatal_count | number | fatalities since 2000 |
| carrier_note | string | human-readable summary for attorney display |

**National FMCSA inspection benchmarks (inspection_national_stats.json)**

| Field | Type | Notes |
|-------|------|-------|
| national_violation_rate | number | 0.0–1.0; most recent year (~0.59) |
| national_oos_rate | number | 0.0–1.0; most recent year (~0.22) |

**Phase 2 corpus patterns (violation_corpus.json — Kaggle CDL data)**

| Field | Type | Notes |
|-------|------|-------|
| corpus_count | number | CDL records for this state+category; null if no corpus hit |
| corpus_citation_rate | number | 0.0–1.0 citation rate |
| corpus_top_counties | array | highest-citation counties |
| corpus_county_rank | number | percentile rank for this ticket's county |
| corpus_defense_note | string | pattern-based defense suggestion |
| corpus_high_risk | boolean | citation_rate > 0.7 |

---

## Operational Endpoints (`/api/v1/operations/`)

All protected by `x-api-key` header. Cron targets for Cloud Scheduler.

| Endpoint | Method | Cron | Purpose |
|----------|--------|------|---------|
| `/operations/court-deadlines` | POST | Daily 8am | Court date work queue + driver reminders |
| `/operations/record-outcome/{ticket_id}` | POST | On demand | Records outcome, dual-writes, notifies driver |
| `/operations/payment-alerts` | GET | Daily | Lapsed/expiring subscription alerts |
| `/operations/case-status` | GET | On demand | Unified case manager queue; `?state=TX&urgency=CRITICAL` |

---

*Schema version: 1.2 — Rig Resolve QA — Updated 2026-06-26*  
*Changes from v1.1: added jurisdiction_context sub-map (carrier validation, FMCSA crash history, national inspection benchmarks, Phase 2 corpus patterns); added Operational Endpoints section; documented full agent pipeline order.*
