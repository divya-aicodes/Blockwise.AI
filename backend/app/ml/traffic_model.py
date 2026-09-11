"""Statistical traffic aggregation and constant-time lookups."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd

from backend.app.config import TRAFFIC_PROFILE_PATH, TRAINS_PATH
from backend.app.constants import SECTION_ID_SET, SECTION_IDS


PROFILE_COLUMNS = ["section_id", "hour_of_day", "weekday", "expected_trains_per_hour"]


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


def build_traffic_profile(
    trains_path: str | Path = TRAINS_PATH,
    output_path: str | Path = TRAFFIC_PROFILE_PATH,
) -> dict[str, int]:
    """Average daily section entries by hour and weekday, including zero-count hours."""
    trains = pd.read_csv(trains_path)
    required = {"section_id", "date", "actual_entry_time"}
    missing = required.difference(trains.columns)
    if missing:
        raise ValueError(f"Traffic data is missing columns: {sorted(missing)}")
    if trains.empty:
        raise ValueError("Traffic data must not be empty")

    trains["date"] = pd.to_datetime(trains["date"], errors="raise").dt.normalize()
    entry_timestamps = pd.to_datetime(
        trains["date"].dt.strftime("%Y-%m-%d")
        + " "
        + trains["actual_entry_time"].astype(str),
        errors="raise",
    )
    trains["hour_of_day"] = entry_timestamps.dt.hour.astype(int)
    counts = (
        trains.groupby(["section_id", "date", "hour_of_day"], observed=True)
        .size()
        .rename("train_count")
        .reset_index()
    )

    all_dates = pd.date_range(trains["date"].min(), trains["date"].max(), freq="D")
    complete_index = pd.MultiIndex.from_product(
        [SECTION_IDS, all_dates, range(24)],
        names=["section_id", "date", "hour_of_day"],
    )
    complete_counts = (
        counts.set_index(["section_id", "date", "hour_of_day"])
        .reindex(complete_index, fill_value=0)
        .reset_index()
    )
    complete_counts["weekday"] = complete_counts["date"].dt.weekday.astype(int)
    profile = (
        complete_counts.groupby(
            ["section_id", "hour_of_day", "weekday"], observed=True
        )["train_count"]
        .mean()
        .rename("expected_trains_per_hour")
        .reset_index()
        .sort_values(["section_id", "weekday", "hour_of_day"])
    )
    profile["expected_trains_per_hour"] = profile[
        "expected_trains_per_hour"
    ].round(6)
    profile = profile.loc[:, PROFILE_COLUMNS]
    _atomic_write_csv(profile, Path(output_path))
    _load_profile.cache_clear()
    return {"rows": int(len(profile)), "history_days": int(len(all_dates))}


@dataclass(frozen=True, slots=True)
class TrafficProfile:
    """Immutable O(1) lookup table for traffic estimates."""

    values: dict[tuple[str, int, int], float]

    @classmethod
    def from_csv(cls, path: str | Path = TRAFFIC_PROFILE_PATH) -> "TrafficProfile":
        frame = pd.read_csv(path)
        if frame.columns.tolist() != PROFILE_COLUMNS:
            raise ValueError("Traffic profile schema is invalid")
        values = {
            (str(row.section_id), int(row.hour_of_day), int(row.weekday)): float(
                row.expected_trains_per_hour
            )
            for row in frame.itertuples(index=False)
        }
        return cls(values=values)

    def get_expected_traffic(self, section: str, hour: int, weekday: int) -> float:
        if section not in SECTION_ID_SET:
            raise ValueError(f"Unknown section: {section}")
        if not 0 <= hour <= 23:
            raise ValueError("hour must be between 0 and 23")
        if not 0 <= weekday <= 6:
            raise ValueError("weekday must be between 0 (Monday) and 6 (Sunday)")
        return round(self.values.get((section, hour, weekday), 0.0), 6)


@lru_cache(maxsize=4)
def _load_profile(resolved_path: str, modified_ns: int) -> TrafficProfile:
    del modified_ns
    return TrafficProfile.from_csv(resolved_path)


def load_traffic_profile(path: str | Path = TRAFFIC_PROFILE_PATH) -> TrafficProfile:
    profile_path = Path(path).resolve()
    if not profile_path.is_file():
        raise FileNotFoundError(f"Traffic profile is missing: {profile_path}")
    return _load_profile(str(profile_path), profile_path.stat().st_mtime_ns)


def get_expected_traffic(
    section: str,
    hour: int,
    weekday: int,
    profile_path: str | Path = TRAFFIC_PROFILE_PATH,
) -> float:
    """Return the historical average without rescanning train history."""
    return load_traffic_profile(profile_path).get_expected_traffic(section, hour, weekday)

