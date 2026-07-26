from datetime import datetime, timezone

import pytest

from app.services.tip_score import (
    ActiveCeiling,
    ComponentInput,
    ConfidenceInput,
    ScoreCalculationInput,
    TipComponent,
    TipScoreCalculator,
    TipScoreStatus,
    TipTier,
    confidence_label,
    thin_file_input,
    tier_for_score,
)


def _input(risks: dict[TipComponent, float], **overrides):
    values = dict(
        driver_id="prn_driver",
        components={
            component: ComponentInput(risk=risks[component])
            for component in TipComponent
        },
        confidence=ConfidenceInput(
            source_completeness=0.8,
            identity_match_quality=0.9,
            record_freshness=0.8,
            credential_verification=0.9,
            exposure_sufficiency=0.7,
        ),
        status=TipScoreStatus.OFFICIAL,
        data_as_of=datetime(2026, 7, 25, tzinfo=timezone.utc),
        verified_history_months=24,
        verified_inspections=2,
    )
    values.update(overrides)
    return ScoreCalculationInput(**values)


def test_golden_preferred_example_is_745_and_deterministic():
    value = _input({
        TipComponent.UNSAFE_DRIVING: 0.30,
        TipComponent.CRASH: 0.10,
        TipComponent.HOURS_OF_SERVICE: 0.40,
        TipComponent.DRIVER_FITNESS: 0.20,
        TipComponent.SUBSTANCE_ALCOHOL: 0.00,
        TipComponent.SAFETY_MANAGEMENT: 0.25,
    })
    now = datetime(2026, 7, 25, 18, 45, tzinfo=timezone.utc)
    first = TipScoreCalculator().calculate(value, calculated_at=now)
    second = TipScoreCalculator().calculate(value, calculated_at=now)
    assert first.score == 745
    assert first.tier == TipTier.PREFERRED
    assert first.total_risk == 0.21
    assert first.id == second.id
    assert first == second


def test_golden_standard_example_rounds_to_734():
    result = TipScoreCalculator().calculate(_input({
        TipComponent.UNSAFE_DRIVING: 0.35,
        TipComponent.CRASH: 0.20,
        TipComponent.HOURS_OF_SERVICE: 0.40,
        TipComponent.DRIVER_FITNESS: 0.10,
        TipComponent.SUBSTANCE_ALCOHOL: 0.00,
        TipComponent.SAFETY_MANAGEMENT: 0.30,
    }))
    assert result.score == 734
    assert result.tier == TipTier.STANDARD


@pytest.mark.parametrize(
    ("score", "tier"),
    [(850, TipTier.ELITE), (800, TipTier.ELITE), (799, TipTier.PREFERRED),
     (740, TipTier.PREFERRED), (739, TipTier.STANDARD), (670, TipTier.STANDARD),
     (669, TipTier.ELEVATED), (580, TipTier.ELEVATED), (579, TipTier.CRITICAL),
     (350, TipTier.CRITICAL)],
)
def test_tier_boundaries(score, tier):
    assert tier_for_score(score) == tier


def test_lowest_active_ceiling_applies_after_calculation():
    result = TipScoreCalculator().calculate(_input(
        {component: 0 for component in TipComponent},
        active_ceilings=[
            ActiveCeiling(ceiling_score=669, reason_code="MEDICAL_EXPIRED"),
            ActiveCeiling(ceiling_score=579, reason_code="CDL_SUSPENDED"),
        ],
    ))
    assert result.score == 579
    assert result.active_ceiling.reason_code == "CDL_SUSPENDED"


def test_thin_file_is_not_elite_and_is_low_confidence():
    result = TipScoreCalculator().calculate(thin_file_input("prn_driver"))
    assert result.score == 700
    assert result.status == TipScoreStatus.INSUFFICIENT_DATA
    assert result.tier == TipTier.STANDARD
    assert result.confidence_percent == 10
    assert confidence_label(result.confidence_percent) == "Insufficient"


def test_requires_exactly_six_components():
    value = thin_file_input("prn_driver")
    del value.components[TipComponent.CRASH]
    with pytest.raises(ValueError, match="Exactly six"):
        TipScoreCalculator().calculate(value)
