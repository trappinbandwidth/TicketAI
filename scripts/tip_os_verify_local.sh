#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

.venv/bin/pytest -q \
  tests/test_platform_identity.py \
  tests/test_platform_migration.py \
  tests/test_driver_cloud.py \
  tests/test_record_migration.py \
  tests/test_document_pipeline.py \
  tests/test_document_provider.py \
  tests/test_workflows.py \
  tests/test_intelligence.py \
  tests/test_driver_resolve.py \
  tests/test_attorney_case_access.py \
  tests/test_carrier_resolve.py \
  tests/test_platform_admin.py \
  tests/test_platform_integrations.py \
  tests/test_platform_ledger.py \
  tests/test_partner_api.py \
  tests/test_platform_analytics.py \
  tests/test_security.py \
  tests/test_platform_launch.py

echo "TIP OS backend verification passed."
echo "Production activation is not authorized by this result."
