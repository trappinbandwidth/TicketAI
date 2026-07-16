# TIP OS WP-07 — Attorney Resolve

Attorney Resolve already provides onboarding, license/coverage capture, available and assigned case views, offers/bids, case activity, deadlines, outcomes, wallet, and payout requests. WP-07 adds the missing governed gates around that journey.

When `TIP_OS_ATTORNEY_GOVERNANCE_ENABLED=true`:

- Unverified attorneys cannot access the case marketplace.
- Available case previews remain anonymized and exclude driver contact information.
- An attorney must record a case-specific conflict decision before claiming.
- Only `no_conflict` permits claim; conflicts and unresolved reviews block access.
- Conflict decisions are idempotent and audited.
- Case workspace entries identify attorney authorship and default to attorney-client privileged visibility.
- Existing ownership checks prevent non-assigned attorneys, carriers, and unrelated users from reading or writing case activity.

The Attorney frontend adds the conflict attestation immediately before a claim. Its production build passes. Existing claim behavior remains available while the governance flag is disabled, permitting a controlled cohort rollout after attorney verification data is reconciled.
