"""WP-10 connector contracts, source records, sync jobs, and reconciliation."""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, Callable, Literal, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field

from app.platform.models import utc_now


class ConnectorRequest(BaseModel):
    connector_id: str = Field(pattern="^[a-z0-9_-]{3,80}$")
    tenant_id: str
    resource_type: str
    external_id: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class ManualSourceRecord(BaseModel):
    connector_id: str = "manual"
    tenant_id: str
    resource_type: str
    external_id: str
    payload: dict[str, Any]
    source_reference: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ReconciliationRequest(BaseModel):
    connector_id: str
    tenant_id: str
    resource_type: Optional[str] = None


class Connector(ABC):
    connector_id: str
    version: str

    @abstractmethod
    def fetch(self, request: ConnectorRequest) -> dict[str, Any]:
        raise NotImplementedError


class FmcsaQCMobileConnector(Connector):
    """Official FMCSA QCMobile carrier lookup with bounded retry behavior."""

    connector_id = "fmcsa_qc_mobile"
    version = "1"
    base_url = "https://mobile.fmcsa.dot.gov/qc/services"

    def __init__(
        self,
        web_key: Optional[str] = None,
        transport: Optional[Callable[[str, float], dict[str, Any]]] = None,
        timeout_seconds: float = 8.0,
        attempts: int = 3,
    ):
        self.web_key = web_key or os.getenv("FMCSA_WEB_KEY", "")
        self.transport = transport or self._request_json
        self.timeout_seconds = timeout_seconds
        self.attempts = attempts

    @staticmethod
    def _request_json(url: str, timeout: float):
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "RigResolve-TIP-OS/1"})
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def fetch(self, request: ConnectorRequest):
        if not self.web_key:
            raise RuntimeError("FMCSA_WEB_KEY is not configured.")
        dot = "".join(character for character in request.external_id if character.isdigit())
        if not dot:
            raise ValueError("A numeric USDOT number is required.")
        url = f"{self.base_url}/carriers/{dot}?{urlencode({'webKey': self.web_key})}"
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            try:
                result = self.transport(url, self.timeout_seconds)
                if not isinstance(result, dict):
                    raise RuntimeError("FMCSA returned a non-object response.")
                return result
            except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
                last_error = exc
                if attempt + 1 < self.attempts:
                    time.sleep(0.1 * (2 ** attempt))
        raise RuntimeError("FMCSA request failed after bounded retries.") from last_error


