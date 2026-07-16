# TIP OS WP-02 — Canonical Records and Driver Cloud

## Objective

Provide an additive, source-aware Driver Cloud without replacing legacy ticket writes. Canonical records keep original source data, normalized facts, and derived conclusions in separate fields.

## Collections

- `canonical_records`: owner-scoped canonical records for profile, credential, document, employment, inspection, violation, case, training, and monitoring categories.
- `canonical_record_activity`: append-only create/update history.

Each record includes source provenance, status, record date, sharing scope, schema version, optimistic record version, and a SHA-256 hash of the raw payload.

## API

All routes require a verified Firebase ID token and `TIP_OS_RECORDS_ENABLED=true`.

- `GET /api/v1/driver-cloud/me`
- `POST /api/v1/driver-cloud/me/records`
- `PUT /api/v1/driver-cloud/me/records/{record_id}?expected_version=N`
- `GET /api/v1/driver-cloud/me/activity`

The API is owner-only in this work package. Carrier and attorney reads remain deny-by-default until their purpose-specific consent projections are introduced.

## Migration and rollout

1. Keep the flag disabled in production.
2. Backfill legacy data with `provenance.method=migration` and a stable legacy reference.
3. Reconcile counts, hashes, categories, and ownership.
4. Enable read views for a test cohort.
5. Migrate writes only after dual-read parity passes.

Rollback is disabling `TIP_OS_RECORDS_ENABLED`; existing ticket and portal collections are unchanged.

## Verification

Tests cover raw/normalized/derived separation, provenance, cross-driver denial, optimistic concurrency, activity history, and owner isolation.
