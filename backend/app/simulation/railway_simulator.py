"""Deterministic 24-hour SimPy railway-corridor digital twin."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Mapping

import simpy

from backend.app.constants import SECTION_IDS
from backend.app.simulation.conflict_detector import LOCAL_TIMEZONE, require_timezone


@dataclass(frozen=True, slots=True)
class TrainSectionSchedule:
    section_id: str
    scheduled_entry_min: float
    scheduled_exit_min: float

    @property
    def travel_duration_min(self) -> float:
        return self.scheduled_exit_min - self.scheduled_entry_min


@dataclass(frozen=True, slots=True)
class TrainSchedule:
    train_id: str
    priority: str
    sections: tuple[TrainSectionSchedule, ...]


@dataclass(frozen=True, slots=True)
class SimulationDayConfig:
    simulation_date: date
    trains: tuple[TrainSchedule, ...]
    maintenance_section_id: str
    predicted_duration_min: int
    section_ids: tuple[str, ...] = SECTION_IDS
    random_seed: int = 42
    horizon_min: int = 1440


class Section:
    """Exclusive controlled occupancy resource for one macro section."""

    def __init__(
        self, environment: simpy.Environment, section_id: str, capacity: int
    ) -> None:
        self.section_id = section_id
        self.capacity = capacity
        self.resource = simpy.PriorityResource(environment, capacity=capacity)
        self.occupant_train_ids: set[str] = set()
        self.maintenance_active = False


class MaintenanceBlock:
    """Maintenance process that holds its target section exclusively."""

    def __init__(
        self,
        environment: simpy.Environment,
        section: Section,
        *,
        maintenance_id: str,
        plan_id: str,
        planned_start_min: float,
        predicted_duration_min: int,
        simulated_duration_min: int,
        state: dict[str, Any],
    ) -> None:
        self.environment = environment
        self.section = section
        self.maintenance_id = maintenance_id
        self.plan_id = plan_id
        self.planned_start_min = planned_start_min
        self.predicted_duration_min = predicted_duration_min
        self.simulated_duration_min = simulated_duration_min
        self.state = state
        self.simulated_start_min: float | None = None
        self.simulated_end_min: float | None = None
        self.completion_status = "NOT_STARTED"

    def process(self):
        yield self.environment.timeout(max(0.0, self.planned_start_min - self.environment.now))
        self.completion_status = "WAITING_FOR_SECTION"
        requests = [
            self.section.resource.request(priority=0)
            for _ in range(self.section.capacity)
        ]
        try:
            yield self.environment.all_of(requests)
            self.simulated_start_min = self.environment.now
            if self.section.occupant_train_ids:
                self.state["safety_conflicts"].append(
                    {
                        "time_min": self.environment.now,
                        "section_id": self.section.section_id,
                        "type": "MAINTENANCE_TRAIN_OVERLAP",
                    }
                )
            self.section.maintenance_active = True
            self.completion_status = "IN_PROGRESS"
            self.state["maintenance_events"].append(
                {
                    "event": "MAINTENANCE_STARTED",
                    "time_min": self.environment.now,
                    "section_id": self.section.section_id,
                }
            )
            yield self.environment.timeout(self.simulated_duration_min)
            self.section.maintenance_active = False
            self.simulated_end_min = self.environment.now
            self.completion_status = "COMPLETED"
            self.state["maintenance_events"].append(
                {
                    "event": "MAINTENANCE_COMPLETED",
                    "time_min": self.environment.now,
                    "section_id": self.section.section_id,
                }
            )
        finally:
            for request in requests:
                if request.triggered:
                    self.section.resource.release(request)
                else:
                    request.cancel()


class Train:
    """Sequential train process across the four physical macro sections."""

    def __init__(
        self,
        environment: simpy.Environment,
        schedule: TrainSchedule,
        sections: Mapping[str, Section],
        *,
        maintenance_section_id: str,
        planned_delay_min: int,
        state: dict[str, Any],
    ) -> None:
        self.environment = environment
        self.schedule = schedule
        self.sections = sections
        self.maintenance_section_id = maintenance_section_id
        self.planned_delay_min = planned_delay_min
        self.state = state
        self.events: list[dict[str, Any]] = []
        self.completed = False

    def process(self):
        maintenance_index = list(self.sections).index(self.maintenance_section_id)
        previous_exit = 0.0
        for section_index, scheduled in enumerate(self.schedule.sections):
            section = self.sections[scheduled.section_id]
            applied_plan_delay = (
                self.planned_delay_min if section_index >= maintenance_index else 0
            )
            adjusted_scheduled_entry = (
                scheduled.scheduled_entry_min + applied_plan_delay
            )
            intended_entry = max(adjusted_scheduled_entry, previous_exit)
            yield self.environment.timeout(max(0.0, intended_entry - self.environment.now))
            request_time = self.environment.now
            with section.resource.request(priority=1) as request:
                yield request
                simulated_entry = self.environment.now
                if section.maintenance_active:
                    self.state["safety_conflicts"].append(
                        {
                            "time_min": simulated_entry,
                            "section_id": section.section_id,
                            "train_id": self.schedule.train_id,
                            "type": "TRAIN_MAINTENANCE_OVERLAP",
                        }
                    )
                section.occupant_train_ids.add(self.schedule.train_id)
                yield self.environment.timeout(scheduled.travel_duration_min)
                simulated_exit = self.environment.now
                section.occupant_train_ids.remove(self.schedule.train_id)

            additional_wait = max(0.0, simulated_entry - adjusted_scheduled_entry)
            total_delay = max(0.0, simulated_exit - scheduled.scheduled_exit_min)
            event = {
                "train_id": self.schedule.train_id,
                "section_id": scheduled.section_id,
                "scheduled_entry_min": scheduled.scheduled_entry_min,
                "scheduled_exit_min": scheduled.scheduled_exit_min,
                "simulated_entry_min": simulated_entry,
                "simulated_exit_min": simulated_exit,
                "planned_delay_min": applied_plan_delay,
                "additional_wait_min": additional_wait,
                "delay_added_min": total_delay,
                "total_delay_min": total_delay,
                "resource_queue_wait_min": max(0.0, simulated_entry - request_time),
            }
            self.events.append(event)
            self.state["train_events"].append(event)
            previous_exit = simulated_exit
        self.completed = len(self.events) == len(self.schedule.sections)


def parse_plan_datetime(plan: Mapping[str, Any], field: str) -> datetime:
    raw = plan["maintenance_window"][field]
    value = raw if isinstance(raw, datetime) else datetime.fromisoformat(str(raw))
    return require_timezone(value, f"maintenance_window.{field}")


def _minute_to_datetime(simulation_date: date, minute: float) -> datetime:
    return datetime.combine(
        simulation_date, time.min, tzinfo=LOCAL_TIMEZONE
    ) + timedelta(minutes=minute)


def _duration_variation(
    plan_id: str, simulation_date: date, seed: int
) -> int:
    material = f"{plan_id}|{simulation_date.isoformat()}|{seed}".encode("utf-8")
    digest = hashlib.sha256(material).digest()
    return int(digest[0] % 11) - 5


def _round_minutes(value: float) -> int:
    return max(0, round(value))


def _baseline_section_capacities(
    trains: tuple[TrainSchedule, ...], section_ids: tuple[str, ...]
) -> dict[str, int]:
    """Find the minimum slots that reproduce the conflict-free base timetable."""
    events: dict[str, list[tuple[float, int]]] = {
        section_id: [] for section_id in section_ids
    }
    for train in trains:
        for scheduled in train.sections:
            if scheduled.section_id not in events:
                raise ValueError(
                    f"Train {train.train_id} references an unknown section"
                )
            events[scheduled.section_id].append((scheduled.scheduled_entry_min, 1))
            events[scheduled.section_id].append((scheduled.scheduled_exit_min, -1))

    capacities: dict[str, int] = {}
    for section_id, section_events in events.items():
        occupancy = 0
        peak = 0
        for _, delta in sorted(section_events, key=lambda event: (event[0], event[1])):
            occupancy += delta
            peak = max(peak, occupancy)
        capacities[section_id] = max(1, peak)
    return capacities


def simulate_plan(
    plan: Mapping[str, Any], day_config: SimulationDayConfig
) -> dict[str, Any]:
    """Run one repeatable batch simulation without accessing FastAPI or files."""
    if day_config.maintenance_section_id not in day_config.section_ids:
        raise ValueError("Maintenance section is not part of the simulation corridor")
    if day_config.predicted_duration_min <= 0:
        raise ValueError("predicted_duration_min must be positive")
    if int(plan.get("safety_conflicts", 0)) != 0:
        raise ValueError("Unsafe Stage 2 plans cannot be simulated")

    planned_start = parse_plan_datetime(plan, "start")
    planned_start_min = (
        planned_start.hour * 60
        + planned_start.minute
        + planned_start.second / 60.0
    )
    variation = _duration_variation(
        str(plan["plan_id"]), day_config.simulation_date, day_config.random_seed
    )
    simulated_duration = max(1, day_config.predicted_duration_min + variation)

    environment = simpy.Environment()
    capacities = _baseline_section_capacities(
        day_config.trains, day_config.section_ids
    )
    sections = {
        section_id: Section(environment, section_id, capacities[section_id])
        for section_id in day_config.section_ids
    }
    state: dict[str, Any] = {
        "train_events": [],
        "maintenance_events": [],
        "safety_conflicts": [],
    }
    planned_delays = {
        str(train["train_id"]): int(train.get("delay_added_min", 0))
        for train in plan.get("affected_trains", [])
    }
    maintenance = MaintenanceBlock(
        environment,
        sections[day_config.maintenance_section_id],
        maintenance_id=str(plan["maintenance_id"]),
        plan_id=str(plan["plan_id"]),
        planned_start_min=planned_start_min,
        predicted_duration_min=day_config.predicted_duration_min,
        simulated_duration_min=simulated_duration,
        state=state,
    )
    environment.process(maintenance.process())
    train_processes: list[Train] = []
    for train_schedule in day_config.trains:
        train = Train(
            environment,
            train_schedule,
            sections,
            maintenance_section_id=day_config.maintenance_section_id,
            planned_delay_min=planned_delays.get(train_schedule.train_id, 0),
            state=state,
        )
        train_processes.append(train)
        environment.process(train.process())
    environment.run(until=day_config.horizon_min)

    train_results: list[dict[str, Any]] = []
    for train in train_processes:
        if not train.events:
            continue
        total_delay = _round_minutes(train.events[-1]["total_delay_min"])
        planned_delay = train.planned_delay_min
        additional_wait = max(0, total_delay - planned_delay)
        serialized_events: list[dict[str, Any]] = []
        for event in train.events:
            serialized_events.append(
                {
                    "train_id": event["train_id"],
                    "section_id": event["section_id"],
                    "scheduled_entry_time": _minute_to_datetime(
                        day_config.simulation_date, event["scheduled_entry_min"]
                    ).isoformat(),
                    "scheduled_exit_time": _minute_to_datetime(
                        day_config.simulation_date, event["scheduled_exit_min"]
                    ).isoformat(),
                    "simulated_entry_time": _minute_to_datetime(
                        day_config.simulation_date, event["simulated_entry_min"]
                    ).isoformat(),
                    "simulated_exit_time": _minute_to_datetime(
                        day_config.simulation_date, event["simulated_exit_min"]
                    ).isoformat(),
                    "planned_delay_min": _round_minutes(event["planned_delay_min"]),
                    "additional_wait_min": _round_minutes(
                        event["additional_wait_min"]
                    ),
                    "delay_added_min": _round_minutes(event["delay_added_min"]),
                    "total_delay_min": _round_minutes(event["total_delay_min"]),
                }
            )
        train_results.append(
            {
                "train_id": train.schedule.train_id,
                "priority": train.schedule.priority,
                "planned_delay_min": planned_delay,
                "additional_simulation_wait_min": additional_wait,
                "total_delay_min": total_delay,
                "completion_status": "COMPLETED" if train.completed else "INCOMPLETE",
                "section_events": serialized_events,
            }
        )

    delays = [result["total_delay_min"] for result in train_results]
    affected_train_ids = sorted(
        result["train_id"] for result in train_results if result["total_delay_min"] > 0
    )
    total_delay = sum(delays)
    maintenance_completed = maintenance.completion_status == "COMPLETED"
    simulated_start = (
        _minute_to_datetime(day_config.simulation_date, maintenance.simulated_start_min)
        if maintenance.simulated_start_min is not None
        else None
    )
    simulated_end = (
        _minute_to_datetime(day_config.simulation_date, maintenance.simulated_end_min)
        if maintenance.simulated_end_min is not None
        else None
    )
    planned_end = planned_start_min + day_config.predicted_duration_min
    return {
        "plan_id": str(plan["plan_id"]),
        "maintenance_id": str(plan["maintenance_id"]),
        "section_id": day_config.maintenance_section_id,
        "simulation_date": day_config.simulation_date.isoformat(),
        "random_seed": day_config.random_seed,
        "kpis": {
            "total_delay_min": total_delay,
            "max_single_train_delay_min": max(delays, default=0),
            "average_delay_min": round(
                total_delay / len(train_results), 2
            ) if train_results else 0.0,
            "affected_trains_count": len(affected_train_ids),
            "affected_train_ids": affected_train_ids,
            "conflicts_detected": len(state["safety_conflicts"]),
            "maintenance_completed": maintenance_completed,
            "maintenance_completion_time": (
                simulated_end.isoformat() if simulated_end else None
            ),
            "trains_simulated": len(train_results),
            "maintenance_start_time": (
                simulated_start.isoformat() if simulated_start else None
            ),
            "maintenance_end_time": simulated_end.isoformat() if simulated_end else None,
            "predicted_maintenance_duration_min": day_config.predicted_duration_min,
            "simulated_maintenance_duration_min": simulated_duration,
        },
        "maintenance": {
            "maintenance_id": str(plan["maintenance_id"]),
            "plan_id": str(plan["plan_id"]),
            "section_id": day_config.maintenance_section_id,
            "planned_start": _minute_to_datetime(
                day_config.simulation_date, planned_start_min
            ).isoformat(),
            "planned_end": _minute_to_datetime(
                day_config.simulation_date, planned_end
            ).isoformat(),
            "simulated_start": simulated_start.isoformat() if simulated_start else None,
            "simulated_end": simulated_end.isoformat() if simulated_end else None,
            "predicted_duration_min": day_config.predicted_duration_min,
            "simulated_duration_min": simulated_duration,
            "duration_variation_min": variation,
            "completion_status": maintenance.completion_status,
        },
        "train_results": train_results,
        "safety_events": state["safety_conflicts"],
        "maintenance_events": state["maintenance_events"],
    }
