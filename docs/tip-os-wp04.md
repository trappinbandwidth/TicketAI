# TIP OS WP-04 — Workflows, Tasks, Deadlines, and Notifications

## Deterministic workflows

Versioned definitions now cover ticket, DataQs, credential, and legal case lifecycles. Each instance stores its current state, immutable transition history, subject, resource, UTC deadline, deadline basis/source/confidence, tenant, and end-to-end correlation ID.

Invalid transitions are rejected. Consequential engagement, submission, activation, and closure transitions require a matching recorded human approval. Retried workflow creation and alerts are idempotent.

## Tasks and deadlines

Tasks include assignee, priority, UTC due date, dependencies, evidence requirements, completion evidence, and formal waiver reason. A dependent task cannot complete early, and an evidence-required task cannot close without evidence or an explicit waiver.

## Notifications

Users control in-app, email, SMS, and push preferences. An urgent-deadline override is disabled by default and carries disclosure version `notifications-v1`. Alerts are deduplicated and retain their workflow correlation ID.

## API and rollout

Routes under `/api/v1/workflows` require Firebase authentication and `TIP_OS_WORKFLOWS_ENABLED=true`. Subject access is owner-only unless a staff role is present. Creation, transitions, approvals, tasks, preferences, and alerts produce immutable audit events.

The feature remains disabled until portal workflow projections, delivery-provider workers, timer scheduling, and operations escalation dashboards are ready. Existing ticket/case status fields remain compatibility projections during rollout.
