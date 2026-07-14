# Integration Strategy

Rig Resolve should separate systems of record, systems of engagement, systems of
intelligence, and provider adapters. This keeps integrations from becoming
tightly coupled to portal UI code.

## Categories

### Systems Of Record

Authoritative external or internal data sources.

- FMCSA
- PSP
- MVR providers
- Courts
- DataQs
- Firebase Auth / Firestore for current MVP identity and app data

### Systems Of Engagement

User-facing applications.

- Driver App
- Carrier Portal
- Attorney Portal
- Admin Dashboard
- Website

### Systems Of Intelligence

Rig Resolve platform logic that transforms events and data into decisions,
recommendations, and workflows.

- AI Ticket Engine
- Event Service
- Recommendation Service
- Financial Service
- Future knowledge graph / learning loop

### Provider Adapters

Replaceable vendor-specific boundaries.

- Stripe
- Choice Digital
- Plaid or future bank verification provider
- Twilio
- SendGrid
- Tenstreet
- Workday
- Samsara
- Motive
- Geotab

## Design Rules

- Portals should call Rig Resolve APIs, not provider SDKs, for business-critical
  actions.
- Webhooks should verify provider signatures before mutating state.
- Provider references can be stored; sensitive secrets and banking details should
  not be logged or returned to frontends.
- Integration events should be normalized into `events/{event_id}` where useful.
- Use provider adapters so a vendor change does not require rewriting product
  workflows.

## Near-Term Work

- Document Tenstreet and Workday webhook auth before external rollout.
- Keep Stripe webhook verification strict.
- Wait for Choice Digital API docs before real payout submission.
- Add integration-specific event names once the event model is stable.
