# Transportation Intelligence Platform — Backend Plan

The Engine is the authoritative TIP `/api/v1` backend and AI pipeline. It does
not replace FMCSA, DMV, PSP, DataQs, Clearinghouse, court, or professional
records. It stores immutable source evidence, normalized facts, and reproducible
role projections above those sources.

## Required backend domains

1. **Capability registry** — maturity, supported roles/sources, limitations,
   support owner, and release evidence.
2. **Consent and relationships** — purpose, scope, subject, grantee, source,
   effective/expiry/revocation, and audit.
3. **Source records** — immutable protected artifact, hash, source class/system,
   jurisdiction, timestamps, verification, dispute, and supersession.
4. **Normalized facts** — typed/versioned facts reproducible from source records.
5. **Passport projections** — role-safe sections with completion, confidence,
   freshness, sources, issues, actions, challenges, and optional score snapshot.
6. **Score engine** — versioned 300–850 TIS snapshots, grades, inputs,
   exclusions, categories, explanations, confidence, review/publication,
   dispute, withdrawal, and recalculation.
7. **Restoration** — issue, eligibility, evidence, cited draft, review,
   submission, response, outcome, monitoring, and audit.
8. **Monitoring** — connector cursor, freshness SLO, change detection, retry,
   dead-letter, alert deduplication, and Support escalation.
9. **AI governance** — provider-neutral Anthropic/OpenAI telemetry, citations,
   fallback, disagreement, review, quality, latency, and cost.
10. **Marketplace/wallet** — capability-gated offers and PCI-provider ledger;
    never raw payment credentials.

## Security and reliability

- Bearer-token subject and tenant are authoritative; request fields cannot
  select a different owner.
- Driver records default to Driver-only. Carrier/Attorney/Captain access uses a
  current purpose-bound relationship and minimum projection.
- Sensitive/raw artifacts use protected object storage and short-lived,
  authorized delivery.
- Mutation endpoints require idempotency, audit, replay safety, partial-failure
  recovery, and rollback.
- Passport and score projections rebuild from immutable source/fact versions
  and reconcile with zero unexplained differences.

## Current versus planned

Current Engine capabilities include Driver profile/ticket/document boundaries,
Carrier APIs, document extraction through Anthropic/OpenAI, and operational
routes. They are inputs to future intelligence domains, not proof that Passport,
TIS, monitoring, restoration, Copilot, marketplace, or wallet is implemented.

Existing safety/risk/CSA fields retain their schemas. No legacy metric may be
written into a TIS snapshot without an approved score version.

Canonical proposal:
`_coordination/contracts/CONTRACT-004-transportation-intelligence.md`.
First implementation dependency: `_coordination/tasks/TIP-FOUND-001.md`.
