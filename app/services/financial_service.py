"""Financial Service abstraction for payments, transactions, ledger, and payouts."""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from pydantic import BaseModel, Field

from app.services.event_service import write_event
from app.services.payment_providers.choice_digital_provider import ChoiceDigitalProvider
from app.services.payment_providers.stripe_provider import StripeProvider

logger = logging.getLogger(__name__)


def _server_timestamp():
    try:
        from google.cloud.firestore_v1 import SERVER_TIMESTAMP

        return SERVER_TIMESTAMP
    except Exception:
        return None


class CheckoutSessionRequest(BaseModel):
    payer_type: str
    payer_id: str
    amount_cents: int = Field(gt=0)
    currency: str = "USD"
    transaction_type: str
    success_url: str
    cancel_url: str
    metadata: dict = Field(default_factory=dict)


class TransactionRecord(BaseModel):
    id: str
    payer_type: str
    payer_id: str
    payee_type: str = "rig_resolve"
    payee_id: str = "rig_resolve"
    amount_cents: int = Field(gt=0)
    currency: str = "USD"
    transaction_type: str
    status: str = "created"
    provider: str = "internal_ledger"
    provider_reference: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    created_at: Optional[object] = None
    updated_at: Optional[object] = None


class PayoutRequest(BaseModel):
    id: str
    attorney_id: str
    case_id: str
    amount_cents: int = Field(gt=0)
    currency: str = "USD"
    status: str = "requested"
    provider: str = "choice_digital"
    provider_reference: Optional[str] = None
    requested_by: str = "system"
    approved_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: Optional[object] = None
    updated_at: Optional[object] = None


class LedgerEntry(BaseModel):
    id: str
    transaction_id: str
    entry_type: str
    account_type: str
    account_id: str
    amount_cents: int
    currency: str = "USD"
    created_at: Optional[object] = None


def _doc_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def create_checkout_session(
    request: CheckoutSessionRequest,
    provider: Optional[StripeProvider] = None,
) -> dict:
    provider = provider or StripeProvider()
    session = provider.create_checkout_session(request.model_dump())
    write_event(
        event_type="payment.session_created",
        actor_type=request.payer_type,
        actor_id=request.payer_id,
        entity_type="payment",
        entity_id=session.get("id", ""),
        source="financial_service",
        payload={
            "provider": provider.provider_name,
            "amount_cents": request.amount_cents,
            "currency": request.currency,
            "transaction_type": request.transaction_type,
        },
    )
    return session


def record_transaction(db, transaction: TransactionRecord) -> str:
    now = _server_timestamp()
    data = transaction.model_copy(update={"created_at": transaction.created_at or now, "updated_at": now}).model_dump()
    db.collection("transactions").document(transaction.id).set(data)
    write_event(
        event_type=f"payment.{transaction.status}",
        actor_type=transaction.payer_type,
        actor_id=transaction.payer_id,
        entity_type="transaction",
        entity_id=transaction.id,
        source="financial_service",
        payload={
            "provider": transaction.provider,
            "amount_cents": transaction.amount_cents,
            "currency": transaction.currency,
            "transaction_type": transaction.transaction_type,
        },
    )
    return transaction.id


def create_ledger_entry(db, entry: LedgerEntry) -> str:
    data = entry.model_copy(update={"created_at": entry.created_at or _server_timestamp()}).model_dump()
    db.collection("ledger_entries").document(entry.id).set(data)
    write_event(
        event_type="ledger.entry_created",
        actor_type="system",
        actor_id=None,
        entity_type="transaction",
        entity_id=entry.transaction_id,
        source="financial_service",
        payload={
            "ledger_id": entry.id,
            "entry_type": entry.entry_type,
            "account_type": entry.account_type,
            "amount_cents": entry.amount_cents,
            "currency": entry.currency,
        },
    )
    return entry.id


def create_payout_request(
    db,
    attorney_id: str,
    case_id: str,
    amount_cents: int,
    requested_by: str = "system",
    currency: str = "USD",
) -> PayoutRequest:
    now = _server_timestamp()
    payout = PayoutRequest(
        id=_doc_id("payout"),
        attorney_id=attorney_id,
        case_id=case_id,
        amount_cents=amount_cents,
        currency=currency,
        requested_by=requested_by,
        created_at=now,
        updated_at=now,
    )
    db.collection("payout_requests").document(payout.id).set(payout.model_dump())
    write_event(
        event_type="payout.requested",
        actor_type="system" if requested_by == "system" else "staff",
        actor_id=None if requested_by == "system" else requested_by,
        entity_type="payout",
        entity_id=payout.id,
        source="financial_service",
        payload={"attorney_id": attorney_id, "case_id": case_id, "amount_cents": amount_cents},
    )
    return payout


def approve_payout_request(db, payout_id: str, approved_by: str) -> dict:
    ref = db.collection("payout_requests").document(payout_id)
    update = {
        "status": "approved",
        "approved_by": approved_by,
        "updated_at": _server_timestamp(),
    }
    ref.update(update)
    write_event(
        event_type="payout.approved",
        actor_type="staff",
        actor_id=approved_by,
        entity_type="payout",
        entity_id=payout_id,
        source="financial_service",
        payload={"status": "approved"},
    )
    return {"payout_id": payout_id, **update}


def submit_payout(
    payout_request: PayoutRequest,
    provider: Optional[ChoiceDigitalProvider] = None,
) -> dict:
    provider = provider or ChoiceDigitalProvider()
    result = provider.submit_payout(payout_request.model_dump())
    write_event(
        event_type="payout.submitted",
        actor_type="system",
        actor_id=None,
        entity_type="payout",
        entity_id=payout_request.id,
        source="financial_service",
        payload={"provider": provider.provider_name, "provider_reference": result.get("provider_reference")},
    )
    return result
