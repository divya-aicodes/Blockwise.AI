"""Half-open interval conflict detection for section occupancy."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

from backend.app.constants import SECTION_ID_SET


LOCAL_TIMEZONE = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True, slots=True)
class Conflict:
    maintenance_id: str
    train_id: str
    section_id: str
    train_entry_time: datetime
    train_exit_time: datetime
    maintenance_start: datetime
    maintenance_end: datetime
    overlap_start: datetime
    overlap_end: datetime
    overlap_duration_min: int
    train_priority: str
    conflict_type: str = "OCCUPANCY_CONFLICT"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for field in (
            "train_entry_time",
            "train_exit_time",
            "maintenance_start",
            "maintenance_end",
            "overlap_start",
            "overlap_end",
        ):
            payload[field] = payload[field].isoformat()
        return payload


def require_timezone(value: datetime, field_name: str) -> datetime:
    """Require an explicit offset and normalize it to the corridor timezone."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a UTC offset")
    return value.astimezone(LOCAL_TIMEZONE)


def _as_datetime(value: Any, field_name: str) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    return require_timezone(parsed, field_name)


def movement_interval(movement: Mapping[str, Any]) -> tuple[datetime, datetime]:
    """Convert actual history or a scheduled projection into an aware interval."""
    movement_date = date.fromisoformat(str(movement["date"]))
    has_actual = bool(movement.get("actual_entry_time")) and bool(
        movement.get("actual_exit_time")
    )
    entry_field = "actual_entry_time" if has_actual else "scheduled_entry_time"
    exit_field = "actual_exit_time" if has_actual else "scheduled_exit_time"
    entry = datetime.combine(
        movement_date,
        time.fromisoformat(str(movement[entry_field])),
        tzinfo=LOCAL_TIMEZONE,
    )
    exit_time = datetime.combine(
        movement_date,
        time.fromisoformat(str(movement[exit_field])),
        tzinfo=LOCAL_TIMEZONE,
    )
    if exit_time <= entry:
        exit_time += timedelta(days=1)
    return entry, exit_time


def _job_value(job: Mapping[str, Any] | object, name: str) -> Any:
    if isinstance(job, Mapping):
        return job[name]
    return getattr(job, name)


def _ceil_minutes(seconds: float) -> int:
    return int((max(0.0, seconds) + 59.999999) // 60)


def detect_conflicts(
    maintenance_job: Mapping[str, Any] | object,
    train_movements: Iterable[Mapping[str, Any]],
) -> list[Conflict]:
    """Return structured same-section conflicts for one maintenance window.

    Expected maintenance fields are ``maintenance_id``, ``section_id``,
    ``start_time``, and ``end_time``. Intervals are half-open, so touching
    boundaries are safe.
    """
    maintenance_id = str(_job_value(maintenance_job, "maintenance_id"))
    section_id = str(_job_value(maintenance_job, "section_id"))
    if section_id not in SECTION_ID_SET:
        raise ValueError(f"Unknown section: {section_id}")
    start = _as_datetime(_job_value(maintenance_job, "start_time"), "start_time")
    end = _as_datetime(_job_value(maintenance_job, "end_time"), "end_time")
    if end <= start:
        raise ValueError("end_time must be later than start_time")

    conflicts: list[Conflict] = []
    for movement in train_movements:
        if str(movement.get("section_id")) != section_id:
            continue
        train_entry, train_exit = movement_interval(movement)
        if not (train_entry < end and train_exit > start):
            continue
        overlap_start = max(train_entry, start)
        overlap_end = min(train_exit, end)
        conflicts.append(
            Conflict(
                maintenance_id=maintenance_id,
                train_id=str(movement["train_id"]),
                section_id=section_id,
                train_entry_time=train_entry,
                train_exit_time=train_exit,
                maintenance_start=start,
                maintenance_end=end,
                overlap_start=overlap_start,
                overlap_end=overlap_end,
                overlap_duration_min=max(
                    1, _ceil_minutes((overlap_end - overlap_start).total_seconds())
                ),
                train_priority=str(movement.get("priority", "MEDIUM")),
            )
        )
    conflicts.sort(
        key=lambda conflict: (conflict.overlap_start, conflict.train_id)
    )
    return conflicts

