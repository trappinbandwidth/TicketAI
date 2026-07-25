# Recommendation Contract

Rig Resolve should not merely extract data. It should explain:

1. What happened
2. Why it matters
3. What to do next

The Recommendation Contract gives every product surface a stable shape for that
explainable intelligence.

## Schema

```json
{
  "id": "rec_...",
  "type": "dataq_opportunity",
  "version": "1.0",
  "subject_type": "ticket|driver|carrier|case|inspection|payment|document",
  "subject_id": "ticket_123",
  "audience": "driver|carrier|attorney|staff|system",
  "summary": "...",
  "why_it_matters": "...",
  "recommended_action": "...",
  "model_confidence": 0.91,
  "severity": "low|medium|high|critical",
  "status": "pending_review|approved|dismissed|acted_on|expired",
  "requires_human_approval": true,
  "evidence": [
    {
      "source_type": "ticket|inspection|mvr|psp|court|ai_extraction|human_note",
      "source_id": "...",
      "excerpt": "...",
      "field": "violation_description",
      "confidence": 0.95
    }
  ],
  "reasoning_summary": "...",
  "created_by": "document_intelligence|legal_intelligence|compliance_intelligence|financial_intelligence|system",
  "created_at": "server_timestamp",
  "expires_at": null
}
```

`model_confidence` describes the recommendation process; it is not Passport
`confidence_percent`, legal-success probability, record-removal probability,
employment likelihood, or insurance likelihood. Current stored records that use
the legacy `confidence` field retain it until an approved compatibility change;
new Transportation Intelligence contracts use the unambiguous name.

Evidence must reference an authorized SourceRecord/normalized fact or another
documented source. Generated reasoning cannot cite itself.

## Recommendation Types

Driver-facing:

- `ticket_translation`
- `court_deadline_warning`
- `cdl_risk_alert`
- `subscription_lapse_warning`
- `medical_card_expiration`
- `mvr_psp_explanation`
- `safe_driver_discount_eligible`
- `passport_completion_action`
- `record_verification_action`
- `record_restoration_candidate`
- `career_improvement_action`

Attorney-facing:

- `case_fit_recommendation`
- `court_context_summary`
- `defense_strategy_prompt`
- `missing_document_request`
- `case_law_research_prompt`

Carrier-facing:

- `driver_risk_alert`
- `dataq_opportunity`
- `inspection_challenge_candidate`
- `coverage_gap_alert`
- `fleet_compliance_trend`

Staff/internal:

- `ai_review_needed`
- `cdl_mismatch_review`
- `attorney_match_recommendation`
- `payout_review_needed`
- `carrier_onboarding_risk`

## Storage

Phase 1 stores recommendations in:

```text
recommendations/{recommendation_id}
```

Later denormalized views may be added:

```text
drivers/{driver_id}/recommendations/{recommendation_id}
carriers/{carrier_id}/recommendations/{recommendation_id}
cases/{case_id}/recommendations/{recommendation_id}
```

## Current Implementation

The AI engine defines the Pydantic model in `app/models/response.py` and writes
recommendations through `app/services/recommendation_service.py`.

Current recommendation writes:

- `court_deadline_warning` from urgency output
- `attorney_match_recommendation` from attorney matching output

These current writes are not proof that Passport, TIS, record restoration,
monitoring, or career coaching is implemented. Capability maturity controls
whether a recommendation type may be shown to users.

Recommendation creation also emits `recommendation.created`.
