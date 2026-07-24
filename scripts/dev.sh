#!/usr/bin/env bash
# Local TIP OS stack — the replacement for a cloud staging project.
#
#   ./scripts/dev.sh emulators   # Firebase Auth + Firestore + Storage + UI
#   ./scripts/dev.sh seed        # synthetic data (needs emulators running)
#   ./scripts/dev.sh engine      # FastAPI with every TIP_OS_* flag ON
#
# Nothing here touches a real GCP project or costs money.
set -euo pipefail
cd "$(dirname "$0")/.."

# Forced (not defaulted): app/.env sets FIREBASE_PROJECT_ID=rigresolve for
# production, and load_dotenv(override=True) would win — making the engine
# verify tokens against the wrong project and reject every emulator login.
export FIREBASE_PROJECT_ID="rigresolve-local"
export FIRESTORE_EMULATOR_HOST="${FIRESTORE_EMULATOR_HOST:-localhost:8080}"
export FIREBASE_AUTH_EMULATOR_HOST="${FIREBASE_AUTH_EMULATOR_HOST:-localhost:9099}"
export FIREBASE_STORAGE_EMULATOR_HOST="${FIREBASE_STORAGE_EMULATOR_HOST:-localhost:9199}"
# Google Cloud Storage (used by firebase-admin) reads this host, including scheme.
export STORAGE_EMULATOR_HOST="${STORAGE_EMULATOR_HOST:-http://localhost:9199}"
# Synthetic local-only AES key. Production injects an independently generated
# key and version from Secret Manager; this value protects no real data.
export PII_ENCRYPTION_KEY_B64="${PII_ENCRYPTION_KEY_B64:-BwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwc=}"
export PII_ENCRYPTION_KEY_ID="${PII_ENCRYPTION_KEY_ID:-local-v1}"

case "${1:-}" in
  emulators)
    exec firebase emulators:start --project "$FIREBASE_PROJECT_ID"
    ;;

  seed)
    exec .venv/bin/python scripts/seed_local.py
    ;;

  engine)
    # USE_MOCK keeps Claude calls off unless a key is present — no AI spend
    # while building UI. Set USE_MOCK=false with a key to exercise the pipeline.
    export USE_MOCK="${USE_MOCK:-true}"
    export API_KEY="${API_KEY:-tipos-local-dev}"
    export APP_ENV="development"
    export CORS_ALLOWED_ORIGINS="http://localhost:5301|http://localhost:5302|http://localhost:5303|http://localhost:5304"
    for flag in \
      TIP_OS_IDENTITY_ENABLED TIP_OS_RECORDS_ENABLED TIP_OS_DOCUMENTS_ENABLED \
      TIP_OS_WORKFLOWS_ENABLED TIP_OS_INTELLIGENCE_ENABLED TIP_OS_ADMIN_CONSOLE_ENABLED \
      TIP_OS_CARRIER_RESOLVE_ENABLED TIP_OS_FINANCIAL_LEDGER_ENABLED \
      TIP_OS_ANALYTICS_ENABLED TIP_OS_INTEGRATIONS_ENABLED TIP_OS_PARTNER_API_ENABLED \
      TIP_OS_ENTITY_RESOLUTION_ENABLED TIP_OS_ATTORNEY_GOVERNANCE_ENABLED \
      TIP_OS_LAUNCH_ASSESSMENT_ENABLED TIP_OS_AUTH_SHADOW_ENABLED
    do export "$flag=true"; done
    exec .venv/bin/python -m uvicorn app.main:app --reload --port 8000
    ;;

  *)
    echo "usage: ./scripts/dev.sh {emulators|seed|engine}" >&2
    exit 1
    ;;
esac
