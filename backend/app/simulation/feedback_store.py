"""Persistent simulated prediction-versus-outcome feedback statistics."""

from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from typing import Any, Mapping


FEEDBACK_COLUMNS = [
    "timestamp",
    "maintenance_id",
    "plan_id",
    "section_id",
    "predicted_duration_min",
    "simulated_actual_duration_min",
    "duration_error_min",
    "absolute_duration_error_min",
    "predicted_total_delay_min",
    "simulated_actual_total_delay_min",
    "delay_error_min",
    "absolute_delay_error_min",
]


class FeedbackStore:
    """Thread-safe, atomically persisted Stage 3 simulation feedback."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._records: list[dict[str, Any]] = []
        self._load_or_initialize()

    def _load_or_initialize(self) -> None:
        with self._lock:
            if not self.path.exists():
                self._persist()
                return
            with self.path.open("r", encoding="utf-8", newline="") as source:
                reader = csv.DictReader(source)
                if reader.fieldnames != FEEDBACK_COLUMNS:
                    raise ValueError("simulation_feedback.csv schema is invalid")
                self._records = [self._normalize(row) for row in reader]

    @staticmethod
    def _normalize(record: Mapping[str, Any]) -> dict[str, Any]:
        normalized = dict(record)
        for column in FEEDBACK_COLUMNS[4:]:
            normalized[column] = float(normalized[column])
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
            writer = csv.DictWriter(temporary_file, fieldnames=FEEDBACK_COLUMNS)
            writer.writeheader()
            writer.writerows(self._records)
            temporary_path = Path(temporary_file.name)
        os.replace(temporary_path, self.path)

    def record_feedback(
        self,
        *,
        timestamp: datetime,
        maintenance_id: str,
        plan_id: str,
        section_id: str,
        predicted_duration_min: float,
        simulated_actual_duration_min: float,
        predicted_total_delay_min: float,
        simulated_actual_total_delay_min: float,
    ) -> dict[str, Any]:
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("timestamp must include a UTC offset")
        numeric_values = (
            predicted_duration_min,
            simulated_actual_duration_min,
            predicted_total_delay_min,
            simulated_actual_total_delay_min,
        )
        if any(value < 0 for value in numeric_values):
            raise ValueError("Feedback metrics cannot be negative")
        duration_error = simulated_actual_duration_min - predicted_duration_min
        delay_error = simulated_actual_total_delay_min - predicted_total_delay_min
        record = {
            "timestamp": timestamp.isoformat(),
            "maintenance_id": maintenance_id,
            "plan_id": plan_id,
            "section_id": section_id,
            "predicted_duration_min": float(predicted_duration_min),
            "simulated_actual_duration_min": float(simulated_actual_duration_min),
            "duration_error_min": float(duration_error),
            "absolute_duration_error_min": float(abs(duration_error)),
            "predicted_total_delay_min": float(predicted_total_delay_min),
            "simulated_actual_total_delay_min": float(
                simulated_actual_total_delay_min
            ),
            "delay_error_min": float(delay_error),
            "absolute_delay_error_min": float(abs(delay_error)),
        }
        with self._lock:
            self._records.append(record)
            try:
                self._persist()
            except OSError:
                self._records.pop()
                raise
        return dict(record)

    def get_feedback_stats(self, *, last_n: int | None = None) -> dict[str, Any]:
        if last_n is not None and last_n <= 0:
            raise ValueError("last_n must be positive")
        with self._lock:
            records = self._records[-last_n:] if last_n is not None else self._records
            selected = [dict(record) for record in records]
        count = len(selected)

        def mean(column: str) -> float:
            if not selected:
                return 0.0
            return round(sum(float(row[column]) for row in selected) / count, 3)

        return {
            "total_simulations": count,
            "duration_mae_min": mean("absolute_duration_error_min"),
            "delay_mae_min": mean("absolute_delay_error_min"),
            "mean_duration_error_min": mean("duration_error_min"),
            "mean_delay_error_min": mean("delay_error_min"),
            "scope": f"LAST_{last_n}" if last_n is not None else "ALL",
            "data_source": "DETERMINISTIC_SIMULATION",
        }

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)

