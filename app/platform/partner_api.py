"""WP-12 partner API clients, scoped authorization, events, and webhooks."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import uuid
from typing import Any, Callable, Optional

from pydantic import AnyHttpUrl, BaseModel, Field

from app.platform.models import utc_now


class PartnerClientCreate(BaseModel):
    tenant_id: str
    name: str = Field(min_length=1)
    scopes: list[str] = Field(min_length=1)
    environment: str = Field(pattern="^(development|staging|production)$")


class WebhookSubscriptionCreate(BaseModel):
    client_id: str
    tenant_id: str
    url: AnyHttpUrl
    event_types: list[str] = Field(min_length=1)
    secret_ref: str = Field(min_length=1)


class PartnerEventCreate(BaseModel):
    tenant_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    data: dict[str, Any]
    correlation_id: Optional[str] = None


class PartnerApiService:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _hash_secret(secret: str, salt: str):
        value = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt.encode(), 210_000)
        return base64.b64encode(value).decode()

    def create_client(self, body: PartnerClientCreate, actor_id: str):
        client_id = f"pac_{uuid.uuid4().hex}"
        secret = secrets.token_urlsafe(40)
        salt = secrets.token_hex(16)
        value = {
            "id": client_id,
            **body.model_dump(),
            "secret_hash": self._hash_secret(secret, salt),
            "secret_salt": salt,
            "status": "active",
            "created_by": actor_id,
            "created_at": utc_now().isoformat(),
        }
        self.db.collection("partner_api_clients").document(client_id).set(value)
        return {
            "client": {key: item for key, item in value.items() if not key.startswith("secret_")},
            "client_secret": secret,
        }

    def authenticate(self, client_id: str, secret: str, required_scope: str):
        snapshot = self.db.collection("partner_api_clients").document(client_id).get()
        if not getattr(snapshot, "exists", False):
            raise PermissionError("Invalid partner credentials.")
        client = snapshot.to_dict() or {}
        supplied = self._hash_secret(secret, client.get("secret_salt", ""))
        if not hmac.compare_digest(supplied, client.get("secret_hash", "")):
            raise PermissionError("Invalid partner credentials.")
        if client.get("status") != "active" or required_scope not in client.get("scopes", []):
            raise PermissionError("Partner scope denied.")
        return {
            "client_id": client_id,
            "tenant_id": client["tenant_id"],
            "scopes": client["scopes"],
        }

    def create_subscription(self, body: WebhookSubscriptionCreate, actor_id: str):
        client = self.db.collection("partner_api_clients").document(body.client_id).get()
        if not getattr(client, "exists", False) or (client.to_dict() or {}).get("tenant_id") != body.tenant_id:
            raise PermissionError("Partner client does not belong to tenant.")
        subscription_id = f"whs_{uuid.uuid4().hex}"
        value = {
            "id": subscription_id,
            **body.model_dump(mode="json"),
            "status": "active",
            "created_by": actor_id,
            "created_at": utc_now().isoformat(),
        }
        self.db.collection("webhook_subscriptions").document(subscription_id).set(value)
        return value

    def publish(self, body: PartnerEventCreate):
        event_id = f"pev_{uuid.uuid4().hex}"
        event = {
            "id": event_id,
            "schema_version": "1.0",
            **body.model_dump(),
            "occurred_at": utc_now().isoformat(),
        }
        self.db.collection("partner_events").document(event_id).set(event)
        subscriptions_ref = self.db.collection("webhook_subscriptions")
        subscriptions = list(subscriptions_ref.rows.values()) if hasattr(subscriptions_ref, "rows") else [
            item.to_dict() or {} for item in subscriptions_ref.stream()
        ]
        deliveries = []
        for subscription in subscriptions:
            if (
                subscription.get("status") == "active"
                and subscription.get("tenant_id") == body.tenant_id
                and body.event_type in subscription.get("event_types", [])
            ):
                delivery_id = f"whd_{uuid.uuid4().hex}"
                delivery = {
                    "id": delivery_id,
                    "event_id": event_id,
                    "subscription_id": subscription["id"],
                    "tenant_id": body.tenant_id,
                    "status": "pending",
                    "attempt_count": 0,
                    "next_attempt_at": utc_now().isoformat(),
                    "created_at": utc_now().isoformat(),
                }
                self.db.collection("webhook_deliveries").document(delivery_id).set(delivery)
                deliveries.append(delivery)
        return event, deliveries

    def prepare_delivery(
        self, delivery_id: str, secret_resolver: Callable[[str], str]
    ):
        delivery = self.db.collection("webhook_deliveries").document(delivery_id).get()
        if not getattr(delivery, "exists", False):
            raise LookupError("Webhook delivery not found.")
        value = delivery.to_dict() or {}
        event = self.db.collection("partner_events").document(value["event_id"]).get().to_dict() or {}
        subscription = self.db.collection("webhook_subscriptions").document(
            value["subscription_id"]
        ).get().to_dict() or {}
        payload = json.dumps(event, sort_keys=True, separators=(",", ":"), default=str).encode()
        timestamp = str(int(utc_now().timestamp()))
        secret = secret_resolver(subscription["secret_ref"])
        signature = hmac.new(secret.encode(), timestamp.encode() + b"." + payload, hashlib.sha256).hexdigest()
        return {
            "url": subscription["url"],
            "body": payload,
            "headers": {
                "Content-Type": "application/json",
                "X-RigResolve-Event": event["id"],
                "X-RigResolve-Timestamp": timestamp,
                "X-RigResolve-Signature": f"v1={signature}",
            },
        }

    def record_delivery_result(self, delivery_id: str, success: bool, status_code: int, response_excerpt: str):
        ref = self.db.collection("webhook_deliveries").document(delivery_id)
        snapshot = ref.get()
        if not getattr(snapshot, "exists", False):
            raise LookupError("Webhook delivery not found.")
        current = snapshot.to_dict() or {}
        attempts = int(current.get("attempt_count", 0)) + 1
        terminal = success or attempts >= 8
        updated = {
            **current,
            "attempt_count": attempts,
            "status": "delivered" if success else ("dead_letter" if terminal else "retry"),
            "last_status_code": status_code,
            "last_response_excerpt": response_excerpt[:500],
            "updated_at": utc_now().isoformat(),
        }
        ref.set(updated)
        return updated
