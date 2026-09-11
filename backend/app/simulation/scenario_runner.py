"""Stage 3 scenario assembly for the deterministic SimPy engine."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, time
from typing import Any, Mapping

from backend.app.config import DATA_DIR, GRAPH_PATH, MAINTENANCE_REQUESTS_PATH
from backend.app.constants import SECTION_IDS
from backend.app.graph.railway_graph import RailwayGraph
from backend.app.maintenance_repository import MaintenanceRepository
from backend.app.repository import CsvRepository
from backend.app.simulation.railway_simulator import (
    SimulationDayConfig,
    TrainSchedule,
    TrainSectionSchedule,
    parse_plan_datetime,
    simulate_plan,
)


EXPECTED_CORRIDOR_PATH = ["NDLS", "RE", "AWR", "BKI", "JP"]


def _minutes(clock: object) -> float:
    parsed = time.fromisoformat(str(clock))
    return parsed.hour * 60 + parsed.minute + parsed.second / 60.0


def _build_train_schedules(
    rows: list[dict[str, Any]],
) -> tuple[TrainSchedule, ...]:
    by_train: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_train[str(row["train_id"])].append(row)

    section_order = {section_id: index for index, section_id in enumerate(SECTION_IDS)}
    schedules: list[TrainSchedule] = []
    for train_id in sorted(by_train):
        train_rows = sorted(
            by_train[train_id], key=lambda row: section_order[str(row["section_id"])]
        )
        actual_sections = tuple(str(row["section_id"]) for row in train_rows)
        if actual_sections != SECTION_IDS:
            raise ValueError(
                f"Train {train_id} does not contain the complete ordered corridor"
            )

        section_schedules: list[TrainSectionSchedule] = []
        previous_exit = -1.0
        day_offset = 0.0
        for row in train_rows:
            entry = _minutes(row["scheduled_entry_time"]) + day_offset
            while entry < previous_exit:
                day_offset += 1440.0
                entry += 1440.0
            exit_minute = _minutes(row["scheduled_exit_time"]) + day_offset
            if exit_minute <= entry:
                exit_minute += 1440.0
            section_schedules.append(
                TrainSectionSchedule(
                    section_id=str(row["section_id"]),
                    scheduled_entry_min=entry,
                    scheduled_exit_min=exit_minute,
                )
            )
            previous_exit = exit_minute
        schedules.append(
            TrainSchedule(
                train_id=train_id,
                priority=str(train_rows[0]["priority"]),
                sections=tuple(section_schedules),
            )
        )
    return tuple(schedules)


def run_scenario(
    plan: Mapping[str, Any],
    simulation_date: date,
    *,
    maintenance_requirement: Mapping[str, Any] | None = None,
    repository: CsvRepository | None = None,
    railway_graph: RailwayGraph | None = None,
    random_seed: int = 42,
) -> dict[str, Any]:
    """Validate dependencies, assemble a day, and run one batch scenario."""
    if maintenance_requirement is None:
        maintenance_requirement = MaintenanceRepository(
            MAINTENANCE_REQUESTS_PATH
        ).get(str(plan.get("maintenance_id", "")))
        if maintenance_requirement is None:
            raise ValueError("Plan maintenance requirement is unavailable")
    repository = repository or CsvRepository.from_data_dir(DATA_DIR)
    railway_graph = railway_graph or RailwayGraph.load_graph(GRAPH_PATH)
    if str(plan.get("maintenance_id")) != str(
        maintenance_requirement.get("maintenance_id")
    ):
        raise ValueError("Plan and maintenance requirement do not match")
    if int(plan.get("safety_conflicts", 0)) != 0:
        raise ValueError("Unsafe Stage 2 plans cannot be simulated")
    if railway_graph.get_path_stations("NDLS", "JP") != EXPECTED_CORRIDOR_PATH:
        raise ValueError("The loaded graph is not the supported corridor")
    graph_sections = tuple(
        str(section["section_id"]) for section in railway_graph.get_all_sections()
    )
    if graph_sections != SECTION_IDS:
        raise ValueError("The loaded graph section order is invalid")

    section_id = str(maintenance_requirement["section_id"])
    if section_id not in graph_sections:
        raise ValueError("Maintenance section is absent from the corridor graph")
    window = plan.get("maintenance_window")
    if not isinstance(window, Mapping):
        raise ValueError("Plan maintenance_window is invalid")
    start = parse_plan_datetime(plan, "start")
    end = parse_plan_datetime(plan, "end")
    predicted_duration = round((end - start).total_seconds() / 60)
    if predicted_duration <= 0:
        raise ValueError("Plan maintenance duration must be positive")

    timetable = repository.timetable_for_date(simulation_date)
    schedules = _build_train_schedules(timetable)
    config = SimulationDayConfig(
        simulation_date=simulation_date,
        trains=schedules,
        maintenance_section_id=section_id,
        predicted_duration_min=predicted_duration,
        random_seed=random_seed,
    )
    return simulate_plan(plan, config)
