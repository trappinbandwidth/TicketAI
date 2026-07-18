# TIP OS WP-03 — Document Intelligence

## Safety boundary

The new lifecycle is additive and disabled unless `TIP_OS_DOCUMENTS_ENABLED=true`. Uploads accept PDF, JPEG, and PNG up to 20 MB, validate magic bytes rather than trusting the declared MIME type, sanitize filenames, compute SHA-256 checksums, and detect owner-scoped duplicates.

Files are stored under the private `tip-os-quarantine/` prefix. `MALWARE_SCAN_URL` must return `clean` before extraction can begin. Missing, failed, or unrecognized scanner responses remain `scan_pending`; known unsafe content remains `unsafe`. The system never fails open.

## Lifecycle

`scan_pending -> ready -> classifying -> extracting -> review_required -> verified`

Unsafe and failed states are terminal until an authorized operational reprocessing workflow is introduced. Extraction cannot begin unless the document is `ready`. Every field retains confidence, page, bounding box, raw evidence, correction, and verification status.

## Providers

`DOCUMENT_AI_PROVIDER=anthropic|openai` selects the extraction provider. Anthropic remains the default. OpenAI uses the Responses API, sends image inputs, requests JSON, sets `store=false`, and records provider, model, token usage, and response ID. `OPENAI_DOCUMENT_MODEL` is configurable; no provider is silently substituted.

## API

- `POST /api/v1/documents`
- `GET /api/v1/documents`
- `GET /api/v1/documents/{id}`
- `POST /api/v1/documents/{id}/extract`
- `GET /api/v1/documents/jobs/{job_id}`
- `GET /api/v1/documents/extractions/{run_id}`
- `POST /api/v1/documents/extractions/{run_id}/verify`

All endpoints require a Firebase ID token and enforce document ownership. Extraction requests create idempotent, correlation-ID-bearing asynchronous jobs. Ingestion, queueing, extraction start, and verification emit audit events.

## Rollout

Keep the feature flag disabled until a production malware scanner, private bucket rules, retention policy, background worker, and operational quarantine queue are verified. Existing `/process` intake remains the compatibility path during shadow rollout.
