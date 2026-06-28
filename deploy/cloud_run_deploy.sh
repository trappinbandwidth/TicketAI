#!/bin/bash
# One-time Cloud Run setup for ai-ticket-engine on GCP project: rigresolve
# Run this from the repo root after setting ANTHROPIC_API_KEY below.
#
# Prerequisites:
#   gcloud auth login
#   gcloud config set project rigresolve

set -euo pipefail

PROJECT_ID="rigresolve"
REGION="us-central1"
SERVICE_NAME="ai-ticket-engine"

# Read key from shell env, then fall back to .env file in repo root
ANTHROPIC_KEY="${ANTHROPIC_API_KEY:-}"
if [[ -z "$ANTHROPIC_KEY" ]] && [[ -f ".env" ]]; then
  ANTHROPIC_KEY=$(grep "^ANTHROPIC_API_KEY=" .env | head -1 | cut -d= -f2-)
fi

if [[ -z "$ANTHROPIC_KEY" ]]; then
  echo "ERROR: ANTHROPIC_API_KEY not found in shell environment or .env"
  exit 1
fi

export PATH="$HOME/google-cloud-sdk/bin:$PATH"

echo "==> Enabling required APIs..."
gcloud services enable \
  run.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  --project="$PROJECT_ID"

echo "==> Storing ANTHROPIC_API_KEY in Secret Manager..."
echo -n "$ANTHROPIC_KEY" | gcloud secrets create ANTHROPIC_API_KEY \
  --data-file=- \
  --project="$PROJECT_ID" 2>/dev/null \
  || echo -n "$ANTHROPIC_KEY" | gcloud secrets versions add ANTHROPIC_API_KEY \
       --data-file=- --project="$PROJECT_ID"

echo "==> Granting Cloud Run default SA access to secrets and Firestore..."
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA}" \
  --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA}" \
  --role="roles/datastore.user"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA}" \
  --role="roles/cloudbuild.builds.builder"

echo "==> Deploying to Cloud Run (GCP builds the container — no local Docker needed)..."
gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --platform managed \
  --memory 2Gi \
  --cpu 2 \
  --timeout 600 \
  --concurrency 10 \
  --min-instances 0 \
  --max-instances 5 \
  --set-env-vars "FIREBASE_PROJECT_ID=${PROJECT_ID},USE_MOCK=false,PROMPT_VERSION=v2,API_KEY=collard-greens-rr-prod-2026" \
  --set-secrets "ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest" \
  --allow-unauthenticated

echo ""
echo "==> Done. Service URL:"
gcloud run services describe "$SERVICE_NAME" \
  --region "$REGION" --project "$PROJECT_ID" \
  --format="value(status.url)"

echo ""
echo "NOTE: --no-allow-unauthenticated means only requests with a valid"
echo "      Bearer token (or your API_KEY header) will be accepted."
echo "      To open it publicly: gcloud run services add-iam-policy-binding ..."
