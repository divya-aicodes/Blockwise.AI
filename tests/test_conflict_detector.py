from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from backend.app.constants import SECTION_IDS
from backend.app.simulation.conflict_detector import detect_conflicts


IST = ZoneInfo("Asia/Kolkata")


def movement(
    train_id: str, entry: str, exit_time: str, section: str = "SEC-NDLS-RE"
) -> dict[str, object]:
    return {
        "train_id": train_id,
        "section_id": section,
        "date": "2025-01-01",
        "actual_entry_time": entry,
        "actual_exit_time": exit_time,
        "scheduled_entry_time": entry,
        "scheduled_exit_time": exit_time,
        "priority": "HIGH",
    }


def job(section: str = "SEC-NDLS-RE") -> dict[str, object]:
    return {
        "maintenance_id": "M001",
        "section_id": section,
        "start_time": datetime(2025, 1, 1, 8, 0, tzinfo=IST),
        "end_time": datetime(2025, 1, 1, 10, 0, tzinfo=IST),
    }


def test_overlap_rules_and_multiple_structured_conflicts() -> None:
    trains = [
        movement("T-BEFORE", "07:30:00", "08:00:00"),
        movement("T-OVERLAP-1", "08:30:00", "09:15:00"),
        movement("T-OVERLAP-2", "09:45:00", "10:15:00"),
        movement("T-AFTER", "10:00:00", "10:30:00"),
        movement("T-OTHER-SECTION", "08:30:00", "09:00:00", "SEC-RE-AWR"),
    ]
    conflicts = detect_conflicts(job(), trains)
    assert [conflict.train_id for conflict in conflicts] == [
        "T-OVERLAP-1",
        "T-OVERLAP-2",
    ]
    assert conflicts[0].overlap_duration_min == 45
    payload = conflicts[0].to_dict()
    assert payload["section_id"] == "SEC-NDLS-RE"
    assert payload["conflict_type"] == "OCCUPANCY_CONFLICT"
    assert "maintenance_start" in payload and "train_entry_time" in payload


@pytest.mark.parametrize("section", SECTION_IDS)
def test_all_four_sections_detect_conflicts(section: str) -> None:
    conflicts = detect_conflicts(
        job(section), [movement("T001", "08:30:00", "09:00:00", section)]
    )
    assert len(conflicts) == 1
    assert conflicts[0].section_id == section


def test_conflict_detector_validates_timezone() -> None:
    invalid_job = job()
    invalid_job["start_time"] = datetime(2025, 1, 1, 8, 0)
    with pytest.raises(ValueError, match="UTC offset"):
        detect_conflicts(invalid_job, [])

