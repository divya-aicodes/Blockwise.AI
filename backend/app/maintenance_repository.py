"""Thread-safe, atomically persisted maintenance-requirement repository."""

from __future__ import annotations

import csv
import os
import re
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from typing import Any


MAINTENANCE_COLUMNS = [
    "maintenance_id",
    "version",
    "asset_id",
    "section_id",
    "required_skill",
    "job_type",
    "urgency",
    "risk_level",
    "condition_score",
    "minimum_duration_min",
    "preferred_start_time",
    "earliest_start_time",
    "latest_end_time",
    "status",
    "created_at",
]
MAINTENANCE_ID_PATTERN = re.compile(r"^M(\d{3,})$")


class MaintenanceRepository:
    """Small CSV system of record suitable for the Stage 2 prototype."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = RLock()
        self._records: dict[str, dict[str, Any]] = {}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._load_or_initialize()

    def _load_or_initialize(self) -> None:
        with self._lock:
            if not self.path.exists():
                self._persist()
                return
            with self.path.open("r", encoding="utf-8", newline="") as source:
                reader = csv.DictReader(source)
                if reader.fieldnames != MAINTENANCE_COLUMNS:
                    raise ValueError("maintenance_requests.csv schema is invalid")
                for row in reader:
                    maintenance_id = str(row["maintenance_id"])
                    if maintenance_id in self._records:
                        raise ValueError(
                            f"Duplicate maintenance_id in storage: {maintenance_id}"
                        )
                    self._records[maintenance_id] = self._normalize(row)

    @staticmethod
    def _normalize(record: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(record)
        normalized["version"] = int(normalized["version"])
        normalized["condition_score"] = float(normalized["condition_score"])
        normalized["minimum_duration_min"] = int(
            normalized["minimum_duration_min"]
        )
        return normalized

    def _persist(self) -> None:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=self.path.parent,
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            writer = csv.DictWriter(temporary_file, fieldnames=MAINTENANCE_COLUMNS)
            writer.writeheader()
            for record in self._records.values():
                writer.writerow({column: record[column] for column in MAINTENANCE_COLUMNS})
            temporary_path = Path(temporary_file.name)
        os.replace(temporary_path, self.path)

    def _next_id(self) -> str:
        sequence = 0
        for maintenance_id in self._records:
            match = MAINTENANCE_ID_PATTERN.fullmatch(maintenance_id)
            if match:
                sequence = max(sequence, int(match.group(1)))
        return f"M{sequence + 1:03d}"

    def create(
        self,
        *,
        asset_id: str,
        section_id: str,
        required_skill: str,
        job_type: str,
        urgency: str,
        risk_level: str,
        condition_score: float,
        minimum_duration_min: int,
        preferred_start_time: datetime,
        earliest_start_time: datetime,
        latest_end_time: datetime,
        created_at: datetime,
    ) -> dict[str, Any]:
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise ValueError("created_at must include a UTC offset")
        timestamps = {
            "preferred_start_time": preferred_start_time,
            "earliest_start_time": earliest_start_time,
            "latest_end_time": latest_end_time,
        }
        for field_name, value in timestamps.items():
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{field_name} must include a UTC offset")
        if minimum_duration_min <= 0:
            raise ValueError("minimum_duration_min must be positive")
        if not earliest_start_time <= preferred_start_time < latest_end_time:
            raise ValueError("Maintenance planning timestamps are inconsistent")
        horizon_min = (latest_end_time - earliest_start_time).total_seconds() / 60
        if horizon_min < minimum_duration_min:
            raise ValueError("Planning horizon is shorter than required duration")
        with self._lock:
            maintenance_id = self._next_id()
            record = {
                "maintenance_id": maintenance_id,
                "version": 1,
                "asset_id": asset_id,
                "section_id": section_id,
                "required_skill": required_skill,
                "job_type": job_type,
                "urgency": urgency,
                "risk_level": risk_level,
                "condition_score": float(condition_score),
                "minimum_duration_min": int(minimum_duration_min),
                "preferred_start_time": preferred_start_time.isoformat(),
                "earliest_start_time": earliest_start_time.isoformat(),
                "latest_end_time": latest_end_time.isoformat(),
                "status": "REQUIREMENT_CREATED",
                "created_at": created_at.isoformat(),
            }
            self._records[maintenance_id] = record
            try:
                self._persist()
            except OSError:
                self._records.pop(maintenance_id, None)
                raise
            return dict(record)

    def get(self, maintenance_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._records.get(maintenance_id)
            return dict(record) if record is not None else None

    def list_all(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(record) for record in self._records.values()]

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)
