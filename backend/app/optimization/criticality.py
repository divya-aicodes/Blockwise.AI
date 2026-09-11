"""Dynamic operational criticality calculation with structured reason codes.

This module computes a deterministic operational criticality score (0–100)
and risk class for a maintenance requirement by combining the asset's ML-predicted
risk level with operational context: condition, age, failure history, overdue
maintenance, weather, train traffic, and section impact.

Reason codes are returned alongside the score so the dashboard can display the
positive and negative factors that drove the calculation.

This is a deterministic synthetic-data demo. Scores and reasons should not be
interpreted as real-world railway safety assessments.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence

from backend.app.config import (
    CRITICALITY_THRESHOLDS,
    CRITICALITY_WEIGHTS,
    RISK_CRITICALITY_BUMP,
    RISK_SEVERITY_SCORE,
    WEATHER_CRITICALITY_PENALTY,
)

CRITICALITY_CLASSES: tuple[str, ...] = ("CRITICAL", "HIGH", "MEDIUM", "LOW")


@dataclass(frozen=True, slots=True)
class ReasonCode:
    """A single structured explanation factor."""

    factor: str
    direction: str
    value: float
    description: str


@dataclass(frozen=True, slots=True)
class CriticalityResult:
    """Output of the dynamic criticality calculation."""

    score: float
    risk_class: str
    reasons: list[ReasonCode] = field(default_factory=list)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _normalize(value: float, max_value: float) -> float:
    """Normalize a non-negative value to a 0-100 scale."""
    if max_value <= 0:
        return 0.0
    return _clamp((value / max_value) * 100.0)


def _condition_factor(condition_score: float) -> tuple[float, list[ReasonCode]]:
    """Lower condition score increases criticality."""
    score = _clamp(100.0 - condition_score)
    reasons = []
    if condition_score < 50:
        reasons.append(
            ReasonCode(
                factor="condition_score",
                direction="negative",
                value=condition_score,
                description="Poor asset condition increases criticality.",
            )
        )
    elif condition_score >= 85:
        reasons.append(
            ReasonCode(
                factor="condition_score",
                direction="positive",
                value=condition_score,
                description="Good asset condition reduces criticality.",
            )
        )
    return score, reasons


def _age_factor(age_years: int) -> tuple[float, list[ReasonCode]]:
    """Older assets have higher criticality (capped at 100 years)."""
    score = _normalize(age_years, 100.0)
    reasons = []
    if age_years >= 25:
        reasons.append(
            ReasonCode(
                factor="age_years",
                direction="negative",
                value=float(age_years),
                description="Asset is aged; higher failure probability.",
            )
        )
    return score, reasons


def _failure_factor(previous_failures: int) -> tuple[float, list[ReasonCode]]:
    """More previous failures increase criticality."""
    score = _normalize(previous_failures, 20.0)
    reasons = []
    if previous_failures >= 3:
        reasons.append(
            ReasonCode(
                factor="previous_failures",
                direction="negative",
                value=float(previous_failures),
                description="Repeated failure history increases risk.",
            )
        )
    return score, reasons


def _maintenance_factor(days_since_maintenance: int) -> tuple[float, list[ReasonCode]]:
    """Overdue maintenance increases criticality (capped at 365 days = 100)."""
    score = _normalize(days_since_maintenance, 365.0)
    reasons = []
    if days_since_maintenance > 180:
        reasons.append(
            ReasonCode(
                factor="days_since_maintenance",
                direction="negative",
                value=float(days_since_maintenance),
                description="Maintenance overdue; operational exposure increasing.",
            )
        )
    return score, reasons


def _weather_factor(weather_condition: str) -> tuple[float, list[ReasonCode]]:
    """Adverse weather conditions increase criticality."""
    penalty = WEATHER_CRITICALITY_PENALTY.get(weather_condition.upper(), 0.0)
    score = _clamp(penalty * 5.0)
    reasons = []
    if penalty > 0:
        reasons.append(
            ReasonCode(
                factor="weather_condition",
                direction="negative",
                value=penalty,
                description=f"Weather ({weather_condition}) degrades safety margins.",
            )
        )
    return score, reasons


def _risk_factor(risk_level: str) -> tuple[float, list[ReasonCode]]:
    """ML-predicted risk level contributes to criticality."""
    severity = RISK_SEVERITY_SCORE.get(risk_level.upper(), 1)
    bump = RISK_CRITICALITY_BUMP.get(risk_level.upper(), 10.0)
    score = bump
    reasons = []
    if risk_level.upper() in ("HIGH", "CRITICAL"):
        reasons.append(
            ReasonCode(
                factor="asset_risk",
                direction="negative",
                value=float(severity),
                description=f"ML risk model predicts {risk_level} for this asset.",
            )
        )
    return score, reasons


def _traffic_factor(
    expected_trains_per_hour: float,
) -> tuple[float, list[ReasonCode]]:
    """Higher train traffic through the section increases criticality."""
    score = _normalize(expected_trains_per_hour, 30.0)
    reasons = []
    if expected_trains_per_hour >= 5.0:
        reasons.append(
            ReasonCode(
                factor="train_traffic",
                direction="negative",
                value=expected_trains_per_hour,
                description="High train traffic amplifies failure impact.",
            )
        )
    return score, reasons


def _section_impact_factor(
    section_id: str,
    all_section_risk_scores: dict[str, float] | None = None,
) -> tuple[float, list[ReasonCode]]:
    """Critical sections (e.g. bridges, tunnels) have higher impact."""
    critical_sections = {"SEC-NDLS-RE", "SEC-BKI-JP"}
    is_critical = section_id in critical_sections
    score = 50.0 if is_critical else 10.0
    reasons = []
    if is_critical:
        reasons.append(
            ReasonCode(
                factor="section_impact",
                direction="negative",
                value=50.0,
                description=f"Section {section_id} is a high-impact corridor segment.",
            )
        )
    else:
        reasons.append(
            ReasonCode(
                factor="section_impact",
                direction="positive",
                value=10.0,
                description=f"Section {section_id} has standard operational impact.",
            )
        )
    return score, reasons


def calculate_criticality(
    asset: dict[str, Any],
    traffic_by_section: dict[str, float] | None = None,
    section_id: str | None = None,
    all_section_risk_scores: dict[str, float] | None = None,
) -> CriticalityResult:
    """Calculate a deterministic operational criticality score (0–100) and class.

    Combines asset risk level, condition, age, failure history, overdue
    maintenance, weather, train traffic, and section impact.
    """
    reasons: list[ReasonCode] = []

    risk_level = str(asset.get("risk_level", "LOW"))
    condition_score = float(asset.get("condition_score", 100))
    age_years = int(asset.get("age_years", 0))
    previous_failures = int(asset.get("previous_failures", 0))
    days_since_maintenance = int(asset.get("days_since_maintenance", 0))
    weather_condition = str(asset.get("weather_condition", "CLEAR"))
    asset_section_id = str(asset.get("section_id", section_id or "UNKNOWN"))

    risk_score, risk_reasons = _risk_factor(risk_level)
    condition_component, cond_reasons = _condition_factor(condition_score)
    age_component, age_reasons = _age_factor(age_years)
    failure_component, fail_reasons = _failure_factor(previous_failures)
    maint_component, maint_reasons = _maintenance_factor(days_since_maintenance)
    weather_component, weather_reasons = _weather_factor(weather_condition)
    traffic_score, traffic_reasons = _traffic_factor(
        (traffic_by_section or {}).get(asset_section_id, 0.0)
    )
    impact_score, impact_reasons = _section_impact_factor(
        asset_section_id, all_section_risk_scores
    )

    reasons.extend(
        risk_reasons + cond_reasons + age_reasons + fail_reasons
        + maint_reasons + weather_reasons + traffic_reasons + impact_reasons
    )

    weights = CRITICALITY_WEIGHTS
    weighted_score = (
        risk_score * weights["asset_risk"]
        + condition_component * weights["condition_score"]
        + age_component * weights["age_years"]
        + failure_component * weights["previous_failures"]
        + maint_component * weights["days_since_maintenance"]
        + weather_component * weights["weather_condition"]
        + traffic_score * weights["train_traffic"]
        + impact_score * weights["section_impact"]
    )

    score = _clamp(round(weighted_score, 2))

    if score >= CRITICALITY_THRESHOLDS["HIGH"]:
        risk_class = "CRITICAL"
    elif score >= CRITICALITY_THRESHOLDS["MEDIUM"]:
        risk_class = "HIGH"
    elif score >= 30.0:
        risk_class = "MEDIUM"
    else:
        risk_class = "LOW"

    return CriticalityResult(
        score=score,
        risk_class=risk_class,
        reasons=reasons,
    )
