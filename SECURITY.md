# Security Policy

Rig Resolve handles driver, citation, payment-adjacent, and legal workflow data. Please do not report security issues in public issues, pull requests, screenshots, or logs.

## Reporting a Vulnerability

Use GitHub private vulnerability reporting or a private security advisory for this repository. Include:

- A short description of the issue
- Affected endpoint, file, workflow, or deployment surface
- Reproduction steps with test data only
- Impact assessment and any evidence of exposure

Do not include real credentials, Firebase service account keys, driver PII, court documents, payment data, or production tokens.

## Scope

In scope:

- Authentication or authorization bypass
- Exposed secrets or unsafe logging
- Firestore, Firebase Auth, Cloud Run, or GitHub Actions misconfiguration
- Unsafe file upload, document parsing, or ticket-processing behavior
- Cross-portal data access between drivers, attorneys, carriers, and staff

Out of scope:

- Social engineering
- Denial-of-service testing
- Physical attacks
- Reports based only on missing optional headers without a realistic exploit path

## Handling Expectations

Security fixes should be scoped, reviewed, and verified before deployment. If a secret is exposed, revoke or rotate it before treating the code cleanup as complete.

