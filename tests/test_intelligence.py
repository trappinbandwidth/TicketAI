from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.platform.intelligence import Evidence, ModelRegistration, Recommendation, Signal
from app.platform.intelligence_service import IntelligenceService, stable_hash
from tests.test_platform_identity import FakeDb


def evidence():
    return Evidence(
        source_type="canonical_record",
        source_id="rec_1",
        field="court_date",
        quote="2026-08-01",
        retrieved_at=datetime(2026, 7, 16, tzinfo=timezone.utc),
        source_version="driver-cloud-v1",
        confidence=0.95,
    )


def test_signal_requires_evidence_and_supports_review_dispositions():
    with pytest.raises(ValidationError):
        Signal(
            id="sig_bad", signal_type="deadline", subject_principal_id="prn_driver",
            resource_type="case", resource_id="case_1", severity="high", confidence=.9,
            source_freshness_at=datetime.now(timezone.utc), explanation="Court date is close",
            impact_dimensions=["legal"],
        )
    service = IntelligenceService(FakeDb())
    signal = service.create_signal(Signal(
        id="sig_1", signal_type="deadline", subject_principal_id="prn_driver",
        resource_type="case", resource_id="case_1", severity="high", confidence=.9,
        source_freshness_at=datetime.now(timezone.utc), explanation="Court date is close",
        impact_dimensions=["legal", "employment"], evidence=[evidence()],
    ))
    snoozed = service.disposition_signal(
        "prn_driver", signal.id, "snooze", "Waiting for court", datetime.now(timezone.utc) + timedelta(days=1)
    )
    assert snoozed.status.value == "snoozed"


def test_recommendations_require_alternatives_risks_evidence_and_human_review():
    service = IntelligenceService(FakeDb())
    recommendation = service.create_recommendation(Recommendation(
        id="grec_1", recommendation_type="attorney_review",
        subject_principal_id="prn_driver", resource_type="ticket", resource_id="ticket_1",
        action="Ask an attorney to review the citation",
        rationale="The deadline is near and the citation may affect CDL status.",
        alternatives=["Contact the court for procedural information"],
        risks=["Waiting may reduce available options"], evidence=[evidence()], confidence=.84,
        required_approver_role="driver",
    ))
    assert recommendation.status.value == "pending_review"
    assert "not legal advice" in recommendation.educational_disclosure
    reviewed = service.review_recommendation("prn_driver", recommendation.id, True, "Proceed")
    assert reviewed.status.value == "approved"
    assert reviewed.approved_by == "prn_driver"


def test_rules_precede_model_runs_and_are_reproducible():
    service = IntelligenceService(FakeDb())
    facts = {"days_until_court": 3}
    evaluation = service.evaluate_rule(
        "court-urgency", "v1", facts,
        lambda item: ("urgent", "Court is within 7 days") if item["days_until_court"] <= 7 else ("normal", "More than 7 days"),
    )
    with pytest.raises(ValueError, match="must precede"):
        service.record_run(
            purpose="ticket_options", provider="anthropic", model="claude",
            prompt_version="v2", input_hash=stable_hash(facts), output_hash="out",
        )
    run = service.record_run(
        purpose="ticket_options", provider="anthropic", model="claude",
        prompt_version="v2", input_hash=stable_hash(facts), output_hash="out",
        rule_evaluation_ids=[evaluation.id], knowledge_versions=["traffic-rules-2026-07"],
    )
    assert run.rule_evaluation_ids == [evaluation.id]
    assert evaluation.input_hash == stable_hash(facts)


def test_anthropic_and_openai_models_are_governed_independently():
    service = IntelligenceService(FakeDb())
    anthropic = service.register_model("prn_admin", ModelRegistration(
        id="model_anthropic_extract",
        provider="anthropic",
        model="configured-claude-model",
        purpose="document_extraction",
        status="approved",
        prompt_versions=["v2"],
        approval_thresholds={"human_review_below": 0.8},
    ))
    openai = service.register_model("prn_admin", ModelRegistration(
        id="model_openai_extract",
        provider="openai",
        model="configured-openai-model",
        purpose="document_extraction",
        status="evaluation",
        prompt_versions=["v2"],
    ))

    assert anthropic.approved_by == "prn_admin"
    assert openai.status == "evaluation"
