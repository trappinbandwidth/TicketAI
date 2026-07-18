# TIP OS WP-11 — Financial Ledger, Holds, and Payout Controls

## Delivered

- Immutable ledger accounts, journals, and individual postings.
- Double-entry enforcement: every journal has at least two non-zero postings
  and must balance to zero in one currency.
- Deterministic idempotency keys for payment and settlement retries.
- Tenant and currency validation before any posting is recorded.
- Case-linked funds holds with explicit release conditions and controlled
  release, refund, dispute, and resolution transitions.
- Provider reconciliation reports that expose missing and unexpected
  settlements instead of silently balancing differences.
- Staff-only, feature-flagged APIs for accounts, journals, holds, and
  reconciliation.

## Operational boundaries

- `TIP_OS_FINANCIAL_LEDGER_ENABLED` remains off until staging reconciliation is
  complete.
- Choice Digital payout submission remains intentionally unimplemented until
  official provider documentation and credentials are supplied.
- Existing Stripe and manual payout paths are not automatically redirected to
  the new ledger in this dark-launch package.
- Corrections are made through compensating journals; posted journal and
  posting records are never edited through the service.

