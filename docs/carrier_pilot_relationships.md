# Carrier Pilot relationship and consent support

The Pilot does not require a paid messaging, identity, or analytics vendor to
connect a Driver and Carrier.

## Connection flow

1. The authenticated Driver requests a connection code with
   `POST /api/v1/driver/profile/carrier-connection-code`.
2. The Engine returns a 12-character code that expires after 15 minutes. Only
   its SHA-256 hash is stored.
3. The authenticated Carrier submits the code to
   `POST /api/v1/carrier/relationships/connect`.
4. The code is consumed once using a Firestore update precondition. It creates
   an `invited` relationship, not consent.
5. The Driver reviews the request under
   `GET /api/v1/driver/profile/carrier-relationships` and accepts or declines
   with the relationship response endpoint.
6. Safety-data access requires a second, explicit Driver action at the
   `safety-consent` endpoint. The Pilot disclosure permits read-only access to
   profile, credential, employment, and inspection categories.

Possession of a code does not expose the Driver's Firebase UID, profile,
credentials, tickets, legal records, or consent.

## Former Drivers and revocation

Either the Driver or an authorized Carrier administrator can end the
relationship. Carrier Resolve requires an active membership, active
relationship, and active matching consent on every request, so ending the
relationship immediately denies access even before the Driver separately
revokes the consent record.

The Driver remains the only party that can revoke the Driver-granted consent.
Relationship, consent, and revocation events are audit logged.

## Support response

- Expired or used code: ask the Driver to generate a new code.
- Wrong Carrier: the Driver declines the invitation; do not disclose Carrier
  or Driver account details to the requester.
- Employment ended: end the relationship and ask the Driver to revoke the
  corresponding safety consent.
- Disputed access: record the relationship and consent IDs, preserve audit
  events, and escalate to Captain. Never manually copy data between tenants.
