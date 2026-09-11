from __future__ import annotations

from datetime import datetime
import csv
from zoneinfo import ZoneInfo

import pytest

from backend.app.simulation.feedback_store import FeedbackStore


def test_feedback_store_persists_and_aggregates_errors(tmp_path) -> None:
    path = tmp_path / "simulation_feedback.csv"
    store = FeedbackStore(path)
    timestamp = datetime(2026, 9, 1, 12, tzinfo=ZoneInfo("Asia/Kolkata"))
    store.record_feedback(
        timestamp=timestamp,
        maintenance_id="M001",
        plan_id="P001",
        section_id="SEC-NDLS-RE",
        predicted_duration_min=60,
        simulated_actual_duration_min=65,
        predicted_total_delay_min=20,
        simulated_actual_total_delay_min=30,
    )
    store.record_feedback(
        timestamp=timestamp,
        maintenance_id="M002",
        plan_id="P002",
        section_id="SEC-RE-AWR",
        predicted_duration_min=50,
        simulated_actual_duration_min=47,
        predicted_total_delay_min=40,
        simulated_actual_total_delay_min=32,
    )

    assert len(store) == 2
    with path.open("r", encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    assert float(rows[0]["duration_error_min"]) == 5.0
    assert float(rows[0]["delay_error_min"]) == 10.0
    assert float(rows[1]["duration_error_min"]) == -3.0
    assert float(rows[1]["delay_error_min"]) == -8.0
    assert store.get_feedback_stats() == {
        "total_simulations": 2,
        "duration_mae_min": 4.0,
        "delay_mae_min": 9.0,
        "mean_duration_error_min": 1.0,
        "mean_delay_error_min": 1.0,
        "scope": "ALL",
        "data_source": "DETERMINISTIC_SIMULATION",
    }
    assert FeedbackStore(path).get_feedback_stats(last_n=1)["delay_mae_min"] == 8.0


def test_feedback_store_rejects_invalid_values(tmp_path) -> None:
    store = FeedbackStore(tmp_path / "simulation_feedback.csv")
    with pytest.raises(ValueError, match="UTC offset"):
        store.record_feedback(
            timestamp=datetime(2026, 9, 1),
            maintenance_id="M001",
            plan_id="P001",
            section_id="SEC-NDLS-RE",
            predicted_duration_min=60,
            simulated_actual_duration_min=60,
            predicted_total_delay_min=0,
            simulated_actual_total_delay_min=0,
        )
