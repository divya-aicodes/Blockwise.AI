from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from math import inf
from zoneinfo import ZoneInfo

from backend.app.optimization.scheduler import (
    ExistingMaintenanceWindow,
    JobSpec,
    OptimizationContext,
    PRIORITY_WEIGHT,
    generate_maintenance_alternatives,
)
from backend.app.optimization.scoring import rank_plans, score_plan


IST = ZoneInfo("Asia/Kolkata")


def _movement(
    train_id: str, entry: str, exit_time: str, priority: str
) -> dict[str, object]:
    return {
        "train_id": train_id,
        "section_id": "SEC-NDLS-RE",
        "date": "2025-01-01",
        "actual_entry_time": entry,
        "actual_exit_time": exit_time,
        "scheduled_entry_time": entry,
        "scheduled_exit_time": exit_time,
        "priority": priority,
    }


def _job(*, duration: int = 60, skill: str = "TRACK") -> JobSpec:
    return JobSpec(
        maintenance_id="M001",
        asset_id="AST-01-01",
        section_id="SEC-NDLS-RE",
        job_type="CORRECTIVE",
        urgency="HIGH",
        required_skill=skill,
        minimum_duration_min=duration,
        preferred_start_time=datetime(2025, 1, 1, 8, 0, tzinfo=IST),
        earliest_start_time=datetime(2025, 1, 1, 8, 0, tzinfo=IST),
        latest_end_time=datetime(2025, 1, 1, 16, 0, tzinfo=IST),
        risk_level="HIGH",
        condition_score=45,
    )


def _context(
    *,
    existing_windows: tuple[ExistingMaintenanceWindow, ...] = (),
    crews: tuple[dict[str, object], ...] | None = None,
) -> OptimizationContext:
    return OptimizationContext(
        train_movements=(
            _movement("T-HIGH", "08:30:00", "09:00:00", "HIGH"),
            _movement("T-LOW", "10:00:00", "10:30:00", "LOW"),
        ),
        crews=crews
        or (
            {
                "crew_id": "C1",
                "primary_skill": "TRACK",
                "secondary_skills": "SIGNAL",
                "shift_start": "06:00:00",
                "shift_end": "14:00:00",
                "crew_size": 5,
                "availability": "AVAILABLE",
            },
            {
                "crew_id": "C2",
                "primary_skill": "SIGNAL",
                "secondary_skills": "TRACK",
                "shift_start": "08:00:00",
                "shift_end": "16:00:00",
                "crew_size": 3,
                "availability": "AVAILABLE",
            },
            {
                "crew_id": "C3",
                "primary_skill": "TRACK",
                "secondary_skills": "",
                "shift_start": "08:00:00",
                "shift_end": "16:00:00",
                "crew_size": 2,
                "availability": "UNAVAILABLE",
            },
        ),
        traffic_by_hour={(2, hour): 1.0 for hour in range(24)},
        existing_windows=existing_windows,
        max_train_delay_min=180,
        solver_timeout_seconds=2,
    )


def _crew_skills(context: OptimizationContext, crew_id: str) -> set[str]:
    crew = next(item for item in context.crews if item["crew_id"] == crew_id)
    return {str(crew["primary_skill"]), *str(crew["secondary_skills"]).split("|")}


def test_scheduler_enforces_duration_horizon_crew_and_safety() -> None:
    job = _job(duration=60)
    context = _context()
    plans = generate_maintenance_alternatives(job, context, top_n=5)
    assert 3 <= len(plans) <= 5
    assert len(
        {
            (plan.maintenance_window["start"], plan.assigned_crew_id)
            for plan in plans
        }
    ) == len(plans)
    for plan in plans:
        start = plan.maintenance_window["start"]
        end = plan.maintenance_window["end"]
        assert (end - start).total_seconds() / 60 >= job.minimum_duration_min
        assert start >= job.earliest_start_time
        assert end <= job.latest_end_time
        assert job.required_skill in _crew_skills(context, plan.assigned_crew_id)
        assert plan.assigned_crew_id != "C3"
        assert plan.safety_conflicts == 0
        assert all(train["delay_added_min"] >= 0 for train in plan.affected_trains)
        for train in plan.affected_trains:
            adjusted_entry = datetime.fromisoformat(train["adjusted_entry_time"])
            assert adjusted_entry >= end


