from __future__ import annotations

from datetime import date

import pytest

from backend.app.constants import SECTION_IDS
from backend.app.simulation.railway_simulator import (
    SimulationDayConfig,
    TrainSchedule,
    TrainSectionSchedule,
    simulate_plan,
)


SIMULATION_DATE = date(2026, 9, 1)


def _plan(
    *,
    plan_id: str = "P001",
    section_id: str = SECTION_IDS[0],
    start: str = "2026-09-01T01:10:00+05:30",
    end: str = "2026-09-01T02:10:00+05:30",
    affected: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "plan_id": plan_id,
        "maintenance_id": "M001",
        "section_id": section_id,
        "maintenance_window": {"start": start, "end": end},
        "affected_trains": affected or [],
        "total_train_delay_min": sum(
            int(train["delay_added_min"]) for train in (affected or [])
        ),
        "safety_conflicts": 0,
    }


def _train(
    train_id: str = "TRN-TEST-1",
    *,
    first_entry: int = 80,
    gap: int = 10,
    duration: int = 20,
) -> TrainSchedule:
    rows: list[TrainSectionSchedule] = []
    entry = first_entry
    for section_id in SECTION_IDS:
        rows.append(
            TrainSectionSchedule(
                section_id=section_id,
                scheduled_entry_min=entry,
                scheduled_exit_min=entry + duration,
            )
        )
        entry += duration + gap
    return TrainSchedule(train_id=train_id, priority="HIGH", sections=tuple(rows))


def _config(
    *,
    section_id: str = SECTION_IDS[0],
    trains: tuple[TrainSchedule, ...] | None = None,
    duration: int = 60,
    seed: int = 42,
) -> SimulationDayConfig:
    return SimulationDayConfig(
        simulation_date=SIMULATION_DATE,
        trains=trains if trains is not None else (_train(),),
        maintenance_section_id=section_id,
        predicted_duration_min=duration,
        random_seed=seed,
    )


def test_train_moves_in_corridor_order_and_maintenance_is_exclusive() -> None:
    result = simulate_plan(_plan(), _config())
    events = result["train_results"][0]["section_events"]

    assert [event["section_id"] for event in events] == list(SECTION_IDS)
    assert all(
        later["simulated_entry_time"] >= earlier["simulated_exit_time"]
        for earlier, later in zip(events, events[1:])
    )
    assert events[0]["simulated_entry_time"] >= result["maintenance"]["simulated_end"]
    assert events[0]["additional_wait_min"] > 0
    assert result["kpis"]["conflicts_detected"] == 0
    assert result["safety_events"] == []
    assert result["kpis"]["maintenance_completed"] is True


def test_stage_two_delay_is_applied_and_propagated_without_extra_wait() -> None:
    affected = [{"train_id": "TRN-TEST-1", "delay_added_min": 80}]
    plan = _plan(
        section_id=SECTION_IDS[1],
        start="2026-09-01T00:50:00+05:30",
        end="2026-09-01T01:20:00+05:30",
        affected=affected,
    )
    result = simulate_plan(
        plan,
        _config(section_id=SECTION_IDS[1], trains=(_train(first_entry=20),), duration=30),
    )
    train = result["train_results"][0]

    assert train["planned_delay_min"] == 80
    assert train["additional_simulation_wait_min"] == 0
    assert train["total_delay_min"] == 80
    assert train["section_events"][0]["planned_delay_min"] == 0
    assert all(
        event["planned_delay_min"] == 80
        for event in train["section_events"][1:]
    )


def test_unaffected_train_has_no_unnecessary_delay_in_sparse_scenario() -> None:
    plan = _plan(
        start="2026-09-01T00:05:00+05:30",
        end="2026-09-01T00:15:00+05:30",
    )
    result = simulate_plan(plan, _config(trains=(_train(first_entry=120),), duration=10))

    assert result["train_results"][0]["total_delay_min"] == 0
    assert result["kpis"]["total_delay_min"] == 0
    assert result["kpis"]["affected_trains_count"] == 0


def test_simulation_is_repeatable_for_the_same_plan_date_and_seed() -> None:
    plan = _plan()
    config = _config()
    assert simulate_plan(plan, config) == simulate_plan(plan, config)


def test_duration_variation_is_seeded_small_and_reported_in_kpis() -> None:
    result = simulate_plan(_plan(), _config())
    maintenance = result["maintenance"]
    assert -5 <= maintenance["duration_variation_min"] <= 5
    assert maintenance["simulated_duration_min"] == (
        maintenance["predicted_duration_min"]
        + maintenance["duration_variation_min"]
    )
    assert result["kpis"]["predicted_maintenance_duration_min"] == 60
    assert result["kpis"]["simulated_maintenance_duration_min"] == maintenance[
        "simulated_duration_min"
    ]


def test_different_maintenance_windows_change_delay_kpis() -> None:
    blocking = simulate_plan(_plan(plan_id="P001"), _config())
    clear = simulate_plan(
        _plan(
            plan_id="P002",
            start="2026-09-01T03:20:00+05:30",
            end="2026-09-01T04:20:00+05:30",
        ),
        _config(),
    )
    assert blocking["kpis"]["total_delay_min"] > clear["kpis"]["total_delay_min"]


def test_delay_aggregates_match_train_results() -> None:
    trains = (_train("TRN-TEST-1", first_entry=80), _train("TRN-TEST-2", first_entry=100))
    result = simulate_plan(_plan(), _config(trains=trains))
    delays = [train["total_delay_min"] for train in result["train_results"]]
    expected_ids = sorted(
        train["train_id"]
        for train in result["train_results"]
        if train["total_delay_min"] > 0
    )
    assert result["kpis"]["total_delay_min"] == sum(delays)
    assert result["kpis"]["max_single_train_delay_min"] == max(delays)
    assert result["kpis"]["affected_train_ids"] == expected_ids
    assert result["kpis"]["affected_trains_count"] == len(expected_ids)


def test_maintenance_acquires_all_baseline_capacity_slots() -> None:
    trains = (
        _train("TRN-TEST-1", first_entry=80),
        _train("TRN-TEST-2", first_entry=90),
    )
    result = simulate_plan(_plan(), _config(trains=trains))
    maintenance_end = result["maintenance"]["simulated_end"]
    first_section_events = [
        train["section_events"][0] for train in result["train_results"]
    ]
    assert all(
        event["simulated_entry_time"] >= maintenance_end
        for event in first_section_events
    )
    assert result["kpis"]["conflicts_detected"] == 0


@pytest.mark.parametrize("section_id", SECTION_IDS)
def test_all_corridor_sections_can_be_maintenance_targets(section_id: str) -> None:
    result = simulate_plan(
        _plan(section_id=section_id, start="2026-09-01T00:05:00+05:30", end="2026-09-01T00:15:00+05:30"),
        _config(section_id=section_id, trains=(), duration=10),
    )
    assert result["section_id"] == section_id
    assert result["kpis"]["maintenance_completed"] is True
    assert result["kpis"]["conflicts_detected"] == 0


def test_unsafe_optimizer_plan_is_rejected() -> None:
    plan = _plan()
    plan["safety_conflicts"] = 1
    with pytest.raises(ValueError, match="Unsafe Stage 2 plans"):
        simulate_plan(plan, _config())
