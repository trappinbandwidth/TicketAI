# TIP OS WP-08 — Carrier and Safety Resolve

Safety Resolve is a governed view over driver-owned data. Access requires all three conditions:

1. An active carrier organization membership.
2. An active driver-carrier relationship.
3. Active, purpose-specific `safety_compliance` consent.

The shared projection returns only consented profile, credential, employment, and inspection records; credential/DataQs workflows; their tasks; and signals with safety, compliance, credential, or employment impact. Legal cases, defense strategy, attorney activity, and privileged content are excluded by construction.

The Carrier frontend adds a Safety Resolve command center for exceptions, source-backed compliance deadlines, and corrective tasks. When consent or the relationship ends, the API immediately denies the driver summary. Existing roster, FMCSA, billing, documents, and subscription tools remain intact.

The API and frontend are disabled unless `TIP_OS_CARRIER_RESOLVE_ENABLED=true`. Tests cover missing membership denial and exclusion of legal records, workflows, and signals. The Carrier production build passes.
