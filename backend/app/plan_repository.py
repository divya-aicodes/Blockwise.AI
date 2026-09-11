"""Atomic persistent storage for ranked Stage 2 plans."""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from typing import Any, Iterable, Mapping


PLAN_ID_PATTERN = re.compile(r"^P(\d{3,})$")


def _json_safe(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


class PlanRepository:
    """Store generated alternatives and preserve IDs for identical decisions."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._records: dict[str, dict[str, Any]] = {}
        self._decision_index: dict[str, str] = {}
        self._load_or_initialize()

    @staticmethod
    def _decision_key(plan: Mapping[str, Any]) -> str:
        window = plan["maintenance_window"]
        return "|".join(
            (
                str(plan["maintenance_id"]),
                str(window["start"]),
                str(window["end"]),
                str(plan["assigned_crew_id"]),
            )
        )

    def _load_or_initialize(self) -> None:
        with self._lock:
            if not self.path.exists():
                self._persist()
                return
            with self.path.open("r", encoding="utf-8") as source:
                payload = json.load(source)
            if not isinstance(payload, list):
                raise ValueError("optimization_plans.json must contain a list")
            for raw_record in payload:
                if not isinstance(raw_record, dict):
                    raise ValueError("Optimization plan record must be an object")
                record = _json_safe(raw_record)
                plan_id = str(record.get("plan_id", ""))
                if not PLAN_ID_PATTERN.fullmatch(plan_id):
                    raise ValueError(f"Invalid persisted plan_id: {plan_id}")
                self._records[plan_id] = record
                self._decision_index[self._decision_key(record)] = plan_id

    def _persist(self) -> None:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self.path.parent,
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            json.dump(
                list(self._records.values()),
                temporary_file,
                indent=2,
                sort_keys=True,
            )
            temporary_path = Path(temporary_file.name)
        os.replace(temporary_path, self.path)

    def _next_id(self) -> str:
        sequence = max(
            (
                int(match.group(1))
                for plan_id in self._records
                if (match := PLAN_ID_PATTERN.fullmatch(plan_id))
            ),
            default=0,
        )
        return f"P{sequence + 1:03d}"

    def save_many(self, plans: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
        saved: list[dict[str, Any]] = []
        with self._lock:
            for plan in plans:
                record = _json_safe(dict(plan))
                key = self._decision_key(record)
                existing_id = self._decision_index.get(key)
                plan_id = existing_id or self._next_id()
                record["plan_id"] = plan_id
                self._records[plan_id] = record
                self._decision_index[key] = plan_id
                saved.append(dict(record))
            if saved:
                self._persist()
        return saved

    def get(self, plan_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._records.get(plan_id)
            return dict(record) if record is not None else None

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)

