from dotenv import load_dotenv
from pathlib import Path
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.process import router
from app.routes.queue import router as queue_router
from app.routes.pricing import router as pricing_router
from app.routes.admin import router as admin_router
from app.routes.operations import router as operations_router
from app.routes.cases import router as cases_router
from app.routes.users_admin import router as users_admin_router
from app.routes.bids import router as bids_router
from app.routes.attorneys import router as attorneys_router
from app.routes.attorney_actions import router as attorney_actions_router
from app.routes.stripe_webhooks import router as stripe_webhooks_router
from app.routes.file_requests import router as file_requests_router
from app.services.queue_store import init_db
from app.services.firebase_service import _init as init_firebase

logger = logging.getLogger(__name__)


def _check_env() -> None:
    warnings: list[str] = []

    if os.getenv("USE_MOCK", "true").lower() == "true":
        warnings.append(
            "USE_MOCK=true — AI engine is in mock mode. "
            "Set USE_MOCK=false and provide ANTHROPIC_API_KEY to process real tickets."
        )
    elif not os.getenv("ANTHROPIC_API_KEY", ""):
        warnings.append(
            "ANTHROPIC_API_KEY is not set — ticket processing will fail. "
            "Add your Anthropic API key to .env."
        )

    has_sa_json  = bool(os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip())
    has_project  = bool(os.getenv("FIREBASE_PROJECT_ID", "").strip())
    if not has_sa_json and not has_project:
        warnings.append(
            "Firebase not configured — scan results will NOT be written to Firestore. "
            "Set FIREBASE_SERVICE_ACCOUNT_JSON (or FIREBASE_PROJECT_ID for ADC) in .env."
        )

    api_key = os.getenv("API_KEY", "")
    if api_key == "cdl-local-dev":
        warnings.append(
            "API_KEY is still the default 'cdl-local-dev'. "
            "Set a strong API_KEY in .env before deploying to production."
        )

    for w in warnings:
        logger.warning("[startup] CONFIGURATION WARNING: %s", w)

    if not warnings:
        logger.warning("[startup] Environment OK — all required credentials present.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _check_env()
    init_db()
    init_firebase()
    yield


app = FastAPI(
    title="Rig Resolve — AI Ticket Engine",
    description="Multimodal document processing for CDL traffic tickets.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
app.include_router(queue_router, prefix="/api/v1")
app.include_router(pricing_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(operations_router, prefix="/api/v1")
app.include_router(cases_router, prefix="/api/v1")
app.include_router(users_admin_router, prefix="/api/v1")
app.include_router(bids_router, prefix="/api/v1")
app.include_router(attorneys_router, prefix="/api/v1")
app.include_router(attorney_actions_router, prefix="/api/v1")
app.include_router(stripe_webhooks_router, prefix="/api/v1")
app.include_router(file_requests_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok", "service": "ai-ticket-engine"}
