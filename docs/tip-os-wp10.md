# TIP OS WP-10 — Integrations and Connectors

## Delivered

- A common connector contract and versioned connector execution path.
- Immutable, content-addressed source records with provider provenance.
- Observable sync jobs with success/failure state, bounded errors, and a
  declared manual-upload fallback.
- Per-tenant integration health records consumed by the Captain console.
- Reconciliation reports that identify conflicting upstream snapshots for
  human review.
- A production-oriented FMCSA QCMobile adapter with official carrier lookup,
  key-based authentication, numeric USDOT validation, timeouts, and bounded
  retry behavior.
- Manual source submission that requires a reference, reason, and actor.
- Fail-closed TenStreet HMAC and Workday bearer webhook verification.

## Configuration

- Set `FMCSA_WEB_KEY` from Secret Manager at runtime.
- Set `TIP_OS_INTEGRATIONS_ENABLED=true` only in an approved test cohort.
- Keep the platform integrations flag off until connector credentials and
  reconciliation monitoring have been verified in staging.

## Safety

- Provider credentials are never returned in API responses or source records.
- Integration APIs require Firebase staff authorization.
- Failed syncs do not silently update canonical records.
- Conflicting snapshots require review; reconciliation never auto-selects a
  winner.

