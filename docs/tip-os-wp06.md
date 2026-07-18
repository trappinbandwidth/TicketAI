# TIP OS WP-06 — Driver Resolve

Driver Resolve now provides feature-flagged views for the Driver Cloud, secure document vault, extraction correction, Decision Center, workflow timeline/deadlines, DataQs workspace, carrier relationships and consent, and notification preferences.

The verified-intake handoff is transactional in behavior and idempotent:

1. A malware-cleared document is extracted asynchronously.
2. The driver corrects and verifies every field.
3. Finalization creates one canonical violation or inspection record.
4. A versioned ticket or DataQs workflow starts.
5. Deterministic deadline rules execute before model-derived intelligence.
6. The provider/model/prompt/input/output trace is recorded.
7. Signals and recommendations remain reviewable; no court, DataQs, legal, employment, or carrier submission is automatic.

Driver-facing features remain behind their individual flags. The existing ticket list, upload, status, and case experience remain available throughout shadow rollout.

Focused tests cover the verified-only gate, idempotent finalization, canonical projection, workflow transitions, deterministic-rule ordering, and human-review recommendation state. The Driver production build passes.
