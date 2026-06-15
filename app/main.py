from dotenv import load_dotenv
from pathlib import Path
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.process import router
from app.routes.queue import router as queue_router
from app.routes.pricing import router as pricing_router
from app.routes.admin import router as admin_router
from app.services.queue_store import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="CDL Legal — AI Ticket Engine",
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


@app.get("/health")
def health():
    return {"status": "ok", "service": "ai-ticket-engine"}
