"""Generate deterministic, logically related synthetic railway datasets."""

from __future__ import annotations

import math
import os
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Final

import numpy as np
import pandas as pd

from backend.app.config import DATA_DIR
from backend.app.constants import (
    CRITICALITIES,
    JOB_TYPES,
    RISK_LEVELS,
    SECTION_IDS,
    SECTION_ID_SET,
    SECTIONS,
    WEATHER_CONDITIONS,
)


SEED: Final[int] = 42
HISTORY_START: Final[date] = date(2025, 1, 1)
HISTORY_DAYS: Final[int] = 90
WEEKDAYS: Final[tuple[str, ...]] = (
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
    "SATURDAY",
    "SUNDAY",
)

DATASET_COLUMNS: Final[dict[str, list[str]]] = {
    "timetable_base.csv": [
        "train_id",
        "train_name",
        "train_type",
        "section_id",
        "scheduled_entry_time",
        "scheduled_exit_time",
        "priority",
        "running_days",
    ],
    "trains.csv": [
        "train_id",
        "train_name",
        "train_type",
        "section_id",
        "date",
        "scheduled_entry_time",
        "scheduled_exit_time",
        "actual_entry_time",
        "actual_exit_time",
        "delay_min",
        "priority",
    ],
    "assets.csv": [
        "asset_id",
        "asset_type",
        "section_id",
        "age_years",
        "condition_score",
        "previous_failures",
        "days_since_maintenance",
        "criticality",
        "weather_condition",
        "risk_level",
    ],
    "crews.csv": [
        "crew_id",
        "crew_name",
        "primary_skill",
        "secondary_skills",
        "shift_start",
        "shift_end",
        "crew_size",
        "availability",
    ],
    "maintenance_jobs.csv": [
        "job_id",
        "asset_id",
        "section_id",
        "job_type",
        "asset_condition",
        "crew_id",
        "crew_size",
        "weather_condition",
        "historical_duration",
        "duration_min",
    ],
    "weather.csv": [
        "date",
        "temperature_c",
        "weather_condition",
        "rainfall_mm",
        "visibility_km",
        "wind_speed_kmh",
    ],
}


def _atomic_write_csv(frame: pd.DataFrame, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
        delete=False,
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)
        frame.to_csv(temporary_file, index=False)
    os.replace(temporary_path, destination)


def _clock(value: datetime) -> str:
    return value.strftime("%H:%M:%S")


def _weather_rows(start: date, days: int, rng: np.random.Generator) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for offset in range(days):
        current_date = start + timedelta(days=offset)
        if offset < 35:
            probabilities = [0.40, 0.20, 0.08, 0.02, 0.30]
        else:
            probabilities = [0.58, 0.22, 0.13, 0.04, 0.03]
        condition = str(rng.choice(WEATHER_CONDITIONS, p=probabilities))

        seasonal_temperature = 16.0 + 0.16 * offset
        temperature = float(np.clip(rng.normal(seasonal_temperature, 2.7), 5.0, 38.0))
        if condition == "LIGHT_RAIN":
            rainfall = float(rng.uniform(1.0, 9.0))
            visibility = float(rng.uniform(4.0, 9.0))
        elif condition == "HEAVY_RAIN":
            rainfall = float(rng.uniform(15.0, 45.0))
            visibility = float(rng.uniform(1.0, 4.0))
        elif condition == "FOG":
            rainfall = 0.0
            visibility = float(rng.uniform(0.3, 2.5))
        elif condition == "CLOUDY":
            rainfall = float(rng.uniform(0.0, 0.8))
            visibility = float(rng.uniform(8.0, 15.0))
        else:
            rainfall = 0.0
            visibility = float(rng.uniform(15.0, 30.0))

        wind_base = 7.0 if condition in {"CLEAR", "FOG"} else 13.0
        wind_speed = float(np.clip(rng.normal(wind_base, 4.0), 0.0, 35.0))
        rows.append(
            {
                "date": current_date.isoformat(),
                "temperature_c": round(temperature, 1),
                "weather_condition": condition,
                "rainfall_mm": round(rainfall, 1),
                "visibility_km": round(visibility, 1),
                "wind_speed_kmh": round(wind_speed, 1),
            }
        )
    return rows


