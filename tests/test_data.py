from __future__ import annotations

from pathlib import Path

import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

from backend.app.constants import SECTION_IDS
from backend.app.data.generate_data import generate_all_datasets, validate_datasets
from backend.app.repository import CsvRepository


def test_generated_data_is_deterministic(
    artifact_bundle: dict[str, object], tmp_path: Path
) -> None:
    second_dir = tmp_path / "second"
    generate_all_datasets(second_dir)
    data_dir = artifact_bundle["data_dir"]
    for filename in (
        "timetable_base.csv",
        "trains.csv",
        "assets.csv",
        "crews.csv",
        "maintenance_jobs.csv",
        "weather.csv",
    ):
        assert (data_dir / filename).read_bytes() == (second_dir / filename).read_bytes()


def test_generated_relationships_are_valid(artifact_bundle: dict[str, object]) -> None:
    counts = validate_datasets(artifact_bundle["data_dir"])
    assert counts["timetable_base.csv"] == 24 * 4
    assert counts["assets.csv"] == 24
    assert counts["crews.csv"] == 4
    assert counts["maintenance_jobs.csv"] == 36
    assert counts["weather.csv"] == 90


def test_train_movements_are_full_and_sequential(
    artifact_bundle: dict[str, object]
) -> None:
    trains = pd.read_csv(artifact_bundle["data_dir"] / "trains.csv")
    section_order = {section: index for index, section in enumerate(SECTION_IDS)}
    sample_groups = list(trains.groupby(["train_id", "date"], sort=False))[:50]
    assert sample_groups
    for _, group in sample_groups:
        ordered = group.sort_values(
            "section_id", key=lambda values: values.map(section_order)
        )
        assert ordered["section_id"].tolist() == list(SECTION_IDS)
        actual_entry = pd.to_datetime(
            ordered["date"] + " " + ordered["actual_entry_time"]
        ).reset_index(drop=True)
        actual_exit = pd.to_datetime(
            ordered["date"] + " " + ordered["actual_exit_time"]
        ).reset_index(drop=True)
        assert (actual_entry.iloc[1:].reset_index(drop=True) >= actual_exit.iloc[:-1].reset_index(drop=True)).all()


def test_risk_correlates_with_condition_and_age(artifact_bundle: dict[str, object]) -> None:
    assets = pd.read_csv(artifact_bundle["data_dir"] / "assets.csv")
    ordinal = assets["risk_level"].map(
        {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    )
    assert assets["condition_score"].corr(ordinal) < -0.70
    assert assets["age_years"].corr(ordinal) > 0.70


def test_future_planning_projects_timetable_instead_of_reusing_history(
    artifact_bundle: dict[str, object]
) -> None:
    repository = CsvRepository.from_data_dir(artifact_bundle["data_dir"])
    timezone = ZoneInfo("Asia/Kolkata")
    historical = repository.relevant_train_movements(
        section="SEC-NDLS-RE",
        start_time=datetime(2025, 1, 1, 8, 0, tzinfo=timezone),
        end_time=datetime(2025, 1, 1, 10, 0, tzinfo=timezone),
    )
    future = repository.relevant_train_movements(
        section="SEC-NDLS-RE",
        start_time=datetime(2026, 9, 1, 8, 0, tzinfo=timezone),
        end_time=datetime(2026, 9, 1, 10, 0, tzinfo=timezone),
    )
    assert historical and all("actual_entry_time" in row for row in historical)
    assert future and all(
        row["movement_source"] == "TIMETABLE_PROJECTION"
        and "actual_entry_time" not in row
        for row in future
    )
