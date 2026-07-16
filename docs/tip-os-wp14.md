# TIP OS WP-14 — Security, Privacy, and Reliability Hardening

## Delivered

- Stripe webhook verification is fail-closed; unsigned events and missing
  webhook configuration are rejected.
- Stripe processing failures return retryable server errors without exposing
  internal exception text.
- TenStreet and Workday webhooks already fail closed from WP-10.
- Explicit browser-origin allowlists replace wildcard CORS. Production startup
  fails if `CORS_ALLOWED_ORIGINS` is absent.
- Request correlation IDs, request-size enforcement, no-store behavior, HSTS
  in production, clickjacking protection, MIME sniffing protection, restrictive
  referrer/permissions policy, and an API-safe content security policy.
- AI provider logging no longer emits any API-key prefix.
- Production startup already rejects the shared development API key.

## Required production configuration

- `CORS_ALLOWED_ORIGINS` — comma- or pipe-separated Rig Resolve frontend
  origins. The deploy script supplies the four Firebase portal origins.
- `STRIPE_WEBHOOK_SECRET` — injected from Secret Manager.
- `MAX_REQUEST_BYTES` — defaults to 25 MiB; lower per service where practical.
- Python 3.11 is used by the deployment container. The older local Python 3.9
  virtual environment should be replaced before relying on local dependency
  support warnings as production evidence.

## Remaining infrastructure evidence before launch

- Cloud Armor/rate-limit policy export.
- Secret Manager IAM and rotation evidence.
- Firestore backup/restore exercise and retention evidence.
- Dependency, container, and infrastructure scan reports.
- Incident response and breach-notification tabletop record.