def _service_type(index: int) -> str:
    if index < 10:
        return "EXPRESS"
    if index < 18:
        return "PASSENGER"
    return "FREIGHT"


def _running_days(index: int, train_type: str) -> tuple[str, ...]:
    if train_type == "PASSENGER":
        return WEEKDAYS
    patterns = (
        WEEKDAYS,
        WEEKDAYS[:5],
        ("MONDAY", "WEDNESDAY", "FRIDAY", "SUNDAY"),
        ("TUESDAY", "THURSDAY", "SATURDAY"),
    )
    return patterns[index % len(patterns)]


def _scheduled_runtime_minutes(section: dict[str, object], train_type: str) -> int:
    speed_factor = {"EXPRESS": 0.82, "PASSENGER": 0.68, "FREIGHT": 0.50}[train_type]
    effective_speed = float(section["max_speed_kmh"]) * speed_factor
    return math.ceil(float(section["distance_km"]) / effective_speed * 60.0 + 4.0)


def _timetable_rows(service_count: int = 24) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    base_clock = datetime.combine(HISTORY_START, time(4, 30))
    for index in range(service_count):
        train_type = _service_type(index)
        priority = {"EXPRESS": "HIGH", "PASSENGER": "MEDIUM", "FREIGHT": "LOW"}[
            train_type
        ]
        train_id = f"TRN-{12001 + index}"
        train_name = f"Synthetic Corridor {train_type.title()} {index + 1:02d}"
        # Keep even the final slow freight service within the same calendar day.
        # This preserves unambiguous comparisons in the required date + clock schema.
        scheduled_entry = base_clock + timedelta(minutes=27 * index)
        running_days = _running_days(index, train_type)
        dwell_minutes = {"EXPRESS": 6, "PASSENGER": 9, "FREIGHT": 12}[train_type]
        for section in SECTIONS:
            runtime = _scheduled_runtime_minutes(section, train_type)
            scheduled_exit = scheduled_entry + timedelta(minutes=runtime)
            rows.append(
                {
                    "train_id": train_id,
                    "train_name": train_name,
                    "train_type": train_type,
                    "section_id": section["section_id"],
                    "scheduled_entry_time": _clock(scheduled_entry),
                    "scheduled_exit_time": _clock(scheduled_exit),
                    "priority": priority,
                    "running_days": "|".join(running_days),
                }
            )
            scheduled_entry = scheduled_exit + timedelta(minutes=dwell_minutes)
    return rows


