"""Pure CP-SAT maintenance-window and crew-assignment optimizer."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any, Mapping

from ortools.sat.python import cp_model

from backend.app.constants import SECTION_ID_SET
from backend.app.simulation.conflict_detector import (
    LOCAL_TIMEZONE,
    movement_interval,
    require_timezone,
)


RISK_SEVERITY = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
URGENCY_SEVERITY = {"LOW": 1, "NORMAL": 2, "HIGH": 3, "EMERGENCY": 4}
PRIORITY_WEIGHT = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}


@dataclass(frozen=True, slots=True)
class ExistingMaintenanceWindow:
    maintenance_id: str
    section_id: str
    start_time: datetime
    end_time: datetime
    assigned_crew_id: str | None = None


@dataclass(frozen=True, slots=True)
class JobSpec:
    maintenance_id: str
    asset_id: str
    section_id: str
    job_type: str
    urgency: str
    required_skill: str
    minimum_duration_min: int
    preferred_start_time: datetime
    earliest_start_time: datetime
    latest_end_time: datetime
    risk_level: str
    condition_score: float


@dataclass(frozen=True, slots=True)
class OptimizationContext:
    train_movements: tuple[dict[str, Any], ...]
    crews: tuple[dict[str, Any], ...]
    traffic_by_hour: Mapping[tuple[int, int], float]
    existing_windows: tuple[ExistingMaintenanceWindow, ...] = ()
    max_train_delay_min: int = 240
    solver_timeout_seconds: float = 2.0
    alternative_gap_min: int = 15


@dataclass(frozen=True, slots=True)
class Plan:
    plan_id: str
    maintenance_id: str
    maintenance_window: dict[str, datetime]
    assigned_crew_id: str
    affected_trains: tuple[dict[str, Any], ...]
    total_train_delay_min: int
    priority_weighted_train_delay_min: int
    maintenance_delay_min: int
    risk_reduction_estimate: float
    risk_delay_penalty: float
    crew_cost: float
    reroute_available: bool
    safety_conflicts: int


@dataclass(frozen=True, slots=True)
class _CrewSlot:
    crew_id: str
    crew_size: int
    availability: str
    start_min: int
    end_min: int


@dataclass(frozen=True, slots=True)
class _TrainOccupation:
    movement: dict[str, Any]
    entry: datetime
    exit: datetime
    entry_min: int
    exit_min: int


def _crew_has_skill(crew: Mapping[str, Any], required_skill: str) -> bool:
    skills = {str(crew.get("primary_skill", "")).upper()}
    skills.update(
        skill.strip().upper()
        for skill in str(crew.get("secondary_skills", "")).split("|")
        if skill.strip()
    )
    return required_skill.upper() in skills


def _validate(job: JobSpec, context: OptimizationContext, top_n: int) -> tuple[datetime, int, int]:
    if job.section_id not in SECTION_ID_SET:
        raise ValueError(f"Unknown section: {job.section_id}")
    if job.minimum_duration_min <= 0:
        raise ValueError("minimum_duration_min must be positive")
    if job.urgency not in URGENCY_SEVERITY:
        raise ValueError(f"Unknown urgency: {job.urgency}")
    if job.risk_level not in RISK_SEVERITY:
        raise ValueError(f"Unknown risk level: {job.risk_level}")
    if not 0 <= job.condition_score <= 100:
        raise ValueError("condition_score must be between 0 and 100")
    earliest = require_timezone(job.earliest_start_time, "earliest_start_time")
    preferred = require_timezone(job.preferred_start_time, "preferred_start_time")
    latest = require_timezone(job.latest_end_time, "latest_end_time")
    if not earliest <= preferred < latest:
        raise ValueError("Maintenance planning timestamps are inconsistent")
    horizon_min = math.floor((latest - earliest).total_seconds() / 60)
    if horizon_min < job.minimum_duration_min:
        raise ValueError("Planning horizon is shorter than required duration")
    preferred_offset = round((preferred - earliest).total_seconds() / 60)
    if not 1 <= top_n <= 5:
        raise ValueError("top_n must be between 1 and 5")
    if context.max_train_delay_min < 0:
        raise ValueError("max_train_delay_min must be non-negative")
    return earliest, horizon_min, preferred_offset


def _crew_slots(
    job: JobSpec, context: OptimizationContext, origin: datetime, horizon_min: int
) -> list[_CrewSlot]:
    horizon_end = origin + timedelta(minutes=horizon_min)
    slots: list[_CrewSlot] = []
    first_day = origin.date() - timedelta(days=1)
    final_day = horizon_end.date()
    for crew in context.crews:
        availability = str(crew.get("availability", "UNAVAILABLE")).upper()
        if availability not in {"AVAILABLE", "LIMITED"}:
            continue
        if not _crew_has_skill(crew, job.required_skill):
            continue
        shift_start = time.fromisoformat(str(crew["shift_start"]))
        shift_end = time.fromisoformat(str(crew["shift_end"]))
        for day_offset in range((final_day - first_day).days + 1):
            shift_date = first_day + timedelta(days=day_offset)
            slot_start = datetime.combine(
                shift_date, shift_start, tzinfo=LOCAL_TIMEZONE
            )
            slot_end = datetime.combine(shift_date, shift_end, tzinfo=LOCAL_TIMEZONE)
            if slot_end <= slot_start:
                slot_end += timedelta(days=1)
            if slot_end <= origin or slot_start >= horizon_end:
                continue
            start_min = max(
                0, math.ceil((slot_start - origin).total_seconds() / 60)
            )
            end_min = min(
                horizon_min, math.floor((slot_end - origin).total_seconds() / 60)
            )
            if end_min - start_min >= job.minimum_duration_min:
                slots.append(
                    _CrewSlot(
                        crew_id=str(crew["crew_id"]),
                        crew_size=int(crew["crew_size"]),
                        availability=availability,
                        start_min=start_min,
                        end_min=end_min,
                    )
                )
    slots.sort(key=lambda slot: (slot.start_min, slot.crew_id, slot.end_min))
    return slots


def _train_occupations(
    job: JobSpec,
    context: OptimizationContext,
    origin: datetime,
    horizon_min: int,
) -> list[_TrainOccupation]:
    occupations: list[_TrainOccupation] = []
    for movement in context.train_movements:
        if str(movement.get("section_id")) != job.section_id:
            continue
        entry, exit_time = movement_interval(movement)
        entry_min = math.floor((entry - origin).total_seconds() / 60)
        exit_min = math.ceil((exit_time - origin).total_seconds() / 60)
        if exit_min <= 0 or entry_min >= horizon_min:
            continue
        occupations.append(
            _TrainOccupation(
                movement=movement,
                entry=entry,
                exit=exit_time,
                entry_min=entry_min,
                exit_min=exit_min,
            )
        )
    occupations.sort(
        key=lambda occupation: (
            occupation.entry,
            str(occupation.movement["train_id"]),
        )
    )
    return occupations


def _window_offsets(
    window: ExistingMaintenanceWindow, origin: datetime
) -> tuple[int, int]:
    start = require_timezone(window.start_time, "existing window start_time")
    end = require_timezone(window.end_time, "existing window end_time")
    if end <= start:
        raise ValueError(
            f"Existing window {window.maintenance_id} ends before it starts"
        )
    return (
        math.floor((start - origin).total_seconds() / 60),
        math.ceil((end - origin).total_seconds() / 60),
    )


def _risk_metrics(job: JobSpec, wait_from_earliest_min: int) -> tuple[float, float]:
    risk = RISK_SEVERITY[job.risk_level]
    urgency = URGENCY_SEVERITY[job.urgency]
    base_reduction = (
        12.0
        + (100.0 - job.condition_score) * 0.45
        + risk * 9.0
        + urgency * 4.0
    )
    risk_reduction = max(
        0.0, min(95.0, base_reduction - wait_from_earliest_min * 0.02)
    )
    risk_delay_penalty = risk * urgency * wait_from_earliest_min / 60.0
    return round(risk_reduction, 2), round(risk_delay_penalty, 2)


def _traffic_costs(
    origin: datetime,
    latest_start: int,
    traffic_by_hour: Mapping[tuple[int, int], float],
) -> list[int]:
    costs: list[int] = []
    for minute in range(latest_start + 1):
        candidate = origin + timedelta(minutes=minute)
        density = max(
            0.0, float(traffic_by_hour.get((candidate.weekday(), candidate.hour), 0.0))
        )
        costs.append(round(density * 100))
    return costs


def _delay_costs_by_start(
    *,
    latest_start: int,
    duration: int,
    occupations: list[_TrainOccupation],
    max_train_delay_min: int,
) -> tuple[list[int], list[int]]:
    """Precompute the minimum safe delay for each candidate start minute."""
    feasible_starts: list[int] = []
    weighted_costs: list[int] = []
    for start_min in range(latest_start + 1):
        end_min = start_min + duration
        weighted = 0
        feasible = True
        for occupation in occupations:
            delay = (
                0
                if start_min >= occupation.exit_min
                else max(0, end_min - occupation.entry_min)
            )
            if delay > max_train_delay_min:
                feasible = False
                break
            priority = str(occupation.movement.get("priority", "MEDIUM"))
            weighted += delay * PRIORITY_WEIGHT.get(priority, 2)
        if feasible:
            feasible_starts.append(start_min)
        weighted_costs.append(weighted)
    return feasible_starts, weighted_costs


def _heuristic_alternatives(
    *,
    job_spec: JobSpec,
    context: OptimizationContext,
    top_n: int,
    origin: datetime,
    horizon_min: int,
    preferred_offset: int,
    duration: int,
    latest_start: int,
    slots: list[_CrewSlot],
    occupations: list[_TrainOccupation],
) -> list[Plan]:
    """Enumerate the small linear MVP search space in one bounded pass.

    All hard constraints in the CP-SAT model are interval constraints.  For
    this corridor-sized problem, evaluating each candidate minute is both
    exact and substantially cheaper than starting a CP-SAT search for every
    alternative.  CP-SAT remains below as a fallback for future constraints
    that cannot be represented by this linear enumeration.
    """

    existing_offsets = [
        (*_window_offsets(window, origin), window) for window in context.existing_windows
    ]
    candidates: list[tuple[float, int, int, list[dict[str, Any]], int, int, float, float, float]] = []

    for start_min in range(latest_start + 1):
        end_min = start_min + duration
        maintenance_delay = max(0, start_min - preferred_offset)
        weighted_delay = 0
        total_delay = 0
        affected: list[dict[str, Any]] = []
        safe = True
        for occupation in occupations:
            delay = (
                0
                if start_min >= occupation.exit_min
                else max(0, end_min - occupation.entry_min)
            )
            if delay > context.max_train_delay_min:
                safe = False
                break
            if delay:
                priority = str(occupation.movement.get("priority", "MEDIUM"))
                total_delay += delay
                weighted_delay += delay * PRIORITY_WEIGHT.get(priority, 2)
                affected.append(
                    {
                        "train_id": str(occupation.movement["train_id"]),
                        "priority": priority,
                        "original_entry_time": occupation.entry.isoformat(),
                        "original_exit_time": occupation.exit.isoformat(),
                        "adjusted_entry_time": (
                            occupation.entry + timedelta(minutes=delay)
                        ).isoformat(),
                        "adjusted_exit_time": (
                            occupation.exit + timedelta(minutes=delay)
                        ).isoformat(),
                        "delay_added_min": delay,
                    }
                )
        if not safe:
            continue

        for slot_index, slot in enumerate(slots):
            if start_min < slot.start_min or end_min > slot.end_min:
                continue
            blocked = False
            for window_start, window_end, window in existing_offsets:
                overlaps = start_min < window_end and end_min > window_start
                if not overlaps:
                    continue
                if window.section_id == job_spec.section_id:
                    blocked = True
                    break
                if window.assigned_crew_id == slot.crew_id:
                    blocked = True
                    break
            if blocked:
                continue

            risk_reduction, risk_delay_penalty = _risk_metrics(job_spec, start_min)
            crew_cost = round(
                slot.crew_size * duration / 60.0 * 2.5
                + (25.0 if slot.availability == "LIMITED" else 0.0),
                2,
            )
            candidate_start = origin + timedelta(minutes=start_min)
            traffic_density = max(
                0.0,
                float(
                    context.traffic_by_hour.get(
                        (candidate_start.weekday(), candidate_start.hour), 0.0
                    )
                ),
            )
            objective = (
                10 * weighted_delay
                + 5 * maintenance_delay
                + RISK_SEVERITY[job_spec.risk_level]
                * URGENCY_SEVERITY[job_spec.urgency]
                * start_min
                + risk_delay_penalty
                + crew_cost
                + traffic_density * 100
            )
            candidates.append(
                (
                    objective,
                    start_min,
                    slot_index,
                    affected,
                    total_delay,
                    weighted_delay,
                    maintenance_delay,
                    risk_reduction,
                    risk_delay_penalty,
                )
            )

    candidates.sort(key=lambda item: (item[0], item[1], slots[item[2]].crew_id))
    selected: list[tuple[float, int, int, list[dict[str, Any]], int, int, float, float, float]] = []
    selected_starts: list[int] = []
    for candidate in candidates:
        if any(
            abs(candidate[1] - selected_start) < context.alternative_gap_min
            for selected_start in selected_starts
        ):
            continue
        selected.append(candidate)
        selected_starts.append(candidate[1])
        if len(selected) == top_n:
            break

    plans: list[Plan] = []
    for index, candidate in enumerate(selected, start=1):
        _, start_min, slot_index, affected, total_delay, weighted_delay, maintenance_delay, risk_reduction, risk_delay_penalty = candidate
        slot = slots[slot_index]
        plans.append(
            Plan(
                plan_id=f"CANDIDATE-{index:03d}",
                maintenance_id=job_spec.maintenance_id,
                maintenance_window={
                    "start": origin + timedelta(minutes=start_min),
                    "end": origin + timedelta(minutes=start_min + duration),
                },
                assigned_crew_id=slot.crew_id,
                affected_trains=tuple(affected),
                total_train_delay_min=total_delay,
                priority_weighted_train_delay_min=weighted_delay,
                maintenance_delay_min=int(maintenance_delay),
                risk_reduction_estimate=risk_reduction,
                risk_delay_penalty=risk_delay_penalty,
                crew_cost=round(
                    slot.crew_size * duration / 60.0 * 2.5
                    + (25.0 if slot.availability == "LIMITED" else 0.0),
                    2,
                ),
                reroute_available=False,
                safety_conflicts=0,
            )
        )
    return plans


def generate_maintenance_alternatives(
    job_spec: JobSpec,
    context: OptimizationContext,
    top_n: int = 5,
) -> list[Plan]:
    """Generate distinct feasible plans without reading files or mutating state."""
    origin, horizon_min, preferred_offset = _validate(job_spec, context, top_n)
    duration = int(math.ceil(job_spec.minimum_duration_min))
    latest_start = horizon_min - duration
    slots = _crew_slots(job_spec, context, origin, horizon_min)
    if not slots:
        return []
    occupations = _train_occupations(job_spec, context, origin, horizon_min)

    # The bounded corridor search is exact for the current interval model and
    # avoids repeatedly paying CP-SAT startup cost for each alternative.
    heuristic_plans = _heuristic_alternatives(
        job_spec=job_spec,
        context=context,
        top_n=top_n,
        origin=origin,
        horizon_min=horizon_min,
        preferred_offset=preferred_offset,
        duration=duration,
        latest_start=latest_start,
        slots=slots,
        occupations=occupations,
    )
    if heuristic_plans:
        return heuristic_plans

    model = cp_model.CpModel()
    start = model.NewIntVar(0, latest_start, "maintenance_start")
    end = model.NewIntVar(duration, horizon_min, "maintenance_end")
    model.Add(end == start + duration)

    maintenance_delay = model.NewIntVar(0, horizon_min, "maintenance_delay")
    model.AddMaxEquality(maintenance_delay, [start - preferred_offset, 0])

    assignment = model.NewIntVar(0, len(slots) - 1, "crew_slot")
    assignment_literals: list[cp_model.IntVar] = []
    crew_cost_terms: list[Any] = []
    for index, slot in enumerate(slots):
        selected = model.NewBoolVar(f"crew_slot_{index}")
        assignment_literals.append(selected)
        model.Add(assignment == index).OnlyEnforceIf(selected)
        model.Add(start >= slot.start_min).OnlyEnforceIf(selected)
        model.Add(end <= slot.end_min).OnlyEnforceIf(selected)
        cost = math.ceil(slot.crew_size * duration / 30)
        if slot.availability == "LIMITED":
            cost += 20
        crew_cost_terms.append(selected * cost)
    model.AddExactlyOne(assignment_literals)

    feasible_starts, priority_delay_costs = _delay_costs_by_start(
            latest_start=latest_start,
            duration=duration,
            occupations=occupations,
            max_train_delay_min=context.max_train_delay_min,
    )
    if not feasible_starts:
        return []
    model.AddAllowedAssignments([start], [[minute] for minute in feasible_starts])
    priority_delay_cost = model.NewIntVar(
        0, max(priority_delay_costs, default=0), "priority_delay_cost"
    )
    model.AddElement(start, priority_delay_costs, priority_delay_cost)

    for window_index, window in enumerate(context.existing_windows):
        window_start, window_end = _window_offsets(window, origin)
        if window_end <= 0 or window_start >= horizon_min:
            continue
        if window.section_id == job_spec.section_id:
            before_existing = model.NewBoolVar(f"before_section_{window_index}")
            model.Add(end <= window_start).OnlyEnforceIf(before_existing)
            model.Add(start >= window_end).OnlyEnforceIf(before_existing.Not())
        if window.assigned_crew_id:
            for slot_index, slot in enumerate(slots):
                if slot.crew_id != window.assigned_crew_id:
                    continue
                before_crew = model.NewBoolVar(
                    f"before_crew_{window_index}_{slot_index}"
                )
                after_crew = model.NewBoolVar(
                    f"after_crew_{window_index}_{slot_index}"
                )
                model.Add(end <= window_start).OnlyEnforceIf(before_crew)
                model.Add(start >= window_end).OnlyEnforceIf(after_crew)
                model.AddBoolOr(
                    [
                        before_crew,
                        after_crew,
                        assignment_literals[slot_index].Not(),
                    ]
                )

    traffic_cost_values = _traffic_costs(
        origin, latest_start, context.traffic_by_hour
    )
    traffic_cost = model.NewIntVar(
        0, max(traffic_cost_values, default=0), "traffic_cost"
    )
    model.AddElement(start, traffic_cost_values, traffic_cost)
    risk_urgency = (
        RISK_SEVERITY[job_spec.risk_level] * URGENCY_SEVERITY[job_spec.urgency]
    )
    model.Minimize(
        10 * priority_delay_cost
        + 5 * maintenance_delay
        + risk_urgency * start
        + traffic_cost
        + sum(crew_cost_terms)
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = context.solver_timeout_seconds
    # Parallel workers keep the bounded request-time budget reliable on the
    # larger timetable projection while the fixed seed preserves repeatable
    # candidate ordering for the demo workflow.
    solver.parameters.num_search_workers = 8
    solver.parameters.stop_after_first_solution = True
    solver.parameters.random_seed = 42

    plans: list[Plan] = []
    for candidate_index in range(top_n):
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            break
        start_min = int(solver.Value(start))
        end_min = int(solver.Value(end))
        slot_index = int(solver.Value(assignment))
        slot = slots[slot_index]
        affected: list[dict[str, Any]] = []
        total_delay = 0
        priority_weighted_delay = 0
        for occupation in occupations:
            delay = (
                0
                if start_min >= occupation.exit_min
                else max(0, end_min - occupation.entry_min)
            )
            if delay == 0:
                continue
            priority = str(occupation.movement.get("priority", "MEDIUM"))
            total_delay += delay
            priority_weighted_delay += delay * PRIORITY_WEIGHT.get(priority, 2)
            affected.append(
                {
                    "train_id": str(occupation.movement["train_id"]),
                    "priority": priority,
                    "original_entry_time": occupation.entry.isoformat(),
                    "original_exit_time": occupation.exit.isoformat(),
                    "adjusted_entry_time": (
                        occupation.entry + timedelta(minutes=delay)
                    ).isoformat(),
                    "adjusted_exit_time": (
                        occupation.exit + timedelta(minutes=delay)
                    ).isoformat(),
                    "delay_added_min": delay,
                }
            )

        risk_reduction, risk_delay_penalty = _risk_metrics(job_spec, start_min)
        crew_cost = round(
            slot.crew_size * duration / 60.0 * 2.5
            + (25.0 if slot.availability == "LIMITED" else 0.0),
            2,
        )
        plans.append(
            Plan(
                plan_id=f"CANDIDATE-{candidate_index + 1:03d}",
                maintenance_id=job_spec.maintenance_id,
                maintenance_window={
                    "start": origin + timedelta(minutes=start_min),
                    "end": origin + timedelta(minutes=end_min),
                },
                assigned_crew_id=slot.crew_id,
                affected_trains=tuple(affected),
                total_train_delay_min=total_delay,
                priority_weighted_train_delay_min=priority_weighted_delay,
                maintenance_delay_min=int(solver.Value(maintenance_delay)),
                risk_reduction_estimate=risk_reduction,
                risk_delay_penalty=risk_delay_penalty,
                crew_cost=crew_cost,
                reroute_available=False,
                safety_conflicts=0,
            )
        )

        lower = max(0, start_min - context.alternative_gap_min + 1)
        upper = min(latest_start, start_min + context.alternative_gap_min - 1)
        model.AddForbiddenAssignments(
            [start, assignment],
            [[minute, slot_index] for minute in range(lower, upper + 1)],
        )
    return plans
