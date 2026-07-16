# TIP OS WP-05 — Intelligence Objects and Rules

TIP OS now separates signals, recommendations, deterministic rule evaluations, model runs, knowledge sources, and model registrations.

Signals require severity, confidence, source freshness, explanation, impact dimensions, and evidence. Authorized subjects can confirm, dismiss, snooze, or escalate them with a recorded reason.

Recommendations cannot be created without an action, rationale, alternatives, risks, evidence, confidence, required approver role, and educational-not-legal-advice disclosure. They remain `pending_review` until an authorized human approves or rejects them.

Every generative intelligence run records provider, model/snapshot, prompt version, approved knowledge versions, tool calls, input/output hashes, rule evaluations, and reviewer disposition. A run is rejected unless at least one deterministic rule evaluation was recorded first.

Anthropic and OpenAI registrations are governed independently through `model_registry`; evaluation does not imply production approval. Knowledge sources are versioned, hashed, tagged for applicability, and require an approver before approved use.

Driver-facing routes under `/api/v1/intelligence` require Firebase authentication, enforce subject ownership, and remain disabled unless `TIP_OS_INTELLIGENCE_ENABLED=true`. Existing recommendation outputs remain compatibility projections until parity evaluations pass.
