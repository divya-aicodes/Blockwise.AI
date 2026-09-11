"""Build, validate, smoke-test, and optionally serve the complete backend."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any

import uvicorn
from fastapi.testclient import TestClient

from backend.app.config import (
    DATA_DIR,
    DURATION_MODEL_PATH,
    GRAPH_PATH,
    METRICS_PATH,
    RISK_MODEL_PATH,
    TRAFFIC_PROFILE_PATH,
)
from backend.app.data.generate_data import generate_all_datasets, validate_datasets
from backend.app.graph.railway_graph import RailwayGraph, build_and_save_graph
from backend.app.main import create_application
from backend.app.ml.duration_model import train_duration_model
from backend.app.ml.risk_model import train_risk_model
from backend.app.ml.traffic_model import build_traffic_profile


def _atomic_json_dump(payload: dict[str, Any], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
        delete=False,
    ) as temporary_file:
        json.dump(payload, temporary_file, indent=2, sort_keys=True)
        temporary_path = Path(temporary_file.name)
    os.replace(temporary_path, destination)


def _smoke_test() -> None:
    with TemporaryDirectory(prefix="maintenance-api-smoke-") as temporary_dir:
        maintenance_path = Path(temporary_dir) / "maintenance_requests.csv"
        application = create_application(maintenance_requests_path=maintenance_path)
        with TestClient(application) as client:
            health_response = client.get("/health")
            health_response.raise_for_status()
            health = health_response.json()
            if health["status"] != "ready":
                raise RuntimeError(f"Unexpected health response: {health}")

            assets_response = client.get("/assets")
            assets_response.raise_for_status()
            if len(assets_response.json()) < 15:
                raise RuntimeError("Asset endpoint returned too few records")

            risk_response = client.post(
                "/predict-risk",
                json={
                    "age_years": 18,
                    "condition_score": 55,
                    "previous_failures": 2,
                    "days_since_maintenance": 240,
                    "criticality": "HIGH",
                    "weather_condition": "LIGHT_RAIN",
                },
            )
            risk_response.raise_for_status()
            probability_sum = sum(risk_response.json()["probabilities"].values())
            if abs(probability_sum - 1.0) > 1e-6:
                raise RuntimeError("Risk probabilities are not normalized")

            duration_response = client.post(
                "/predict-duration",
                json={
                    "job_type": "CORRECTIVE",
                    "asset_condition": 55,
                    "crew_size": 5,
                    "weather_condition": "CLOUDY",
                    "historical_duration": 220,
                },
            )
            duration_response.raise_for_status()
            if duration_response.json()["predicted_duration_min"] <= 0:
                raise RuntimeError("Duration prediction is not positive")

            traffic_response = client.get(
                "/traffic/SEC-NDLS-RE", params={"hour": 8, "weekday": 0}
            )
            traffic_response.raise_for_status()

            maintenance_response = client.post(
                "/create-maintenance",
                json={
                    "asset_id": "AST-01-01",
                    "job_type": "INSPECTION",
                    "urgency": "HIGH",
                    "minimum_duration_min": 60,
                    "preferred_start_time": "2026-09-01T08:00:00+05:30",
                    "earliest_start_time": "2026-09-01T06:00:00+05:30",
                    "latest_end_time": "2026-09-02T06:00:00+05:30",
                },
            )
            maintenance_response.raise_for_status()
            maintenance_id = maintenance_response.json()["maintenance_id"]

            conflict_response = client.post(
                "/detect-conflicts",
                json={
                    "maintenance_id": maintenance_id,
                    "section_id": "SEC-NDLS-RE",
                    "start_time": "2026-09-01T08:00:00+05:30",
                    "end_time": "2026-09-01T10:00:00+05:30",
                },
            )
            conflict_response.raise_for_status()
            if conflict_response.json()["conflict_count"] < 1:
                raise RuntimeError("Conflict smoke test found no train overlap")

            alternatives_response = client.post(
                "/generate-alternatives",
                json={
                    "maintenance_id": maintenance_id,
                    "top_n": 3,
                    "max_train_delay_min": 360,
                },
            )
            alternatives_response.raise_for_status()
            alternatives = alternatives_response.json()["alternatives"]
            if not alternatives or any(
                plan["safety_conflicts"] for plan in alternatives
            ):
                raise RuntimeError("Optimizer did not return safe alternatives")

            simulation_response = client.post(
                "/simulate-plan",
                json={
                    "plan_id": alternatives[0]["plan_id"],
                    "simulation_date": "2026-09-01",
                    "random_seed": 42,
                },
            )
            simulation_response.raise_for_status()
            simulation = simulation_response.json()
            if simulation["kpis"]["conflicts_detected"] != 0:
                raise RuntimeError("Digital twin detected an unresolved safety conflict")
            if simulation["kpis"]["maintenance_completed"] is not True:
                raise RuntimeError("Digital twin did not complete maintenance")

            feedback_response = client.get("/feedback-stats")
            feedback_response.raise_for_status()
            if feedback_response.json()["total_simulations"] != 1:
                raise RuntimeError("Simulation feedback was not persisted")


def build_pipeline() -> dict[str, Any]:
    print("1/7 Generating deterministic synthetic datasets...")
    generate_all_datasets(DATA_DIR)
    dataset_counts = validate_datasets(DATA_DIR)

    print("2/7 Building and validating the corridor graph...")
    build_and_save_graph(GRAPH_PATH)
    loaded_graph = RailwayGraph.load_graph(GRAPH_PATH)
    expected_path = ["NDLS", "RE", "AWR", "BKI", "JP"]
    if loaded_graph.get_path_stations("NDLS", "JP") != expected_path:
        raise RuntimeError("Persisted graph failed its route check")

    print("3/7 Training and evaluating model pipelines...")
    risk_metrics = train_risk_model(DATA_DIR / "assets.csv", RISK_MODEL_PATH)
    duration_metrics = train_duration_model(
        DATA_DIR / "maintenance_jobs.csv", DURATION_MODEL_PATH
    )

    print("4/7 Building the statistical traffic profile...")
    traffic_metrics = build_traffic_profile(
        DATA_DIR / "trains.csv", TRAFFIC_PROFILE_PATH
    )
    report = {
        "data": dataset_counts,
        "risk_model": risk_metrics,
        "duration_model": duration_metrics,
        "traffic_profile": traffic_metrics,
    }
    _atomic_json_dump(report, METRICS_PATH)

    print("5/7 Validating Stage 1 API services...")
    print("6/7 Validating Stage 2 conflicts and CP-SAT alternatives...")
    print("7/7 Validating Stage 3 simulation and feedback...")
    _smoke_test()
    print(json.dumps(report, indent=2, sort_keys=True))
    print("Pipeline completed and API smoke tests passed.")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--no-serve",
        action="store_true",
        help="Build and test artifacts, then exit without starting Uvicorn.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    build_pipeline()
    if not arguments.no_serve:
        print(f"Serving API at http://{arguments.host}:{arguments.port}")
        uvicorn.run(
            "backend.app.main:app",
            host=arguments.host,
            port=arguments.port,
            reload=False,
        )
