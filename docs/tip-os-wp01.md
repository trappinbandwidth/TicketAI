# TIP OS WP-01 — Shared Trust Foundation

WP-01 introduces additive canonical identity, organization membership, consent,
authorization, and audit primitives. Existing ticket and portal routes do not
depend on these primitives yet.

## Safety boundary

`TIP_OS_IDENTITY_ENABLED` defaults to `false`. When disabled, every
`/api/v1/platform/*` endpoint returns `404`, while existing routes behave as
before. Enable the flag only for an approved dark-launch environment or cohort.

## Collections

- `principals`
- `organizations`
- `organization_memberships`
- `consent_grants`
- `audit_events`

Existing role profile documents receive only additive `principal_id` and
`migration_version` links during bootstrap.

## Endpoints

All endpoints require a verified Firebase Bearer token.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/api/v1/platform/identity/bootstrap` | Idempotently create/link canonical principal |
| GET | `/api/v1/platform/me` | Read caller principal |
| GET | `/api/v1/platform/me/memberships` | Read caller memberships |
| POST | `/api/v1/platform/organizations` | Create pending organization |
| POST | `/api/v1/platform/organizations/bootstrap-current` | Idempotently create carrier/firm organization and administrator membership |
| GET | `/api/v1/platform/organizations/{id}` | Read authorized organization |
| POST | `/api/v1/platform/organizations/{id}/memberships` | Create membership as creator/staff |
| POST | `/api/v1/platform/consents` | Grant scoped consent for caller's records |
| GET | `/api/v1/platform/consents` | List caller consent history |
| POST | `/api/v1/platform/consents/{id}/revoke` | Revoke caller-granted consent |
| POST | `/api/v1/platform/authorization/evaluate` | Inspect server-side policy decision |

Business APIs must call the policy service internally. A frontend cannot grant
itself access by submitting an `allowed` decision from this diagnostic endpoint.

## Current policy

- Deny by default.
- Disabled principals are always denied.
- A principal can access their own record.
- Tenant access requires an active, unexpired membership in the same tenant.
- Terminal-scoped memberships cannot cross terminals.
- Another driver's protected records require active consent matching recipient,
  tenant, purpose, action, category, and expiration.
- Revoked consent cannot authorize access.

## Rollout

1. Deploy with the flag disabled.
2. Run idempotent dry-run/backfill reporting before mutating profile links.
3. Enable internal staff identities first.
4. Enable test attorney and carrier tenants.
5. Enable selected drivers.
6. Compare policy decisions in shadow mode.
7. Enforce the new policy on a business route only after negative permission
   tests and reconciliation pass.

No Claude or OpenAI runtime call is changed by WP-01.

## Identity backfill

The backfill defaults to report-only mode:

```bash
python scripts/tip_os_identity_backfill.py
```

The report contains hashed profile references, counts, outcomes and conflict
reasons. It does not print profile email, phone, CDL number, or raw Firebase UID.

Apply mode has two independent guards and refuses to run if any conflict or
invalid profile remains:

```bash
TIP_OS_BACKFILL_APPLY_ENABLED=true \
python scripts/tip_os_identity_backfill.py --apply --confirm TIP-OS-WP01
```

Each apply run writes `migration_runs/{id}` with aggregate counts and rollback
metadata. Each linked legacy profile preserves its previous principal link in
`migration_previous_principal_id`. Consent is never inferred or backfilled from
an employment record or legacy `consent_on_file` boolean.

## Shadow authorization

`app/platform/shadow.py` compares the current route decision with the new policy
decision and records the result under `authorization_shadow_comparisons`. Shadow
records always contain `enforced: false`; callers must continue honoring the
legacy decision until the rollout gate explicitly changes.

Set `TIP_OS_AUTH_SHADOW_ENABLED=true` only after the identity dry run has been
reviewed. Shadow failures are logged and never fail a business request.

Attorney case detail, activity reads, and activity writes are the first
instrumented boundary. Activity access now also requires assignment, claim, or
closure ownership; authentication alone is not sufficient to read or append
privileged case activity.

Before enforcement, review mismatch rates by action, resource type, tenant and
policy reason. A mismatch is an investigation signal, not permission to broaden
access.

Minimum rollout telemetry:

- comparison count and mismatch rate;
- `canonical_principal_missing` rate;
- matching-consent failure rate;
- mismatch rate by `read`, `read_activity`, and `write_activity`;
- shadow storage failures;
- request latency before and after shadow enablement.
