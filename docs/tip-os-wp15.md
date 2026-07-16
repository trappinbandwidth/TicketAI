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

## Rollback

- Disable the affected cohort flag using its current version and a reason.
- Stop connector/worker dispatch; preserve source records and outboxes.
- Revert reads to legacy projections; do not delete canonical shadow data.
- Use compensating journals for financial corrections.
- Record incident, affected tenants, timestamps, and reconciliation evidence.

