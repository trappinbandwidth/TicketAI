# TIP OS WP-15 — Migration and Launch Readiness

## Progressive rollout

1. **Dark launch** — canonical writes, shadow authorization, and assessments
   only. All user-visible and consequential feature flags remain disabled.
2. **Internal** — approved staff identities and staging data only.
3. **Named cohort** — explicit tenant IDs, rollback rehearsal, staging E2E
   evidence, and authorization mismatch threshold satisfied.
4. **Production** — zero unresolved migration conflicts, balanced
   reconciliations, healthy integrations, passed quality threshold, and all
   security/operations evidence approved.

No assessment endpoint changes a feature flag. Flag changes remain a separate,
versioned, reason-coded Captain action.

## Required production evidence

- Successful staging E2E suite across driver, attorney, carrier, and Captain.
- Backup/restore exercise.
- Rollback rehearsal.
- Dependency/container/infrastructure security scans.
- Secret rotation evidence for Firebase, AI providers, Stripe, and connectors.
- Incident-response tabletop.
- Reconciled identity, canonical records, connector source records, and
  financial provider settlements.

## Current production migration facts

The most recent read-only dry runs found:

- Identity: 3,331 legacy profiles scanned; 3,331 proposed canonical creates;
  no conflicts or invalid profiles.
- Records: 148 tickets scanned; 10 safe creates; 138 invalid because an
  authoritative owner could not be established; no conflicts.

Therefore the records migration remains blocked. Do not infer ownership from
names, email fragments, CDL values, or portal location. Supply an approved
ticket-to-principal ownership mapping, rerun dry-run reconciliation, and require
zero invalid/conflicting records before applying.

The entity-resolution queue can now record scored, masked match evidence and a
recent-MFA human decision. It never auto-links a candidate and only permits a
reviewer to link a candidate that was included in the evaluated set.

Scoped delegated-access grants are time-bound, purpose-bound, category/action
bound, resource-bound when requested, revocable by the grantor, and audited.
Consequential financial, feature-flag, privileged-access, and resolution
decisions require recent Firebase authentication and an MFA factor.

Both Anthropic and OpenAI keys are required by the deployment script and are
injected independently from Secret Manager. Technical fallback is disabled
unless `DOCUMENT_AI_FALLBACK_ENABLED=true`; when used it is recorded and forces
human review.

## Rollback

- Disable the affected cohort flag using its current version and a reason.
- Stop connector/worker dispatch; preserve source records and outboxes.
- Revert reads to legacy projections; do not delete canonical shadow data.
- Use compensating journals for financial corrections.
- Record incident, affected tenants, timestamps, and reconciliation evidence.
