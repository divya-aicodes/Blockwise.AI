"""Centralized, explainable scoring and deterministic plan ranking."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from math import inf
from typing import Any, Iterable, Mapping


@dataclass(frozen=True, slots=True)
class ScoreWeights:
    safety_conflict: float = 1000.0
    priority_weighted_train_delay: float = 10.0
    maintenance_delay: float = 5.0
    risk_delay_penalty: float = 1.0
    crew_cost_component: float = 1.0


DEFAULT_WEIGHTS = ScoreWeights()


def _plan_dict(plan: Any) -> dict[str, Any]:
    if is_dataclass(plan):
        return asdict(plan)
    if isinstance(plan, Mapping):
        return dict(plan)
    raise TypeError("Each plan must be a dataclass or mapping")


def score_plan(plan: Any, *, weights: ScoreWeights = DEFAULT_WEIGHTS) -> float:
    """Return a lower-is-better score; unsafe plans are invalid (infinite)."""
    payload = _plan_dict(plan)
    safety_conflicts = int(payload.get("safety_conflicts", 0))
    if safety_conflicts:
        return inf
    return round(
        weights.safety_conflict * safety_conflicts
        + weights.priority_weighted_train_delay
        * float(payload.get("priority_weighted_train_delay_min", 0))
        + weights.maintenance_delay
        * float(payload.get("maintenance_delay_min", 0))
        + weights.risk_delay_penalty
        * float(payload.get("risk_delay_penalty", 0))
        + weights.crew_cost_component
        * float(payload.get("crew_cost", payload.get("crew_cost_component", 0))),
        6,
    )


def rank_plans(
    plans: Iterable[Any], *, weights: ScoreWeights = DEFAULT_WEIGHTS
) -> list[dict[str, Any]]:
    """Exclude unsafe candidates, then score and rank deterministically."""
    scored: list[dict[str, Any]] = []
    for plan in plans:
        payload = _plan_dict(plan)
        score = score_plan(payload, weights=weights)
        if score == inf:
            continue
        payload["overall_score"] = score
        scored.append(payload)
    scored.sort(
        key=lambda item: (
            float(item["overall_score"]),
            str(item["maintenance_window"]["start"]),
            str(item["assigned_crew_id"]),
        )
    )
    for rank, plan in enumerate(scored, start=1):
        plan["rank"] = rank
        plan["plan_id"] = f"P{rank:03d}"
    return scored


# Backwards-compatible aliases for callers created during the Stage 2 migration.
calculate_score = score_plan
rank_alternatives = rank_plans
