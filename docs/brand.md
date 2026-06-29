# Rig Resolve — Brand Documentation

## Brand Identity

**Rig Resolve** is a legal benefit platform for commercial truck drivers. The name evokes resolution — solving problems for the people who keep the country moving. Every brand decision should reinforce two things: competence and respect for the driver.

The product's roots are in **CDL Legal**, the prior org. Code still contains CDL Legal references that are being migrated to Rig Resolve branding over time.

---

## Mission Statement

To protect CDL holders' livelihoods by giving every commercial driver access to the same quality legal defense that was previously only available to large fleets.

---

## Brand Voice

| Attribute | Description | Example |
|-----------|-------------|---------|
| **Straight-talking** | No legalese, no corporate speak | "Your court date is in 6 days. We've got you." |
| **Confident** | We know CDL law. Speak from authority | "Speeding 15+ is a serious violation. It needs an attorney." |
| **Respectful** | Drivers are professionals, not victims | "Your CDL is your livelihood. We protect it." |
| **Concise** | Drivers are busy. Get to the point | "Ticket received. Attorney assigned. Done." |

### What to avoid
- Insurance-industry language ("claim", "coverage limits", "deductible")
- Legal hedging ("may potentially", "could possibly")
- Condescension ("Don't worry!", "It's easy!")
- Jargon drivers don't use in daily work

---

## Naming Conventions

These terms have specific meanings within Rig Resolve. Use them consistently across all surfaces — product copy, support responses, legal docs, and code comments.

| Term | Meaning | Do NOT say |
|------|---------|-----------|
| **Ticket** | A traffic citation received by a CDL holder | Support ticket, citation (externally) |
| **Carrier** | A trucking company that enrolls drivers | Insurance carrier |
| **Member / Subscriber / Driver** | An enrolled CDL holder | Customer, client, user |
| **Attorney** | A CDL defense lawyer in our network | Lawyer (too generic), counselor |
| **Case** | A ticket that has been assigned to an attorney | Claim, file |
| **Outcome** | The final result of a case (won, dismissed, etc.) | Settlement, resolution |
| **Review Queue** | Manually scanned tickets awaiting admin approval | Inbox, pending queue |
| **AI Review** | Status of a ticket awaiting human reviewer sign-off | Pending, in review |

---

## User Types

There are exactly three user types. All product decisions should map cleanly to one of these three.

### Drivers
Commercial truck drivers holding a CDL (Class A, B, or C). They receive traffic citations and need legal defense.

**Driver subtypes:**
- `carrier` — enrolled through a trucking company; company pays
- `independent` — self-enrolled; pays monthly directly
- `owner_operator` — runs their own truck/authority; pays monthly directly

**What they care about:** speed of response, knowing their case is handled, protecting their license.

**Plans available:**
| Plan | Monthly | Safe Driver | Coverage |
|------|---------|-------------|----------|
| RigResolve Core | $14.99 | $11.99 | 1 ticket/year |
| RigResolve Pro | $24.99 | $19.99 | Unlimited tickets |

Safe driver rate requires PSP/MVR verification at signup (clean record = 20% discount).

### Attorneys
CDL defense lawyers who claim cases, contact drivers, and represent them in traffic court.

**Attorney tiers:**
| Tier | Experience | Max Active Cases | Requirements |
|------|-----------|-----------------|-------------|
| `senior` | 5+ years | Unlimited | Fast-tracked |
| `junior` | <5 years | 5 | Interview required |
| `law_student` | N/A | 2 | Supervised by licensed attorney; nonprofit eligible |

Attorneys apply via the attorney application pipeline, are verified by staff, then assigned cases by admins.

### Carriers
Trucking companies that enroll their drivers and receive monthly bulk invoices.

**Billing models:**
- `invoice` — RR bills carrier monthly; carrier pays via check/ACH
- `payroll` — carrier deducts from driver paychecks and remits to RR

Carrier pricing: negotiated per fleet size, starting at $9.00/driver/month for 50+ drivers.

---

## Product Positioning

### vs. Paying a Ticket
A serious violation conviction can cost a CDL driver $8,000–$15,000 in increased insurance premiums, points, and potential CDL disqualification. Legal defense that avoids conviction costs $300–$1,000 in attorney fees. For $14.99/month, drivers get that defense on demand.

### vs. Hiring a Private Attorney
Finding a CDL-specific attorney when you're in trouble, on the road, is hard. Rig Resolve maintains a vetted network of CDL defense specialists with proven win rates, already matched to the driver's state and county.

### vs. CDL Legal (Prior Org)
CDL Legal had a strong attorney network and deep CDL expertise but operated with manual, Salesforce-based case management. Rig Resolve automates intake and matching with AI while preserving the human attorney relationship that wins cases.

---

## Tone by Surface

| Surface | Tone | Example |
|---------|------|---------|
| Driver app notifications | Warm, direct, action-oriented | "Marcus Williams has taken your case. He'll contact you within 24 hrs." |
| Attorney portal | Professional, information-dense | "Ticket #TX-2024-... — Speeding 15+ (Harris County). Court: 04/15/2024." |
| Admin dashboard | Operational, factual | "CRITICAL — 4 tickets with court dates in <7 days." |
| Carrier portal | Business-to-business | "Your fleet: 12 enrolled drivers. Invoice due 02/01." |
| Email/SMS to drivers | Short, human | "Good news — your ticket in Dallas was dismissed. Check your app." |

---

## Brand Colors (Reference)

Not yet codified in a design system. Current implementation uses Tailwind utility classes. When a design system is formalized, these are the intended values:

| Role | Description |
|------|-------------|
| Primary | Deep blue — authority and trust |
| Accent | Amber/gold — action and urgency |
| Danger | Red — CRITICAL urgency, rejections |
| Success | Green — approved, won, dismissed |
| Neutral | Slate gray — informational states |

---

## Legal & Compliance Language

When writing copy that touches on legal outcomes or guarantees:
- Never promise a specific outcome ("We'll get your ticket dismissed")
- Never claim specific win rates without disclaimer ("Attorney win rates vary by state and violation type")
- Use "may" or "can" when describing potential outcomes
- Always attribute outcomes to the attorney, not Rig Resolve ("Your attorney secured a dismissal")

The phrase **"vs. CDL Legal"** on the pricing page has not yet been reviewed by legal counsel. Do not publish competitive claims without that review.

---

*Last updated: 2026-06-26*
