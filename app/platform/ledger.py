"""WP-11 immutable, balanced financial ledger and funds-hold controls."""
from __future__ import annotations

import hashlib
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from app.platform.models import utc_now


AccountType = Literal["asset", "liability", "equity", "revenue", "expense"]


class LedgerAccount(BaseModel):
    id: str
    tenant_id: str
    name: str
    account_type: AccountType
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    status: Literal["active", "closed"] = "active"


class Posting(BaseModel):
    account_id: str
    amount_cents: int
    memo: str = ""


class JournalRequest(BaseModel):
    tenant_id: str
    idempotency_key: str = Field(min_length=8, max_length=200)
    transaction_type: str
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    external_reference: Optional[str] = None
    postings: list[Posting] = Field(min_length=2)
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def balanced(self):
        if sum(item.amount_cents for item in self.postings) != 0:
            raise ValueError("Journal postings must balance to zero.")
        if any(item.amount_cents == 0 for item in self.postings):
            raise ValueError("Zero-value postings are not allowed.")
        return self


class FundsHoldRequest(BaseModel):
    tenant_id: str
    payer_id: str
    beneficiary_id: str
    case_id: str
    amount_cents: int = Field(gt=0)
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    idempotency_key: str = Field(min_length=8, max_length=200)
    release_condition: str = Field(min_length=1)


class HoldTransition(BaseModel):
    action: Literal["release", "refund", "dispute", "resolve"]
    reason: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=8, max_length=200)


class LedgerService:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _id(prefix):
        return f"{prefix}_{uuid.uuid4().hex}"

    @staticmethod
    def _stable_id(prefix: str, tenant_id: str, key: str):
        digest = hashlib.sha256(f"{tenant_id}|{key}".encode()).hexdigest()
        return f"{prefix}_{digest[:40]}"

    def create_account(self, account: LedgerAccount):
        ref = self.db.collection("ledger_accounts").document(account.id)
        snapshot = ref.get()
        if getattr(snapshot, "exists", False):
            current = snapshot.to_dict() or {}
            if current != account.model_dump():
                raise RuntimeError("Ledger account already exists with different terms.")
            return current, False
        value = account.model_dump()
        ref.set(value)
        return value, True

    def post_journal(self, body: JournalRequest, actor_id: str):
        journal_id = self._stable_id("jnl", body.tenant_id, body.idempotency_key)
        ref = self.db.collection("ledger_journals").document(journal_id)
        snapshot = ref.get()
        if getattr(snapshot, "exists", False):
            return snapshot.to_dict(), False

        accounts = {}
        for posting in body.postings:
            account_snapshot = self.db.collection("ledger_accounts").document(posting.account_id).get()
            if not getattr(account_snapshot, "exists", False):
                raise LookupError(f"Ledger account not found: {posting.account_id}")
            account = account_snapshot.to_dict() or {}
            if account.get("tenant_id") != body.tenant_id:
                raise PermissionError("Cross-tenant ledger posting denied.")
            if account.get("currency") != body.currency or account.get("status") != "active":
                raise ValueError("Posting account currency/status is invalid.")
            accounts[posting.account_id] = account

        created_at = utc_now().isoformat()
        journal = {
            "id": journal_id,
            **body.model_dump(exclude={"postings"}),
            "status": "posted",
            "posted_by": actor_id,
            "posted_at": created_at,
            "posting_ids": [],
        }
        for index, posting in enumerate(body.postings):
            posting_id = f"{journal_id}_{index:03d}"
            self.db.collection("ledger_postings").document(posting_id).set({
                "id": posting_id,
                "journal_id": journal_id,
                "tenant_id": body.tenant_id,
                "currency": body.currency,
                **posting.model_dump(),
                "created_at": created_at,
            })
            journal["posting_ids"].append(posting_id)
        ref.set(journal)
        self.db.collection("audit_events").document(journal_id).set({
            "id": journal_id,
            "event_type": "ledger.journal_posted",
            "actor_id": actor_id,
            "entity_type": "ledger_journal",
            "entity_id": journal_id,
            "payload": {
                "transaction_type": body.transaction_type,
                "external_reference": body.external_reference,
                "posting_count": len(body.postings),
            },
            "created_at": created_at,
        })
        return journal, True

    def create_hold(self, body: FundsHoldRequest, actor_id: str):
        hold_id = self._stable_id("hld", body.tenant_id, body.idempotency_key)
        ref = self.db.collection("funds_holds").document(hold_id)
        snapshot = ref.get()
        if getattr(snapshot, "exists", False):
            return snapshot.to_dict(), False
        value = {
            "id": hold_id,
            **body.model_dump(),
            "status": "authorized",
            "created_by": actor_id,
            "created_at": utc_now().isoformat(),
            "history": [],
        }
        ref.set(value)
        return value, True

    def transition_hold(self, hold_id: str, body: HoldTransition, actor_id: str):
        ref = self.db.collection("funds_holds").document(hold_id)
        snapshot = ref.get()
        if not getattr(snapshot, "exists", False):
            raise LookupError("Funds hold not found.")
        current = snapshot.to_dict() or {}
        seen = {item.get("idempotency_key") for item in current.get("history", [])}
        if body.idempotency_key in seen:
            return current, False
        allowed = {
            "authorized": {"release": "released", "refund": "refunded", "dispute": "disputed"},
            "disputed": {"resolve": "released", "refund": "refunded"},
        }
        next_status = allowed.get(current.get("status"), {}).get(body.action)
        if not next_status:
            raise ValueError("Invalid funds-hold transition.")
        event = {
            **body.model_dump(),
            "from_status": current["status"],
            "to_status": next_status,
            "actor_id": actor_id,
            "created_at": utc_now().isoformat(),
        }
        updated = {**current, "status": next_status, "updated_at": event["created_at"]}
        updated["history"] = [*current.get("history", []), event]
        ref.set(updated)
        return updated, True

    def reconcile_provider(self, tenant_id: str, provider: str, settlements: list[dict]):
        journals_ref = self.db.collection("ledger_journals")
        journals = list(journals_ref.rows.values()) if hasattr(journals_ref, "rows") else [
            item.to_dict() or {} for item in journals_ref.stream()
        ]
        expected = {
            item.get("external_reference"): item
            for item in journals
            if item.get("tenant_id") == tenant_id and item.get("external_reference")
        }
        actual = {str(item.get("external_reference")): item for item in settlements}
        missing = sorted(key for key in expected if key not in actual)
        unexpected = sorted(key for key in actual if key not in expected)
        report = {
            "id": self._id("finrec"),
            "tenant_id": tenant_id,
            "provider": provider,
            "expected_count": len(expected),
            "actual_count": len(actual),
            "missing_external_references": missing,
            "unexpected_external_references": unexpected,
            "status": "balanced" if not missing and not unexpected else "needs_review",
            "created_at": utc_now().isoformat(),
        }
        self.db.collection("financial_reconciliations").document(report["id"]).set(report)
        return report
