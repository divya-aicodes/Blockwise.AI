from __future__ import annotations

import pytest

from backend.app.ml.duration_model import predict_maintenance_duration
from backend.app.ml.risk_model import predict_asset_risk
from backend.app.ml.traffic_model import TrafficProfile


def test_risk_model_returns_normalized_probabilities(
    artifact_bundle: dict[str, object]
) -> None:
    predicted, probabilities = predict_asset_risk(
        {
            "age_years": 25,
            "condition_score": 38,
            "previous_failures": 4,
            "days_since_maintenance": 420,
            "criticality": "CRITICAL",
            "weather_condition": "HEAVY_RAIN",
        },
        artifact_bundle["risk_model_path"],
    )
    assert predicted in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert sum(probabilities.values()) == pytest.approx(1.0, abs=1e-7)
    metrics = artifact_bundle["risk_metrics"]
    assert 0 <= metrics["accuracy"] <= 1
    assert metrics["test_records"] >= 4


def test_duration_model_returns_positive_numeric_prediction(
    artifact_bundle: dict[str, object]
) -> None:
    prediction = predict_maintenance_duration(
        {
            "job_type": "CORRECTIVE",
            "asset_condition": 48,
            "crew_size": 5,
            "weather_condition": "LIGHT_RAIN",
            "historical_duration": 240,
        },
        artifact_bundle["duration_model_path"],
    )
    assert 20 <= prediction <= 720
    assert artifact_bundle["duration_metrics"]["mae_minutes"] >= 0


def test_traffic_profile_has_complete_constant_time_grid(
    artifact_bundle: dict[str, object]
) -> None:
    profile = TrafficProfile.from_csv(artifact_bundle["traffic_profile_path"])
    assert len(profile.values) == 4 * 24 * 7
    assert profile.get_expected_traffic("SEC-NDLS-RE", 8, 0) >= 0
    with pytest.raises(ValueError, match="hour"):
        profile.get_expected_traffic("SEC-NDLS-RE", 24, 0)

