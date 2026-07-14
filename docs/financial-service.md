# Financial Service

Rig Resolve financial actions should move through a backend service layer rather
than portal code calling payment providers directly.

## Scope

This Phase 1 layer is intentionally an abstraction and local persistence helper.
It does not submit real Choice Digital payouts and does not require provider
credentials for tests.

## Responsibilities

- Create checkout/payment sessions through a provider adapter.
- Create payment intents when product flows require them.
- Record transactions in `transactions/{transaction_id}`.
- Maintain an internal ledger in `ledger_entries/{ledger_id}`.
- Create payout requests in `payout_requests/{payout_id}`.
- Approve payout requests with staff identity.
- Submit payouts through a provider adapter once provider API details exist.
- Emit financial events through the shared event service.

## Collections

```text
transactions/{txn_id}
payout_requests/{payout_id}
ledger_entries/{ledger_id}
```

## Domain Objects

### Transaction

```json
{
  "id": "txn_...",
  "payer_type": "driver|carrier|partner",
  "payer_id": "...",
  "payee_type": "rig_resolve|attorney|driver|partner|court",
  "payee_id": "...",
  "amount_cents": 1499,
  "currency": "USD",
  "transaction_type": "membership|one_time_case|carrier_invoice|attorney_payout|referral_reward|court_fee",
  "status": "created|authorized|captured|failed|refunded|pending_payout|paid_out",
  "provider": "stripe|choice_digital|manual|internal_ledger",
  "provider_reference": "...",
  "metadata": {},
  "created_at": "...",
  "updated_at": "..."
}
```

### Payout Request

```json
{
  "id": "payout_...",
  "attorney_id": "attorney_...",
  "case_id": "case_...",
  "amount_cents": 27500,
  "currency": "USD",
  "status": "requested|approved|submitted|paid|failed|rejected",
  "provider": "choice_digital",
  "provider_reference": null,
  "requested_by": "system|staff_uid",
  "approved_by": null,
  "rejection_reason": null,
  "created_at": "...",
  "updated_at": "..."
}
```

### Ledger Entry

```json
{
  "id": "ledger_...",
  "transaction_id": "txn_...",
  "entry_type": "debit|credit",
  "account_type": "driver_wallet|carrier_account|attorney_payable|rig_resolve_revenue|escrow",
  "account_id": "...",
  "amount_cents": 27500,
  "currency": "USD",
  "created_at": "..."
}
```

## Provider Boundary

Provider modules live under `app/services/payment_providers/`.

- `stripe_provider.py` owns Stripe-facing payment acceptance calls.
- `choice_digital_provider.py` owns Choice Digital payout calls once API docs and
  credentials are available.

Portal routes should call `app/services/financial_service.py`, not provider SDKs
directly, for new money movement.

## Events

- `payment.session_created`
- `payment.authorized`
- `payment.captured`
- `payment.failed`
- `payout.requested`
- `payout.approved`
- `payout.submitted`
- `payout.sent`
- `payout.failed`
- `ledger.entry_created`

## Security Rules

- Frontends never send provider secret keys.
- Payout approval requires staff/admin custom claims before route handlers call
  this service.
- Provider references may be stored; sensitive banking details must not be.
- Webhooks must verify provider signatures before mutating financial state.
