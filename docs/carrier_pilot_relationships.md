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

## In-app notifications

Relationship state changes use first-party in-app notifications; no paid email,
SMS, or push provider is required for the Pilot.

- A connection request notifies only the Driver principal that issued the code.
- Accept/decline and safety-consent changes notify active Carrier administrators,
  safety managers, and fleet managers in that Carrier organization.
- Ending a relationship notifies the other party.
- Notification IDs are deterministic per recipient and state-transition
  instance, so retries do not create duplicates or reset an alert that was
  already read while a later valid relationship lifecycle can still alert.
- Driver and Carrier notification reads are principal-scoped. Looking up or
  marking another principal's notification returns not found.

The Driver uses `GET /api/v1/driver/profile/notifications` and
`POST /api/v1/driver/profile/notifications/{notification_id}/read`. The Carrier
uses the equivalent `/api/v1/carrier/notifications` routes. These notifications
contain relationship state only; they do not contain Driver identifiers, safety
records, ticket/case data, or attorney material.

## Former Drivers and revocation

Either the Driver or an authorized Carrier administrator can end the
relationship. Carrier Resolve requires an active membership, active
relationship, and active matching consent on every request, so ending the
relationship immediately denies access even before the Driver separately
revokes the consent record.

The Driver remains the only party that can revoke the Driver-granted consent.
Relationship, consent, and revocation events are audit logged.

## Acquisition funnel (ADR-010)

Open self-service acquisition is measured with first-party, privacy-minimized
funnel events; no paid analytics vendor is used. Six steps are recorded:

| Step | Where recorded |
| --- | --- |
| `signup_viewed` | `POST /api/v1/carrier/acquisition/funnel` (open, pre-auth) |
| `signup_started` | `POST /api/v1/carrier/acquisition/funnel` (open, pre-auth) |
| `account_created` | server-side during `POST /api/v1/carrier/register` |
| `email_verified` | server-side during registration |
| `carrier_profile_completed` | server-side during registration |
| `first_driver_relationship_requested` | server-side on first relationship |

The two pre-authentication steps have no principal yet, so they use an open
endpoint that accepts **only** those two event types (authenticated steps are
rejected, so the open route cannot inflate them). Events are keyed by a salted
hash of a client-generated visit id — no raw client id, IP, or PII is retained —
and are idempotent per visitor and step. All events are stored in
`acquisition_events` under `funnel = carrier_self_service_pilot`.

## Projection reconciliation

A relationship is stored once in `driver_carrier_relationships`, keyed
deterministically by `(organization_id, driver_principal_id)`. The Carrier
projection (`GET /api/v1/carrier/relationships`) filters that collection by
`carrier_organization_id`; the Driver projection
(`GET /api/v1/driver/profile/carrier-relationships`) filters the same collection
by `driver_principal_id`. Because both read one canonical record, the two views
reconcile field-for-field at every lifecycle state with zero unexplained
differences, and a relationship never appears in an unrelated Driver's view.
`tests/test_carrier_connections.py` asserts this across invited → active → ended.

## Support response

- Expired or used code: ask the Driver to generate a new code.
- Wrong Carrier: the Driver declines the invitation; do not disclose Carrier
  or Driver account details to the requester.
- Employment ended: end the relationship and ask the Driver to revoke the
  corresponding safety consent.
- Disputed access: record the relationship and consent IDs, preserve audit
  events, and escalate to Captain. Never manually copy data between tenants.
