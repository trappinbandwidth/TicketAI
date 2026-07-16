# TIP OS WP-13 — Analytics and Data Quality

## Delivered

- Operational indicators for connector and document success, overdue work,
  critical signals, authorization shadow matching, and webhook delivery.
- Explicit denominators and cohort sizes for every rate.
- Configurable minimum cohort suppression to prevent small-group disclosure.
- Tenant-scoped snapshots containing aggregate operational values only.
- Declarative data-quality rules for required fields and freshness.
- Persisted quality results with record identifiers and failure reasons, but no
  raw record payloads or direct personal identifiers.
- Staff-only APIs to create snapshots and execute quality gates.

## Guardrails

- `TIP_OS_ANALYTICS_ENABLED` remains off by default.
- Empty populations return an explicit null rate, never a fabricated 0% or
  100%.
- Quality failures identify the affected record and rule, not copied PII.
- Analytics snapshots are operational—not legal conclusions, driver scores, or
  automated employment decisions.

