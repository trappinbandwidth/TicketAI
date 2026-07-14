# Contributing

Rig Resolve handles driver, citation, and legal workflow data. Keep changes
small, reviewable, and safe.

## Before You Change Code

- Read `SECURITY.md` before handling security reports or sensitive data.
- Preserve Rig Resolve product language and brand direction.
- Update Claude/onboarding docs in place when they are stale; do not replace
  them wholesale.
- Do not commit `.env` files, private keys, Firebase service account JSON, or
  production tokens.

## Local Check

Run:

```bash
make check
```

Use narrower targets such as `make syntax`, `make test`, `make smoke`, or
`make secret-scan` when isolating a failure.

## Pull Requests

Use the pull request template and include:

- What changed
- Why the change is needed
- Security/privacy impact
- Verification run
- Deployment or migration notes

Security-sensitive changes should be scoped and reviewed before deployment.

