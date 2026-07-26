"""Deterministic, versioned TIP Score domain engine.

This module owns score math. Portals may render its projections but must never
reimplement the calculation. Persistence and authorization live at the route
and store boundaries so the calculator remains reproducible and testable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from typing import Mapping, Optional

from pydantic import BaseModel, Field


MIN_SCORE = 350
MAX_SCORE = 850
SCORE_RANGE = 500
ALGORITHM_VERSION = "tip-driver-v1.0.0"
RULESET_VERSION = "tip-driver-rules-v1.0.0"


class TipTier(str, Enum):
    ELITE = "ELITE"
    PREFERRED = "PREFERRED"
    STANDARD = "STANDARD"
    ELEVATED = "ELEVATED"
    CRITICAL = "CRITICAL"


class TipScoreStatus(str, Enum):
    OFFICIAL = "OFFICIAL"
    PROVISIONAL = "PROVISIONAL"
    UNDER_REVIEW = "UNDER_REVIEW"
    DISPUTED = "DISPUTED"
    STALE = "STALE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class TipComponent(str, Enum):
    UNSAFE_DRIVING = "unsafeDriving"
    CRASH = "crash"
    HOURS_OF_SERVICE = "hoursOfService"
    DRIVER_FITNESS = "driverFitness"
    SUBSTANCE_ALCOHOL = "substanceAlcohol"
    SAFETY_MANAGEMENT = "safetyManagement"


COMPONENT_WEIGHTS: Mapping[TipComponent, float] = {
    TipComponent.UNSAFE_DRIVING: 0.25,
    TipComponent.CRASH: 0.20,
    TipComponent.HOURS_OF_SERVICE: 0.15,
    TipComponent.DRIVER_FITNESS: 0.15,
    TipComponent.SUBSTANCE_ALCOHOL: 0.15,
    TipComponent.SAFETY_MANAGEMENT: 0.10,
}


class ComponentInput(BaseModel):
    risk: float = Field(ge=0, le=1)
    event_count: int = Field(default=0, ge=0)
    verified_event_count: int = Field(default=0, ge=0)
    top_factors: list[str] = Field(default_factory=list, max_length=10)


class ConfidenceInput(BaseModel):
    source_completeness: float = Field(ge=0, le=1)
    identity_match_quality: float = Field(ge=0, le=1)
    record_freshness: float = Field(ge=0, le=1)
    credential_verification: float = Field(ge=0, le=1)
    exposure_sufficiency: float = Field(ge=0, le=1)


class ActiveCeiling(BaseModel):
    ceiling_score: int = Field(ge=MIN_SCORE, le=MAX_SCORE)
    reason_code: str = Field(min_length=1, max_length=120)
    expires_at: Optional[datetime] = None


class ScoreCalculationInput(BaseModel):
    driver_id: str = Field(min_length=1, max_length=200)
    components: dict[TipComponent, ComponentInput]
    confidence: ConfidenceInput
    status: TipScoreStatus = TipScoreStatus.PROVISIONAL
    data_as_of: datetime
    active_ceilings: list[ActiveCeiling] = Field(default_factory=list)
    previous_score: Optional[int] = Field(default=None, ge=MIN_SCORE, le=MAX_SCORE)
    verified_history_months: int = Field(default=0, ge=0)
    verified_inspections: int = Field(default=0, ge=0)


class ComponentResult(BaseModel):
    risk: float
    weight: float
    weighted_risk: float
    event_count: int
    verified_event_count: int
    top_factors: list[str]


class TipScoreSnapshot(BaseModel):
    id: str
    driver_id: str
    score: int
    tier: TipTier
    status: TipScoreStatus
    publication_state: str = "shadow"
    confidence_percent: int
    confidence_label: str
    total_risk: float
    components: dict[TipComponent, ComponentResult]
    active_ceiling: Optional[ActiveCeiling] = None
    previous_score: Optional[int] = None
    score_delta: Optional[int] = None
    calculated_at: datetime
    data_as_of: datetime
    algorithm_version: str = ALGORITHM_VERSION
    ruleset_version: str = RULESET_VERSION
    proprietary_notice: str = (
        "TIP Score is a proprietary Rig Resolve score, not an official FMCSA score."
    )


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def tier_for_score(score: int) -> TipTier:
    if score >= 800:
        return TipTier.ELITE
    if score >= 740:
        return TipTier.PREFERRED
    if score >= 670:
        return TipTier.STANDARD
    if score >= 580:
        return TipTier.ELEVATED
    return TipTier.CRITICAL


def confidence_percent(value: ConfidenceInput) -> int:
    result = (
        value.source_completeness * 0.30
        + value.identity_match_quality * 0.20
        + value.record_freshness * 0.20
        + value.credential_verification * 0.15
        + value.exposure_sufficiency * 0.15
    )
    return round(clamp(result, 0, 1) * 100)


def confidence_label(percent: int) -> str:
    if percent >= 90:
        return "Very High"
    if percent >= 75:
        return "High"
    if percent >= 60:
        return "Moderate"
    if percent >= 40:
        return "Low"
    return "Insufficient"


@dataclass(frozen=True)
class TipScoreCalculator:
    algorithm_version: str = ALGORITHM_VERSION
    ruleset_version: str = RULESET_VERSION

    def calculate(
        self,
        value: ScoreCalculationInput,
        *,
        calculated_at: Optional[datetime] = None,
    ) -> TipScoreSnapshot:
        missing = set(COMPONENT_WEIGHTS) - set(value.components)
        extra = set(value.components) - set(COMPONENT_WEIGHTS)
        if missing or extra:
            raise ValueError(
                f"Exactly six score components are required; missing={sorted(m.value for m in missing)}, "
                f"extra={sorted(e.value for e in extra)}"
            )

        component_results: dict[TipComponent, ComponentResult] = {}
        total_risk = 0.0
        for component, weight in COMPONENT_WEIGHTS.items():
            item = value.components[component]
            weighted = item.risk * weight
            total_risk += weighted
            component_results[component] = ComponentResult(
                risk=item.risk,
                weight=weight,
                weighted_risk=round(weighted, 6),
                event_count=item.event_count,
                verified_event_count=item.verified_event_count,
                top_factors=item.top_factors,
            )

        score = round(clamp(MAX_SCORE - SCORE_RANGE * total_risk, MIN_SCORE, MAX_SCORE))
        active_ceiling = (
            min(value.active_ceilings, key=lambda ceiling: ceiling.ceiling_score)
            if value.active_ceilings
            else None
        )
        if active_ceiling:
            score = min(score, active_ceiling.ceiling_score)

        status = value.status
        if value.verified_history_months == 0 and value.verified_inspections == 0:
            # Product policy: absence of evidence is neither elite performance
            # nor a modeled adverse event. Present a neutral developing-profile
            # value and let confidence communicate the evidence limitation.
            score = 700
            status = TipScoreStatus.INSUFFICIENT_DATA
        elif value.verified_history_months < 12:
            status = TipScoreStatus.PROVISIONAL
            score = min(score, 750)

        confidence = confidence_percent(value.confidence)
        now = calculated_at or datetime.now(timezone.utc)
        stable_input = {
            "driver_id": value.driver_id,
            "components": value.components.model_dump(mode="json")
            if hasattr(value.components, "model_dump")
            else {
                component.value: item.model_dump(mode="json")
                for component, item in value.components.items()
            },
            "confidence": value.confidence.model_dump(mode="json"),
            "status": status.value,
            "data_as_of": value.data_as_of.isoformat(),
            "active_ceilings": [
                item.model_dump(mode="json") for item in value.active_ceilings
            ],
            "algorithm_version": self.algorithm_version,
            "ruleset_version": self.ruleset_version,
        }
        digest = sha256(
            json.dumps(stable_input, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:24]

        return TipScoreSnapshot(
            id=f"tips_{digest}",
            driver_id=value.driver_id,
            score=score,
            tier=tier_for_score(score),
            status=status,
            confidence_percent=confidence,
            confidence_label=confidence_label(confidence),
            total_risk=round(total_risk, 6),
            components=component_results,
            active_ceiling=active_ceiling,
            previous_score=value.previous_score,
            score_delta=(
                score - value.previous_score
                if value.previous_score is not None
                else None
            ),
            calculated_at=now,
            data_as_of=value.data_as_of,
            algorithm_version=self.algorithm_version,
            ruleset_version=self.ruleset_version,
        )


def thin_file_input(driver_id: str, *, data_as_of: Optional[datetime] = None) -> ScoreCalculationInput:
    """Return the neutral, low-confidence input used when no verified history exists."""
    return ScoreCalculationInput(
        driver_id=driver_id,
        components={
            component: ComponentInput(
                risk=0.30 if component != TipComponent.SAFETY_MANAGEMENT else 0.50,
                top_factors=["Insufficient verified history for a full assessment"],
            )
            for component in TipComponent
        },
        confidence=ConfidenceInput(
            source_completeness=0,
            identity_match_quality=0.5,
            record_freshness=0,
            credential_verification=0,
            exposure_sufficiency=0,
        ),
        status=TipScoreStatus.INSUFFICIENT_DATA,
        data_as_of=data_as_of or datetime.now(timezone.utc),
    )
