"""Cross-cutting HTTP security controls."""
from __future__ import annotations

import os
import re
import uuid

from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse


class SecurityHeadersMiddleware:
    """Pure ASGI middleware so multipart request streams are never consumed."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming_headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        request_id = incoming_headers.get("x-request-id") or f"req_{uuid.uuid4().hex}"
        max_bytes = int(os.getenv("MAX_REQUEST_BYTES", str(25 * 1024 * 1024)))
        content_length = incoming_headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > max_bytes:
                    response = JSONResponse(
                        {"detail": "Request body too large.", "request_id": request_id},
                        status_code=413,
                        headers={"X-Request-ID": request_id},
                    )
                    await response(scope, receive, send)
                    return
            except ValueError:
                response = JSONResponse(
                    {"detail": "Invalid Content-Length.", "request_id": request_id},
                    status_code=400,
                    headers={"X-Request-ID": request_id},
                )
                await response(scope, receive, send)
                return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "no-referrer"
                headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                headers["Cache-Control"] = "no-store"
                headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
                if scope.get("scheme") == "https" or os.getenv("APP_ENV", "").lower() in {"prod", "production"}:
                    headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            await send(message)

        await self.app(scope, receive, send_with_headers)


def allowed_origins():
    configured = [
        value.strip()
        for value in re.split(r"[,|]", os.getenv("CORS_ALLOWED_ORIGINS", ""))
        if value.strip()
    ]
    if configured:
        return configured
    if os.getenv("APP_ENV", "development").lower() in {"prod", "production"}:
        raise RuntimeError("CORS_ALLOWED_ORIGINS is required in production.")
    return ["http://localhost:5173", "http://127.0.0.1:5173"]
