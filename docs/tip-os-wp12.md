# TIP OS WP-12 — Partner APIs, Events, and Webhooks

## Delivered

- Versioned `/partner/v1` API surface with tenant-scoped event access.
- Partner clients with environment-specific scopes and one-time secret display.
- PBKDF2 secret hashing at rest and constant-time credential verification.
- Versioned domain events with tenant, aggregate, correlation, and occurrence
  metadata.
- Event-specific webhook subscriptions whose signing secrets are referenced
  from Secret Manager rather than stored in Firestore.
- Signed webhook payloads with event ID and timestamp headers.
- Durable delivery records, retry accounting, response truncation, and a
  dead-letter state after eight unsuccessful attempts.
- Staff-only client, subscription, and event-publication management endpoints.

## Safety and rollout

- `TIP_OS_PARTNER_API_ENABLED` remains off by default.
- Client secrets are shown once and never returned from subsequent reads.
- Partner credentials are tenant-bound; scopes are checked on every request.
- Webhook delivery transport remains an outbox operation so request handling
  never makes an uncontrolled partner network call.
- Production clients require a documented owner, data agreement, scopes, and
  staged webhook verification before activation.

