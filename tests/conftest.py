from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.data.generate_data import generate_all_datasets
from backend.app.graph.railway_graph import build_and_save_graph
from backend.app.ml.duration_model import train_duration_model
from backend.app.ml.risk_model import train_risk_model
from backend.app.ml.traffic_model import build_traffic_profile


@pytest.fixture(scope="session")
def artifact_bundle(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    root = tmp_path_factory.mktemp("artifacts")
    data_dir = root / "data"
    model_dir = root / "models"
    graph_path = root / "graph.json"
    risk_model_path = model_dir / "risk_model.joblib"
    duration_model_path = model_dir / "duration_model.joblib"
    traffic_profile_path = data_dir / "traffic_profile.csv"

    generate_all_datasets(data_dir)
    build_and_save_graph(graph_path)
    risk_metrics = train_risk_model(data_dir / "assets.csv", risk_model_path)
    duration_metrics = train_duration_model(
        data_dir / "maintenance_jobs.csv", duration_model_path
    )
    traffic_metrics = build_traffic_profile(
        data_dir / "trains.csv", traffic_profile_path
    )
    return {
        "root": root,
        "data_dir": data_dir,
        "graph_path": graph_path,
        "risk_model_path": risk_model_path,
        "duration_model_path": duration_model_path,
        "traffic_profile_path": traffic_profile_path,
        "risk_metrics": risk_metrics,
        "duration_metrics": duration_metrics,
        "traffic_metrics": traffic_metrics,
    }

