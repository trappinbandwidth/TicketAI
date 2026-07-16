"""Cross-cutting HTTP security controls."""
from __future__ import annotations

import os
import re
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex}"
        max_bytes = int(os.getenv("MAX_REQUEST_BYTES", str(25 * 1024 * 1024)))
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > max_bytes:
                    return JSONResponse(
                        {"detail": "Request body too large.", "request_id": request_id},
                        status_code=413,
                        headers={"X-Request-ID": request_id},
                    )
            except ValueError:
                return JSONResponse(
                    {"detail": "Invalid Content-Length.", "request_id": request_id},
                    status_code=400,
                    headers={"X-Request-ID": request_id},
                )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        if request.url.scheme == "https" or os.getenv("APP_ENV", "").lower() in {"prod", "production"}:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


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