def test_scheduler_honors_same_section_and_crew_existing_window() -> None:
    window = ExistingMaintenanceWindow(
        maintenance_id="M999",
        section_id="SEC-NDLS-RE",
        start_time=datetime(2025, 1, 1, 9, 0, tzinfo=IST),
        end_time=datetime(2025, 1, 1, 11, 0, tzinfo=IST),
        assigned_crew_id="C1",
    )
    plans = generate_maintenance_alternatives(
        _job(), _context(existing_windows=(window,)), top_n=3
    )
    assert plans
    for plan in plans:
        assert (
            plan.maintenance_window["end"] <= window.start_time
            or plan.maintenance_window["start"] >= window.end_time
        )


def test_overnight_shift_is_supported() -> None:
    overnight_job = replace(
        _job(),
        preferred_start_time=datetime(2025, 1, 1, 23, 0, tzinfo=IST),
        earliest_start_time=datetime(2025, 1, 1, 22, 0, tzinfo=IST),
        latest_end_time=datetime(2025, 1, 2, 6, 0, tzinfo=IST),
    )
    overnight_crew = (
        {
            "crew_id": "N1",
            "primary_skill": "TRACK",
            "secondary_skills": "",
            "shift_start": "22:00:00",
            "shift_end": "06:00:00",
            "crew_size": 4,
            "availability": "AVAILABLE",
        },
    )
    context = OptimizationContext(
        train_movements=(),
        crews=overnight_crew,
        traffic_by_hour={},
    )
    plans = generate_maintenance_alternatives(overnight_job, context, top_n=3)
    assert plans
    assert all(plan.assigned_crew_id == "N1" for plan in plans)


def test_no_fake_plan_when_infeasible() -> None:
    assert (
        generate_maintenance_alternatives(
            _job(skill="UNAVAILABLE_SKILL"), _context(), top_n=3
        )
        == []
    )


def test_risk_urgency_and_traffic_create_an_explainable_tradeoff() -> None:
    short_job = replace(
        _job(duration=30),
        latest_end_time=datetime(2025, 1, 1, 10, 0, tzinfo=IST),
    )
    crew = (
        {
            "crew_id": "C1",
            "primary_skill": "TRACK",
            "secondary_skills": "",
            "shift_start": "06:00:00",
            "shift_end": "14:00:00",
            "crew_size": 4,
            "availability": "AVAILABLE",
        },
    )
    context = OptimizationContext(
        train_movements=(),
        crews=crew,
        traffic_by_hour={(2, 8): 5.0, (2, 9): 0.0},
    )
    low = replace(short_job, risk_level="LOW", urgency="LOW")
    urgent = replace(short_job, risk_level="CRITICAL", urgency="EMERGENCY")
    low_plan = generate_maintenance_alternatives(low, context, top_n=1)[0]
    urgent_plan = generate_maintenance_alternatives(urgent, context, top_n=1)[0]
    assert low_plan.maintenance_window["start"].hour == 9
    assert urgent_plan.maintenance_window["start"].hour == 8


def test_scoring_penalizes_delay_priority_and_is_deterministic() -> None:
    base = {
        "plan_id": "CANDIDATE-001",
        "maintenance_id": "M001",
        "maintenance_window": {
            "start": datetime(2025, 1, 1, 8, 0, tzinfo=IST),
            "end": datetime(2025, 1, 1, 9, 0, tzinfo=IST),
        },
        "assigned_crew_id": "C1",
        "safety_conflicts": 0,
        "priority_weighted_train_delay_min": 10,
        "maintenance_delay_min": 0,
        "risk_delay_penalty": 0,
        "crew_cost_component": 10,
    }
    more_train_delay = {**base, "priority_weighted_train_delay_min": 20}
    more_maintenance_delay = {**base, "maintenance_delay_min": 20}
    assert score_plan(more_train_delay) > score_plan(base)
    assert score_plan(more_maintenance_delay) > score_plan(base)
    assert score_plan({**base, "safety_conflicts": 1}) == inf
    assert PRIORITY_WEIGHT["HIGH"] > PRIORITY_WEIGHT["MEDIUM"] > PRIORITY_WEIGHT["LOW"]
    first = rank_plans([more_train_delay, base, more_maintenance_delay])
    second = rank_plans([more_train_delay, base, more_maintenance_delay])
    assert first == second
    assert first[0]["plan_id"] == "P001"