class IntegrationService:
    def __init__(self, db, connectors: Optional[dict[str, Connector]] = None):
        self.db = db
        self.connectors = connectors or {"fmcsa_qc_mobile": FmcsaQCMobileConnector()}

    @staticmethod
    def _id(prefix: str):
        return f"{prefix}_{uuid.uuid4().hex}"

    @staticmethod
    def _fingerprint(connector_id: str, tenant_id: str, resource_type: str, external_id: str, payload: dict):
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        value = "|".join((connector_id, tenant_id, resource_type, external_id, canonical))
        return hashlib.sha256(value.encode()).hexdigest()

    def _write_health(self, connector_id: str, tenant_id: str, status: str, **extra):
        health_id = hashlib.sha256(f"{connector_id}|{tenant_id}".encode()).hexdigest()[:32]
        value = {
            "id": health_id,
            "connector_id": connector_id,
            "tenant_id": tenant_id,
            "status": status,
            "checked_at": utc_now().isoformat(),
            **extra,
        }
        self.db.collection("integration_health").document(health_id).set(value, merge=True)
        return value

    def _store_source(
        self,
        connector_id: str,
        tenant_id: str,
        resource_type: str,
        external_id: str,
        payload: dict,
        sync_job_id: str,
        provenance: dict,
    ):
        fingerprint = self._fingerprint(connector_id, tenant_id, resource_type, external_id, payload)
        record_id = f"src_{fingerprint[:40]}"
        ref = self.db.collection("source_records").document(record_id)
        snapshot = ref.get()
        if getattr(snapshot, "exists", False):
            return snapshot.to_dict(), False
        value = {
            "id": record_id,
            "connector_id": connector_id,
            "tenant_id": tenant_id,
            "resource_type": resource_type,
            "external_id": external_id,
            "payload": payload,
            "payload_sha256": fingerprint,
            "sync_job_id": sync_job_id,
            "provenance": provenance,
            "received_at": utc_now().isoformat(),
            "status": "received",
        }
        ref.set(value)
        return value, True

    def run(self, body: ConnectorRequest, actor_id: str):
        connector = self.connectors.get(body.connector_id)
        if connector is None:
            raise LookupError("Unknown connector.")
        job_id = self._id("syn")
        started = utc_now().isoformat()
        job = {
            "id": job_id,
            "connector_id": body.connector_id,
            "connector_version": connector.version,
            "tenant_id": body.tenant_id,
            "resource_type": body.resource_type,
            "external_id": body.external_id,
            "status": "running",
            "attempt": 1,
            "started_at": started,
            "requested_by": actor_id,
        }
        ref = self.db.collection("sync_jobs").document(job_id)
        ref.set(job)
        try:
            payload = connector.fetch(body)
            source, created = self._store_source(
                body.connector_id, body.tenant_id, body.resource_type, body.external_id,
                payload, job_id, {"provider": body.connector_id, "connector_version": connector.version},
            )
            job.update({
                "status": "succeeded",
                "completed_at": utc_now().isoformat(),
                "source_record_id": source["id"],
                "source_record_created": created,
            })
            ref.set(job)
            self._write_health(
                body.connector_id, body.tenant_id, "healthy",
                last_success_at=job["completed_at"], last_sync_job_id=job_id, last_error=None,
            )
            return job, source
        except Exception as exc:
            job.update({
                "status": "failed",
                "completed_at": utc_now().isoformat(),
                "error_code": type(exc).__name__,
                "error": str(exc)[:500],
                "fallback": "manual_upload",
            })
            ref.set(job)
            self._write_health(
                body.connector_id, body.tenant_id, "degraded",
                last_failure_at=job["completed_at"], last_sync_job_id=job_id, last_error=job["error"],
            )
            raise RuntimeError(job["error"]) from exc

    def submit_manual(self, body: ManualSourceRecord, actor_id: str):
        job_id = self._id("syn")
        source, created = self._store_source(
            body.connector_id, body.tenant_id, body.resource_type, body.external_id,
            body.payload, job_id,
            {
                "provider": "manual",
                "source_reference": body.source_reference,
                "reason": body.reason,
                "submitted_by": actor_id,
            },
        )
        job = {
            "id": job_id,
            "connector_id": body.connector_id,
            "tenant_id": body.tenant_id,
            "resource_type": body.resource_type,
            "external_id": body.external_id,
            "status": "succeeded",
            "mode": "manual_fallback",
            "source_record_id": source["id"],
            "source_record_created": created,
            "completed_at": utc_now().isoformat(),
            "requested_by": actor_id,
        }
        self.db.collection("sync_jobs").document(job_id).set(job)
        return job, source

    def reconcile(self, body: ReconciliationRequest):
        records = list(self.db.collection("source_records").rows.values()) if hasattr(
            self.db.collection("source_records"), "rows"
        ) else [item.to_dict() or {} for item in self.db.collection("source_records").stream()]
        selected = [
            item for item in records
            if item.get("connector_id") == body.connector_id
            and item.get("tenant_id") == body.tenant_id
            and (not body.resource_type or item.get("resource_type") == body.resource_type)
        ]
        duplicates: dict[str, list[str]] = {}
        by_external: dict[str, list[dict]] = {}
        for item in selected:
            by_external.setdefault(str(item.get("external_id")), []).append(item)
        for external_id, items in by_external.items():
            hashes = {item.get("payload_sha256") for item in items}
            if len(items) > 1 and len(hashes) > 1:
                duplicates[external_id] = [item["id"] for item in items]
        report = {
            "id": self._id("rec"),
            "connector_id": body.connector_id,
            "tenant_id": body.tenant_id,
            "resource_type": body.resource_type,
            "record_count": len(selected),
            "conflict_count": len(duplicates),
            "conflicts": duplicates,
            "status": "needs_review" if duplicates else "balanced",
            "created_at": utc_now().isoformat(),
        }
        self.db.collection("reconciliation_reports").document(report["id"]).set(report)
        return report
