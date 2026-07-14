import pytest

from app.services import financial_service


class FakeDocument:
    def __init__(self):
        self.data = None
        self.update_data = None

    def set(self, data):
        self.data = data

    def update(self, data):
        self.update_data = data


class FakeCollection:
    def __init__(self):
        self.docs = {}

    def document(self, doc_id):
        self.docs.setdefault(doc_id, FakeDocument())
        return self.docs[doc_id]


class FakeDb:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        self.collections.setdefault(name, FakeCollection())
        return self.collections[name]


class FakeStripeProvider:
    provider_name = "stripe"

    def create_checkout_session(self, request):
        return {"id": "cs_test_1", "url": "https://checkout.example.test", "request": request}


class FakeChoiceProvider:
    provider_name = "choice_digital"

    def submit_payout(self, payout_request):
        return {"provider_reference": "choice_1", "status": "submitted", "request": payout_request}


def test_create_checkout_session_uses_provider(monkeypatch):
    emitted = []
    monkeypatch.setattr(financial_service, "write_event", lambda **kwargs: emitted.append(kwargs) or "evt_1")

    session = financial_service.create_checkout_session(
        financial_service.CheckoutSessionRequest(
            payer_type="driver",
            payer_id="driver_1",
            amount_cents=1499,
            transaction_type="membership",
            success_url="https://example.test/success",
            cancel_url="https://example.test/cancel",
        ),
        provider=FakeStripeProvider(),
    )

    assert session["id"] == "cs_test_1"
    assert emitted[0]["event_type"] == "payment.session_created"


def test_record_transaction_persists(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr(financial_service, "write_event", lambda **kwargs: "evt_1")

    transaction = financial_service.TransactionRecord(
        id="txn_1",
        payer_type="driver",
        payer_id="driver_1",
        amount_cents=1499,
        transaction_type="membership",
        status="captured",
        provider="stripe",
        provider_reference="pi_1",
    )

    transaction_id = financial_service.record_transaction(db, transaction)

    assert transaction_id == "txn_1"
    stored = db.collections["transactions"].docs["txn_1"].data
    assert stored["provider_reference"] == "pi_1"


def test_create_and_approve_payout_request(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr(financial_service, "write_event", lambda **kwargs: "evt_1")

    payout = financial_service.create_payout_request(
        db,
        attorney_id="attorney_1",
        case_id="case_1",
        amount_cents=27500,
        requested_by="system",
    )

    assert payout.id.startswith("payout_")
    assert db.collections["payout_requests"].docs[payout.id].data["status"] == "requested"

    result = financial_service.approve_payout_request(db, payout.id, approved_by="staff_1")

    assert result["payout_id"] == payout.id
    assert db.collections["payout_requests"].docs[payout.id].update_data["status"] == "approved"


def test_submit_payout_uses_provider(monkeypatch):
    emitted = []
    monkeypatch.setattr(financial_service, "write_event", lambda **kwargs: emitted.append(kwargs) or "evt_1")

    payout = financial_service.PayoutRequest(
        id="payout_1",
        attorney_id="attorney_1",
        case_id="case_1",
        amount_cents=27500,
    )

    result = financial_service.submit_payout(payout, provider=FakeChoiceProvider())

    assert result["provider_reference"] == "choice_1"
    assert emitted[0]["event_type"] == "payout.submitted"


def test_choice_provider_is_not_implemented_without_docs():
    payout = financial_service.PayoutRequest(
        id="payout_1",
        attorney_id="attorney_1",
        case_id="case_1",
        amount_cents=27500,
    )

    with pytest.raises(NotImplementedError):
        financial_service.submit_payout(payout)
