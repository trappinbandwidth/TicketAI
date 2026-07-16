# TIP OS WP-09 — Captain and Administration

## Delivered

- A staff-only operations summary for document security, failed processing,
  overdue tasks, high-risk signals, organization and attorney verification,
  authorization mismatches, and integration health.
- Versioned feature-flag changes with optimistic concurrency, a mandatory
  reason, actor attribution, tenant/cohort/role targeting, and audit events.
- Time-bound privileged access sessions requiring a purpose and support-ticket
  reference. Sessions expire after 5–60 minutes and create an audit event.
- Captain Trust Center views for the operations queues and connector health,
  plus an audited privileged-access form.

## Safety controls

- The API is unavailable unless `TIP_OS_ADMIN_CONSOLE_ENABLED=true`.
- Every endpoint requires a verified Firebase staff role.
- This package does not enable any TIP OS feature flag.
- No production data migration, feature activation, or deployment is performed
  by this package.

## Verification

- Backend platform/admin, identity, workflow, and intelligence tests pass.
- Captain/Admin production TypeScript and Vite build passes.

