import pytest
from pydantic import ValidationError

from app.platform.ledger import (
    FundsHoldRequest,
    HoldTransition,
    JournalRequest,
    LedgerAccount,
    LedgerService,
    Posting,
)
from tests.test_platform_identity import FakeDb


def service_with_accounts():
    db = FakeDb()
    service = LedgerService(db)
    for account in (
        LedgerAccount(id="acct_cash", tenant_id="org_1", name="Cash", account_type="asset"),
        LedgerAccount(id="acct_revenue", tenant_id="org_1", name="Revenue", account_type="revenue"),
    ):
        service.create_account(account)
    return db, service


def test_journal_must_balance_and_is_idempotent_and_immutable():
    with pytest.raises(ValidationError, match="balance"):
        JournalRequest(
            tenant_id="org_1", idempotency_key="payment-123",
            transaction_type="case_fee",
            postings=[
                Posting(account_id="acct_cash", amount_cents=100),
                Posting(account_id="acct_revenue", amount_cents=-90),
            ],
        )
    db, service = service_with_accounts()
    body = JournalRequest(
        tenant_id="org_1", idempotency_key="payment-123",
        transaction_type="case_fee", external_reference="pi_123",
        postings=[
            Posting(account_id="acct_cash", amount_cents=25000),
            Posting(account_id="acct_revenue", amount_cents=-25000),
        ],
    )
    first, created = service.post_journal(body, "prn_finance")
    second, created_again = service.post_journal(body, "prn_finance")
    assert created is True and created_again is False
    assert first == second
    assert len(db.collection("ledger_postings").rows) == 2
    assert sum(item["amount_cents"] for item in db.collection("ledger_postings").rows.values()) == 0


def test_cross_tenant_and_unknown_accounts_fail_closed():
    _, service = service_with_accounts()
    body = JournalRequest(
        tenant_id="org_2", idempotency_key="payment-456", transaction_type="case_fee",
        postings=[
            Posting(account_id="acct_cash", amount_cents=100),
            Posting(account_id="acct_revenue", amount_cents=-100),
        ],
    )
    with pytest.raises(PermissionError, match="Cross-tenant"):
        service.post_journal(body, "prn_finance")


def test_funds_hold_transition_is_controlled_and_idempotent():
    _, service = service_with_accounts()
    hold, _ = service.create_hold(FundsHoldRequest(
        tenant_id="org_1", payer_id="driver_1", beneficiary_id="attorney_1",
        case_id="case_1", amount_cents=25000, idempotency_key="hold-case-1",
        release_condition="Outcome approved",
    ), "prn_driver")
    transition = HoldTransition(
        action="dispute", reason="Outcome contested", idempotency_key="dispute-case-1"
    )
    disputed, changed = service.transition_hold(hold["id"], transition, "prn_driver")
    repeated, changed_again = service.transition_hold(hold["id"], transition, "prn_driver")
    assert disputed["status"] == "disputed"
    assert changed is True and changed_again is False
    assert repeated["history"] == disputed["history"]


def test_provider_reconciliation_never_silently_balances_mismatch():
    _, service = service_with_accounts()
    body = JournalRequest(
        tenant_id="org_1", idempotency_key="payment-789",
        transaction_type="case_fee", external_reference="pi_expected",
        postings=[
            Posting(account_id="acct_cash", amount_cents=100),
            Posting(account_id="acct_revenue", amount_cents=-100),
        ],
    )
    service.post_journal(body, "prn_finance")
    report = service.reconcile_provider(
        "org_1", "stripe", [{"external_reference": "pi_unexpected"}]
    )
    assert report["status"] == "needs_review"
    assert report["missing_external_references"] == ["pi_expected"]
    assert report["unexpected_external_references"] == ["pi_unexpected"]
