"""Read-only in-memory CSV repository with indexed train filtering."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import pandas as pd

from backend.app.data.generate_data import DATASET_COLUMNS


def _records(frame: pd.DataFrame) -> tuple[dict[str, Any], ...]:
    serialized = frame.to_json(orient="records", date_format="iso")
    return tuple(json.loads(serialized))


def _require_schema(frame: pd.DataFrame, filename: str) -> None:
    expected = DATASET_COLUMNS[filename]
    if frame.columns.tolist() != expected:
        raise ValueError(f"{filename} does not match the required schema")


@dataclass(frozen=True, slots=True)
class CsvRepository:
    assets: tuple[dict[str, Any], ...]
    trains: tuple[dict[str, Any], ...]
    crews: tuple[dict[str, Any], ...]
    maintenance_jobs: tuple[dict[str, Any], ...]
    weather: tuple[dict[str, Any], ...]
    timetable: tuple[dict[str, Any], ...]
    assets_by_id: dict[str, dict[str, Any]]
    train_indexes: dict[str, dict[str, frozenset[int]]]

    @classmethod
    def from_data_dir(cls, data_dir: str | Path) -> "CsvRepository":
        source = Path(data_dir)
        assets_frame = pd.read_csv(source / "assets.csv", keep_default_na=False)
        trains_frame = pd.read_csv(source / "trains.csv", keep_default_na=False)
        crews_frame = pd.read_csv(source / "crews.csv", keep_default_na=False)
        jobs_frame = pd.read_csv(
            source / "maintenance_jobs.csv", keep_default_na=False
        )
        weather_frame = pd.read_csv(source / "weather.csv", keep_default_na=False)
        timetable_frame = pd.read_csv(
            source / "timetable_base.csv", keep_default_na=False
        )
        _require_schema(assets_frame, "assets.csv")
        _require_schema(trains_frame, "trains.csv")
        _require_schema(crews_frame, "crews.csv")
        _require_schema(jobs_frame, "maintenance_jobs.csv")
        _require_schema(weather_frame, "weather.csv")
        _require_schema(timetable_frame, "timetable_base.csv")
        if assets_frame["asset_id"].duplicated().any():
            raise ValueError("assets.csv contains duplicate asset_id values")

        train_records = _records(trains_frame)
        mutable_indexes: dict[str, defaultdict[str, set[int]]] = {
            "section_id": defaultdict(set),
            "date": defaultdict(set),
            "train_id": defaultdict(set),
        }
        for position, record in enumerate(train_records):
            for field, index in mutable_indexes.items():
                index[str(record[field])].add(position)
        indexes = {
            field: {key: frozenset(positions) for key, positions in index.items()}
            for field, index in mutable_indexes.items()
        }
        asset_records = _records(assets_frame)
        return cls(
            assets=asset_records,
            trains=train_records,
            crews=_records(crews_frame),
            maintenance_jobs=_records(jobs_frame),
            weather=_records(weather_frame),
            timetable=_records(timetable_frame),
            assets_by_id={str(record["asset_id"]): record for record in asset_records},
            train_indexes=indexes,
        )

    def list_assets(self) -> list[dict[str, Any]]:
        return [dict(record) for record in self.assets]

    def get_asset(self, asset_id: str) -> dict[str, Any] | None:
        record = self.assets_by_id.get(asset_id)
        return dict(record) if record is not None else None

    def list_crews(self) -> list[dict[str, Any]]:
        return [dict(record) for record in self.crews]

    def historical_duration(self, job_type: str) -> float:
        matching = [
            float(record["historical_duration"])
            for record in self.maintenance_jobs
            if str(record["job_type"]) == job_type
        ]
        values = matching or [
            float(record["historical_duration"]) for record in self.maintenance_jobs
        ]
        if not values:
            raise ValueError("No historical maintenance durations are available")
        values.sort()
        middle = len(values) // 2
        if len(values) % 2:
            return values[middle]
        return (values[middle - 1] + values[middle]) / 2

    @property
    def movement_date_bounds(self) -> tuple[str, str]:
        date_index = self.train_indexes["date"]
        if not date_index:
            raise ValueError("No train movement dates are available")
        dates = sorted(date_index)
        return dates[0], dates[-1]

    def projected_timetable_movements(
        self,
        *,
        section: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Project recurring base timetable rows onto arbitrary future dates."""
        local_timezone = ZoneInfo("Asia/Kolkata")
        start = start_time.astimezone(local_timezone)
        end = end_time.astimezone(local_timezone)
        if end <= start:
            raise ValueError("end_time must be later than start_time")
        rows: list[dict[str, Any]] = []
        day = start.date()
        while datetime.combine(day, time.min, tzinfo=local_timezone) < end:
            weekday = day.strftime("%A").upper()
            for timetable_row in self.timetable:
                if str(timetable_row["section_id"]) != section:
                    continue
                running_days = str(timetable_row["running_days"]).split("|")
                if weekday not in running_days:
                    continue
                entry = datetime.combine(
                    day,
                    time.fromisoformat(str(timetable_row["scheduled_entry_time"])),
                    tzinfo=local_timezone,
                )
                exit_time = datetime.combine(
                    day,
                    time.fromisoformat(str(timetable_row["scheduled_exit_time"])),
                    tzinfo=local_timezone,
                )
                if exit_time <= entry:
                    exit_time += timedelta(days=1)
                if entry >= end or exit_time <= start:
                    continue
                rows.append(
                    {
                        "train_id": timetable_row["train_id"],
                        "train_name": timetable_row["train_name"],
                        "train_type": timetable_row["train_type"],
                        "section_id": section,
                        "date": day.isoformat(),
                        "scheduled_entry_time": timetable_row[
                            "scheduled_entry_time"
                        ],
                        "scheduled_exit_time": timetable_row["scheduled_exit_time"],
                        "priority": timetable_row["priority"],
                        "movement_source": "TIMETABLE_PROJECTION",
                    }
                )
            day += timedelta(days=1)
        return rows

    def relevant_train_movements(
        self,
        *,
        section: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Use actual history where available and timetable projections otherwise."""
        local_timezone = ZoneInfo("Asia/Kolkata")
        start = start_time.astimezone(local_timezone)
        end = end_time.astimezone(local_timezone)
        if end <= start:
            raise ValueError("end_time must be later than start_time")
        historical_dates = self.train_indexes["date"]
        records: list[dict[str, Any]] = []
        day = start.date()
        while datetime.combine(day, time.min, tzinfo=local_timezone) < end:
            day_text = day.isoformat()
            day_start = datetime.combine(day, time.min, tzinfo=local_timezone)
            day_end = day_start + timedelta(days=1)
            clipped_start = max(start, day_start)
            clipped_end = min(end, day_end)
            if day_text in historical_dates:
                records.extend(
                    self.query_trains(section=section, movement_date=day_text)
                )
            else:
                records.extend(
                    self.projected_timetable_movements(
                        section=section,
                        start_time=clipped_start,
                        end_time=clipped_end,
                    )
                )
            day += timedelta(days=1)
        return records

    def timetable_for_date(self, simulation_date: date) -> list[dict[str, Any]]:
        """Project every running service and corridor section onto one date."""
        weekday = simulation_date.strftime("%A").upper()
        records: list[dict[str, Any]] = []
        for row in self.timetable:
            if weekday not in str(row["running_days"]).split("|"):
                continue
            records.append(
                {
                    "train_id": row["train_id"],
                    "train_name": row["train_name"],
                    "train_type": row["train_type"],
                    "section_id": row["section_id"],
                    "date": simulation_date.isoformat(),
                    "scheduled_entry_time": row["scheduled_entry_time"],
                    "scheduled_exit_time": row["scheduled_exit_time"],
                    "priority": row["priority"],
                    "movement_source": "TIMETABLE_PROJECTION",
                }
            )
        return records

    def query_trains(
        self,
        *,
        section: str | None = None,
        movement_date: str | None = None,
        train_id: str | None = None,
    ) -> list[dict[str, Any]]:
        filters = {
            "section_id": section,
            "date": movement_date,
            "train_id": train_id,
        }
        postings: list[frozenset[int]] = []
        for field, value in filters.items():
            if value is None:
                continue
            positions = self.train_indexes[field].get(value)
            if positions is None:
                return []
            postings.append(positions)

        if not postings:
            positions_to_read: Iterable[int] = range(len(self.trains))
        else:
            postings.sort(key=len)
            matches = set(postings[0])
            for positions in postings[1:]:
                matches.intersection_update(positions)
                if not matches:
                    break
            positions_to_read = sorted(matches)
        return [dict(self.trains[position]) for position in positions_to_read]
