import importlib

from fastapi.testclient import TestClient

from app.main import app
from app.security import allowed_origins


def test_cors_never_defaults_to_wildcard(monkeypatch):
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    assert "*" not in allowed_origins()


def test_production_requires_explicit_origins(monkeypatch):
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    try:
        allowed_origins()
        assert False, "production must fail closed"
    except RuntimeError:
        pass


def test_security_headers_and_request_limit(monkeypatch):
    client = TestClient(app)
    response = client.get("/health", headers={"x-request-id": "req_test"})
    assert response.headers["x-request-id"] == "req_test"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"

    monkeypatch.setenv("MAX_REQUEST_BYTES", "10")
    rejected = client.post("/api/v1/process", content=b"x" * 11)
    assert rejected.status_code == 413


def test_stripe_webhook_fails_closed_without_secret(monkeypatch):
    module = importlib.import_module("app.routes.stripe_webhooks")
    monkeypatch.setattr(module, "WEBHOOK_SECRET", "")
    client = TestClient(app)
    response = client.post("/api/v1/webhooks/stripe", content=b"{}")
    assert response.status_code == 503
    assert "verification unavailable" in response.text
