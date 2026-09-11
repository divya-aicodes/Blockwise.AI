"""Stage 5 acceptance path using the real Stage 1-4 application services."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_application


def test_complete_decision_support_flow(artifact_bundle: dict[str, object], tmp_path: Path) -> None:
    app = create_application(
        data_dir=artifact_bundle["data_dir"],
        graph_path=artifact_bundle["graph_path"],
        risk_model_path=artifact_bundle["risk_model_path"],
        duration_model_path=artifact_bundle["duration_model_path"],
        traffic_profile_path=artifact_bundle["traffic_profile_path"],
        maintenance_requests_path=tmp_path / "maintenance.csv",
    )
    with TestClient(app) as client:
        assets = client.get("/assets").json()
        asset = next(item for item in assets if item["risk_level"] in {"HIGH", "CRITICAL"})
        risk = client.post("/predict-risk", json={key: asset[key] for key in ("age_years", "condition_score", "previous_failures", "days_since_maintenance", "criticality", "weather_condition")})
        assert risk.status_code == 200

        maintenance = client.post("/create-maintenance", json={
            "asset_id": asset["asset_id"], "job_type": "INSPECTION", "urgency": "HIGH",
            "minimum_duration_min": 60, "earliest_start_time": "2026-09-01T06:00:00+05:30",
            "preferred_start_time": "2026-09-01T08:00:00+05:30", "latest_end_time": "2026-09-01T22:00:00+05:30",
        })
        assert maintenance.status_code == 201
        maintenance_id = maintenance.json()["maintenance_id"]

        conflicts = client.post("/detect-conflicts", json={
            "maintenance_id": maintenance_id, "section_id": asset["section_id"],
            "start_time": "2026-09-01T08:00:00+05:30", "end_time": "2026-09-01T09:00:00+05:30",
        })
        assert conflicts.status_code == 200

        alternatives = client.post("/generate-alternatives", json={"maintenance_id": maintenance_id, "top_n": 3, "max_train_delay_min": 360, "solver_timeout_seconds": 10})
        assert alternatives.status_code == 200
        plans = alternatives.json()["alternatives"]
        assert plans and all(plan["safety_conflicts"] == 0 and plan["reroute_available"] is False for plan in plans)
        plan = plans[0]

        simulated = client.post("/simulate-plan", json={"plan_id": plan["plan_id"], "simulation_date": "2026-09-01", "random_seed": 42})
        assert simulated.status_code == 200
        assert simulated.json()["kpis"]["conflicts_detected"] == 0
        assert simulated.json()["kpis"]["maintenance_completed"] is True
        feedback = client.get("/feedback-stats")
        assert feedback.status_code == 200 and feedback.json()["total_simulations"] == 1

        decision = client.post("/plan-decision", json={"plan_id": plan["plan_id"], "maintenance_id": maintenance_id, "decision": "APPROVED"})
        assert decision.status_code == 200
        assert decision.json()["decision"] == "APPROVED"