def _movement_rows(
    timetable: pd.DataFrame,
    weather: pd.DataFrame,
    start: date,
    days: int,
    rng: np.random.Generator,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    weather_by_date = weather.set_index("date")["weather_condition"].to_dict()
    section_order = {section_id: index for index, section_id in enumerate(SECTION_IDS)}

    for current_date in (start + timedelta(days=offset) for offset in range(days)):
        weekday = WEEKDAYS[current_date.weekday()]
        daily_weather = str(weather_by_date[current_date.isoformat()])
        weather_delay = {
            "CLEAR": 0.6,
            "CLOUDY": 1.2,
            "LIGHT_RAIN": 3.2,
            "HEAVY_RAIN": 8.0,
            "FOG": 7.0,
        }[daily_weather]

        for train_id, schedule in timetable.groupby("train_id", sort=False):
            schedule = schedule.assign(
                _order=schedule["section_id"].map(section_order)
            ).sort_values("_order")
            service = schedule.iloc[0]
            if weekday not in str(service["running_days"]).split("|"):
                continue

            first_entry = datetime.combine(
                current_date, time.fromisoformat(str(service["scheduled_entry_time"]))
            )
            peak_factor = 2.5 if first_entry.hour in {7, 8, 9, 17, 18, 19} else 0.7
            type_factor = {"EXPRESS": 0.7, "PASSENGER": 1.5, "FREIGHT": 2.3}[
                str(service["train_type"])
            ]
            initial_delay = int(rng.poisson(weather_delay + peak_factor + type_factor))
            previous_actual_exit: datetime | None = None
            previous_scheduled_exit: datetime | None = None

            for _, scheduled_row in schedule.iterrows():
                scheduled_entry = datetime.combine(
                    current_date,
                    time.fromisoformat(str(scheduled_row["scheduled_entry_time"])),
                )
                scheduled_exit = datetime.combine(
                    current_date,
                    time.fromisoformat(str(scheduled_row["scheduled_exit_time"])),
                )
                if scheduled_exit < scheduled_entry:
                    scheduled_exit += timedelta(days=1)
                if previous_scheduled_exit is not None and scheduled_entry < previous_scheduled_exit:
                    scheduled_entry += timedelta(days=1)
                    scheduled_exit += timedelta(days=1)

                if previous_actual_exit is None:
                    actual_entry = scheduled_entry + timedelta(minutes=initial_delay)
                else:
                    scheduled_dwell = max(
                        0,
                        round((scheduled_entry - previous_scheduled_exit).total_seconds() / 60),
                    )
                    propagated_entry = previous_actual_exit + timedelta(minutes=scheduled_dwell)
                    holding_delay = int(rng.poisson(weather_delay * 0.18 + peak_factor * 0.15))
                    actual_entry = max(scheduled_entry, propagated_entry) + timedelta(
                        minutes=holding_delay
                    )

                scheduled_runtime = round(
                    (scheduled_exit - scheduled_entry).total_seconds() / 60
                )
                enroute_delay = int(
                    rng.poisson(weather_delay * 0.35 + type_factor * 0.25)
                )
                actual_exit = actual_entry + timedelta(
                    minutes=scheduled_runtime + enroute_delay
                )
                delay_min = max(
                    0, round((actual_exit - scheduled_exit).total_seconds() / 60)
                )
                rows.append(
                    {
                        "train_id": train_id,
                        "train_name": scheduled_row["train_name"],
                        "train_type": scheduled_row["train_type"],
                        "section_id": scheduled_row["section_id"],
                        "date": current_date.isoformat(),
                        "scheduled_entry_time": _clock(scheduled_entry),
                        "scheduled_exit_time": _clock(scheduled_exit),
                        "actual_entry_time": _clock(actual_entry),
                        "actual_exit_time": _clock(actual_exit),
                        "delay_min": delay_min,
                        "priority": scheduled_row["priority"],
                    }
                )
                previous_actual_exit = actual_exit
                previous_scheduled_exit = scheduled_exit
    return rows


def _risk_level(
    *,
    age_years: int,
    condition_score: int,
    previous_failures: int,
    days_since_maintenance: int,
    criticality: str,
    weather_condition: str,
) -> str:
    criticality_penalty = {"LOW": 0.0, "MEDIUM": 4.0, "HIGH": 8.0, "CRITICAL": 13.0}
    weather_penalty = {
        "CLEAR": 0.0,
        "CLOUDY": 1.0,
        "LIGHT_RAIN": 4.0,
        "HEAVY_RAIN": 8.0,
        "FOG": 5.0,
    }
    score = (
        (100 - condition_score) * 0.52
        + age_years * 0.75
        + previous_failures * 4.0
        + days_since_maintenance * 0.03
        + criticality_penalty[criticality]
        + weather_penalty[weather_condition]
    )
    if score < 25:
        return "LOW"
    if score < 45:
        return "MEDIUM"
    if score < 67:
        return "HIGH"
    return "CRITICAL"


def _asset_rows(weather: pd.DataFrame, rng: np.random.Generator) -> list[dict[str, object]]:
    asset_types = ("TRACK", "SIGNAL", "OHE", "POINT_MACHINE", "BRIDGE", "TELECOM")
    ages = (2, 6, 10, 15, 21, 28)
    conditions = (94, 84, 73, 62, 49, 34)
    failures = (0, 0, 1, 2, 3, 5)
    maintenance_days = (18, 65, 130, 215, 330, 480)
    criticalities = ("LOW", "MEDIUM", "MEDIUM", "HIGH", "HIGH", "CRITICAL")
    observed_weather = weather["weather_condition"].astype(str).tolist()
    rows: list[dict[str, object]] = []

    for section_index, section_id in enumerate(SECTION_IDS):
        for asset_index, asset_type in enumerate(asset_types):
            profile_index = (asset_index + section_index) % len(asset_types)
            age = ages[profile_index]
            condition = conditions[profile_index]
            previous_failures = failures[profile_index]
            days_since_maintenance = maintenance_days[profile_index]
            criticality = criticalities[(asset_index + 2 * section_index) % len(criticalities)]
            weather_condition = str(rng.choice(observed_weather))
            risk_level = _risk_level(
                age_years=age,
                condition_score=condition,
                previous_failures=previous_failures,
                days_since_maintenance=days_since_maintenance,
                criticality=criticality,
                weather_condition=weather_condition,
            )
            rows.append(
                {
                    "asset_id": f"AST-{section_index + 1:02d}-{asset_index + 1:02d}",
                    "asset_type": asset_type,
                    "section_id": section_id,
                    "age_years": age,
                    "condition_score": condition,
                    "previous_failures": previous_failures,
                    "days_since_maintenance": days_since_maintenance,
                    "criticality": criticality,
                    "weather_condition": weather_condition,
                    "risk_level": risk_level,
                }
            )
    return rows


def _crew_rows() -> list[dict[str, object]]:
    return [
        {
            "crew_id": "CRW-01",
            "crew_name": "Track and Structures Crew",
            "primary_skill": "TRACK",
            "secondary_skills": "BRIDGE|POINT_MACHINE",
            "shift_start": "06:00:00",
            "shift_end": "14:00:00",
            "crew_size": 6,
            "availability": "AVAILABLE",
        },
        {
            "crew_id": "CRW-02",
            "crew_name": "Signalling Crew",
            "primary_skill": "SIGNAL",
            "secondary_skills": "TELECOM|POINT_MACHINE",
            "shift_start": "08:00:00",
            "shift_end": "16:00:00",
            "crew_size": 4,
            "availability": "AVAILABLE",
        },
        {
            "crew_id": "CRW-03",
            "crew_name": "Traction Power Crew",
            "primary_skill": "OHE",
            "secondary_skills": "TELECOM|SIGNAL",
            "shift_start": "14:00:00",
            "shift_end": "22:00:00",
            "crew_size": 5,
            "availability": "AVAILABLE",
        },
        {
            "crew_id": "CRW-04",
            "crew_name": "Night Response Crew",
            "primary_skill": "POINT_MACHINE",
            "secondary_skills": "TRACK|SIGNAL|OHE",
            "shift_start": "22:00:00",
            "shift_end": "06:00:00",
            "crew_size": 3,
            "availability": "LIMITED",
        },
    ]


def _maintenance_rows(
    assets: pd.DataFrame,
    crews: pd.DataFrame,
    weather: pd.DataFrame,
    rng: np.random.Generator,
    job_count: int = 36,
) -> list[dict[str, object]]:
    base_duration = {
        "INSPECTION": 45,
        "PREVENTIVE": 100,
        "CORRECTIVE": 190,
        "EMERGENCY": 280,
    }
    weather_penalty = {
        "CLEAR": 0,
        "CLOUDY": 5,
        "LIGHT_RAIN": 22,
        "HEAVY_RAIN": 65,
        "FOG": 28,
    }
    crew_by_skill = {
        str(row["primary_skill"]): row for _, row in crews.iterrows()
    }
    fallback_crews = crews.to_dict(orient="records")
    observed_weather = weather["weather_condition"].astype(str).tolist()
    asset_records = assets.to_dict(orient="records")
    rows: list[dict[str, object]] = []

    for index in range(job_count):
        asset = asset_records[(index * 7) % len(asset_records)]
        job_type = JOB_TYPES[index % len(JOB_TYPES)]
        crew = crew_by_skill.get(str(asset["asset_type"]))
        if crew is None:
            crew = fallback_crews[index % len(fallback_crews)]
        crew_size = int(crew["crew_size"])
        weather_condition = str(rng.choice(observed_weather))
        condition_penalty = (100 - int(asset["condition_score"])) * 1.35
        historical_duration = int(
            round(
                base_duration[job_type]
                + condition_penalty
                + weather_penalty[weather_condition]
                - max(0, crew_size - 3) * 6
                + rng.normal(0, 9)
            )
        )
        historical_duration = max(20, historical_duration)
        duration = int(
            round(
                historical_duration * 0.62
                + base_duration[job_type] * 0.25
                + condition_penalty * 0.35
                + weather_penalty[weather_condition] * 0.35
                - max(0, crew_size - 3) * 4
                + rng.normal(0, 6)
            )
        )
        rows.append(
            {
                "job_id": f"JOB-{index + 1:04d}",
                "asset_id": asset["asset_id"],
                "section_id": asset["section_id"],
                "job_type": job_type,
                "asset_condition": asset["condition_score"],
                "crew_id": crew["crew_id"],
                "crew_size": crew_size,
                "weather_condition": weather_condition,
                "historical_duration": historical_duration,
                "duration_min": max(20, duration),
            }
        )
    return rows


def generate_all_datasets(
    output_dir: str | Path = DATA_DIR,
    *,
    start: date = HISTORY_START,
    days: int = HISTORY_DAYS,
) -> dict[str, Path]:
    """Generate all six CSV datasets in one deterministic pass."""
    if days <= 0:
        raise ValueError("days must be positive")
    random.seed(SEED)
    np.random.seed(SEED)
    rng = np.random.default_rng(SEED)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    weather = pd.DataFrame(_weather_rows(start, days, rng))
    timetable = pd.DataFrame(_timetable_rows())
    trains = pd.DataFrame(_movement_rows(timetable, weather, start, days, rng))
    assets = pd.DataFrame(_asset_rows(weather, rng))
    crews = pd.DataFrame(_crew_rows())
    jobs = pd.DataFrame(_maintenance_rows(assets, crews, weather, rng))

    frames = {
        "timetable_base.csv": timetable,
        "trains.csv": trains,
        "assets.csv": assets,
        "crews.csv": crews,
        "maintenance_jobs.csv": jobs,
        "weather.csv": weather,
    }
    paths: dict[str, Path] = {}
    for filename, frame in frames.items():
        expected_columns = DATASET_COLUMNS[filename]
        frame = frame.loc[:, expected_columns]
        path = destination / filename
        _atomic_write_csv(frame, path)
        paths[filename] = path

    validate_datasets(destination)
    return paths


def _timestamps(frame: pd.DataFrame, column: str) -> pd.Series:
    timestamps = pd.to_datetime(
        frame["date"].astype(str) + " " + frame[column].astype(str), errors="raise"
    )
    return timestamps


def validate_datasets(data_dir: str | Path = DATA_DIR) -> dict[str, int]:
    """Validate schemas, domains, referential integrity, and route sequencing."""
    source = Path(data_dir)
    frames: dict[str, pd.DataFrame] = {}
    for filename, columns in DATASET_COLUMNS.items():
        path = source / filename
        if not path.is_file():
            raise FileNotFoundError(f"Required dataset is missing: {path}")
        frame = pd.read_csv(path, keep_default_na=False)
        if frame.columns.tolist() != columns:
            raise ValueError(
                f"{filename} columns differ from schema: {frame.columns.tolist()}"
            )
        if frame.empty:
            raise ValueError(f"{filename} must not be empty")
        frames[filename] = frame

    timetable = frames["timetable_base.csv"]
    trains = frames["trains.csv"]
    assets = frames["assets.csv"]
    crews = frames["crews.csv"]
    jobs = frames["maintenance_jobs.csv"]
    weather = frames["weather.csv"]

    service_count = timetable["train_id"].nunique()
    if not 20 <= service_count <= 30:
        raise ValueError("Timetable must contain 20 to 30 services")
    for train_id, group in timetable.groupby("train_id", sort=False):
        if group["section_id"].tolist() != list(SECTION_IDS):
            raise ValueError(f"Timetable service {train_id} does not traverse the full corridor")

    if not set(trains["section_id"]).issubset(SECTION_ID_SET):
        raise ValueError("Train history contains an unknown section")
    section_order = {section_id: index for index, section_id in enumerate(SECTION_IDS)}
    trains = trains.assign(_order=trains["section_id"].map(section_order))
    scheduled_entries = _timestamps(trains, "scheduled_entry_time")
    scheduled_exits = _timestamps(trains, "scheduled_exit_time")
    actual_entries = _timestamps(trains, "actual_entry_time")
    actual_exits = _timestamps(trains, "actual_exit_time")
    if not ((actual_entries >= scheduled_entries) & (actual_exits >= scheduled_exits)).all():
        raise ValueError("Actual train times must not precede scheduled times")
    calculated_delay = ((actual_exits - scheduled_exits).dt.total_seconds() / 60).round().astype(int)
    if not calculated_delay.equals(trains["delay_min"].astype(int)):
        raise ValueError("delay_min is inconsistent with actual and scheduled exit times")

    for (train_id, movement_date), group in trains.groupby(["train_id", "date"], sort=False):
        group = group.sort_values("_order")
        if group["section_id"].tolist() != list(SECTION_IDS):
            raise ValueError(f"Movement {train_id}/{movement_date} is not a full ordered route")
        group_entries = _timestamps(group, "actual_entry_time").reset_index(drop=True)
        group_exits = _timestamps(group, "actual_exit_time").reset_index(drop=True)
        if not (group_entries.iloc[1:].reset_index(drop=True) >= group_exits.iloc[:-1].reset_index(drop=True)).all():
            raise ValueError(f"Movement {train_id}/{movement_date} violates section sequencing")

    if not 15 <= len(assets) <= 25:
        raise ValueError("Assets dataset must contain 15 to 25 records")
    if not assets["condition_score"].between(0, 100).all():
        raise ValueError("Asset condition_score must be between 0 and 100")
    if not set(assets["risk_level"]).issubset(RISK_LEVELS):
        raise ValueError("Assets dataset contains an unknown risk level")
    if assets["risk_level"].nunique() < 3:
        raise ValueError("Assets dataset must represent at least three risk levels")

    if not 3 <= len(crews) <= 5:
        raise ValueError("Crews dataset must contain 3 to 5 records")
    if not 20 <= len(jobs) <= 40:
        raise ValueError("Maintenance jobs dataset must contain 20 to 40 records")
    asset_sections = assets.set_index("asset_id")["section_id"].to_dict()
    if not set(jobs["asset_id"]).issubset(asset_sections):
        raise ValueError("Maintenance job references an unknown asset")
    if not set(jobs["crew_id"]).issubset(set(crews["crew_id"])):
        raise ValueError("Maintenance job references an unknown crew")
    if not all(
        asset_sections[asset_id] == section_id
        for asset_id, section_id in zip(jobs["asset_id"], jobs["section_id"], strict=True)
    ):
        raise ValueError("Maintenance job section does not match its asset")
    if not (jobs["duration_min"] > 0).all():
        raise ValueError("Maintenance duration must be positive")

    if weather["date"].nunique() != len(weather) or len(weather) != HISTORY_DAYS:
        raise ValueError(f"Weather dataset must contain {HISTORY_DAYS} unique days")
    if not set(weather["weather_condition"]).issubset(WEATHER_CONDITIONS):
        raise ValueError("Weather dataset contains an unknown condition")
    if (weather[["rainfall_mm", "visibility_km", "wind_speed_kmh"]].astype(float) < 0).any().any():
        raise ValueError("Weather measurements must be non-negative")

    return {filename: len(frame) for filename, frame in frames.items()}


if __name__ == "__main__":
    generated = generate_all_datasets()
    for name, path in generated.items():
        print(f"{name}: {path}")
