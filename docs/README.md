# Rig Resolve — Documentation Index

Rig Resolve legal benefit platform for commercial truck drivers. This directory contains end-to-end documentation for engineers, product, and operations.

---

## Documents

| Document | Contents |
|----------|---------|
| [brand.md](brand.md) | Brand identity, voice, terminology, user types, pricing, legal guardrails |
| [uiux.md](uiux.md) | UI/UX flows for all four interfaces (Driver App, Attorney Portal, Carrier Portal, Admin Dashboard) |
| [api.md](api.md) | Complete API reference — all endpoints with request/response schemas |
| [agents.md](agents.md) | AI agent pipeline — current agents, architecture, state schema, future agents |
| [agent-extension-guide.md](agent-extension-guide.md) | How to add future agents safely: contracts, graph wiring, events, tests, docs, and UI visibility |
| [agent-identity-roster.md](agent-identity-roster.md) | Staff-facing agent display names and honor-name standard |
| [future_state.md](future_state.md) | Roadmap, 90-day launch plan, feature backlog, open decisions, technical debt |
| [domain-model.md](domain-model.md) | Transportation Intelligence Platform entity model |
| [event-model.md](event-model.md) | Shared event schema and current event writes |
| [recommendation-contract.md](recommendation-contract.md) | Explainable recommendation schema and usage |
| [intelligence-services.md](intelligence-services.md) | External intelligence-service taxonomy mapped to current agents |
| [financial-service.md](financial-service.md) | Payment, payout, transaction, and ledger abstraction |
| [integration-strategy.md](integration-strategy.md) | Systems of record/engagement/intelligence and provider adapter strategy |
| [tip-os-wp01.md](tip-os-wp01.md) | Feature-flagged canonical identity, organizations, consent and policy foundation |

---

## Quick Reference

### Three User Types
- **Drivers** — CDL holders who submit tickets (`carrier`, `independent`, `owner_operator`)
- **Attorneys** — CDL defense lawyers who claim and work cases (`senior`, `junior`, `law_student`)
- **Carriers** — Trucking companies that enroll fleets

### Four Portals
| Portal | URL | Auth |
|--------|-----|------|
| Driver App | rigresolve.web.app | Phone OTP |
| Attorney Portal | rigresolve-attorney.web.app | Email/password |
| Carrier Portal | rigresolve-carrier.web.app | Email/password |
| Admin Dashboard | localhost:5173 (local) | Email/password |

### Ticket Lifecycle
```
manual scan → AI Review → (approve) → New → Admin Assigned → Accepted → Outcome Logged → Closed
driver upload →           New ────────────────────────────────────────────────────────────────→ Closed
```

### AI Pipeline (14 agents)
```
Roux → Carver → Bolin →
  Ida Wells → Charlotte Ray → Jollof →
  Stagecoach Mary → Bass Reeves → Banneker → Madam Walker →
  Tubman → Douglass → assemble
```

Future agent work should follow [agent-extension-guide.md](agent-extension-guide.md).

### Local Verification

Use the repo `Makefile` for repeatable local checks:

```bash
make syntax      # Python compile check
make test        # focused service and inventory tests
make smoke       # narrow process-route smoke tests
make secret-scan # local credential marker scan
make check       # full local verification bundle
```

### Key Repos
| Repo | Local Path |
|------|-----------|
| AI Ticket Engine (this repo) | `CDL_Defense/AI_Ticket_Scanner/ai-ticket-engine-main/` |
| Attorney Portal | `CDL_Defense/Attorney-Portal-main/` |
| Driver App | `CDL_Defense/driver-app-main/` |
| Carrier Portal | `CDL_Defense/carrier-portal/` |

### GCP / Firebase
- **Project:** `rigresolve`
- **Region:** `us-central1`
- **AI Engine:** `https://ai-ticket-engine-kajugdk3nq-uc.a.run.app`
- **Attorney Backend:** `https://attorney-portal-626128667800.us-central1.run.app`
- **Carrier Backend:** `https://carrier-portal-626128667800.us-central1.run.app`

---

*Schema reference: [schema/firestore_schema.md](../schema/firestore_schema.md)*  
*Project onboarding: [CLAUDE.md](../CLAUDE.md)*
