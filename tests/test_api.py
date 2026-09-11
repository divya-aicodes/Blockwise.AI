from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_application
from backend.app.constants import SECTION_IDS


@pytest.fixture()
def client(artifact_bundle: dict[str, object], tmp_path: Path) -> TestClient:
    application = create_application(
        data_dir=artifact_bundle["data_dir"],
        graph_path=artifact_bundle["graph_path"],
        risk_model_path=artifact_bundle["risk_model_path"],
        duration_model_path=artifact_bundle["duration_model_path"],
        traffic_profile_path=artifact_bundle["traffic_profile_path"],
        maintenance_requests_path=tmp_path / "maintenance_requests.csv",
    )
    with TestClient(application) as test_client:
        yield test_client


def _maintenance_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "asset_id": "AST-01-01",
        "job_type": "INSPECTION",
        "urgency": "HIGH",
        "minimum_duration_min": 60,
        "preferred_start_time": "2026-09-01T08:00:00+05:30",
        "earliest_start_time": "2026-09-01T06:00:00+05:30",
        "latest_end_time": "2026-09-02T06:00:00+05:30",
    }
    payload.update(overrides)
    return payload


def test_stage_one_endpoints_remain_compatible(client: TestClient) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ready"
    assert health.json()["maintenance_repository_loaded"] is True

    assets = client.get("/assets")
    assert assets.status_code == 200
    assert len(assets.json()) == 24
    trains = client.get(
        "/trains", params={"section": "SEC-RE-AWR", "date": "2025-01-01"}
    )
    assert trains.status_code == 200
    assert trains.json()
    assert all(record["section_id"] == "SEC-RE-AWR" for record in trains.json())

    risk_payload = {
        "age_years": 12,
        "condition_score": 65,
        "previous_failures": 1,
        "days_since_maintenance": 180,
        "criticality": "HIGH",
        "weather_condition": "FOG",
    }
    risk = client.post("/predict-risk", json=risk_payload)
    assert risk.status_code == 200
    assert sum(risk.json()["probabilities"].values()) == pytest.approx(1.0)
    assert client.post(
        "/predict-risk", json={**risk_payload, "condition_score": 101}
    ).status_code == 422

    traffic = client.get(
        "/traffic/SEC-AWR-BKI", params={"hour": 8, "weekday": 2}
    )
    assert traffic.status_code == 200
    assert client.get(
        "/traffic/SEC-AWR-BKI", params={"hour": 24, "weekday": 2}
    ).status_code == 422


def test_all_three_stage_two_endpoints_with_future_timetable_projection(
    client: TestClient,
) -> None:
    created = client.post("/create-maintenance", json=_maintenance_payload())
    assert created.status_code == 201, created.text
    maintenance = created.json()
    assert maintenance["maintenance_id"] == "M001"
    assert maintenance["section_id"] == "SEC-NDLS-RE"
    assert maintenance["minimum_duration_min"] == 60

    conflicts = client.post(
        "/detect-conflicts",
        json={
            "maintenance_id": "M001",
            "section_id": "SEC-NDLS-RE",
            "start_time": "2026-09-01T08:00:00+05:30",
            "end_time": "2026-09-01T10:00:00+05:30",
        },
    )
    assert conflicts.status_code == 200, conflicts.text
    conflict_body = conflicts.json()
    assert conflict_body["has_conflicts"] is True
    assert conflict_body["conflict_count"] == len(conflict_body["conflicts"])
    assert conflict_body["conflict_count"] > 0
    assert all(
        conflict["section_id"] == "SEC-NDLS-RE"
        and conflict["conflict_type"] == "OCCUPANCY_CONFLICT"
        for conflict in conflict_body["conflicts"]
    )

    alternatives = client.post(
        "/generate-alternatives",
        json={
            "maintenance_id": "M001",
            "top_n": 5,
            "max_train_delay_min": 360,
        },
    )
    assert alternatives.status_code == 200, alternatives.text
    body = alternatives.json()
    assert body["status"] == "FEASIBLE_PLANS"
    assert 3 <= body["alternatives_generated"] <= 5
    plans = body["alternatives"]
    assert [plan["rank"] for plan in plans] == list(range(1, len(plans) + 1))
    assert [plan["overall_score"] for plan in plans] == sorted(
        plan["overall_score"] for plan in plans
    )
    assert all(plan["safety_conflicts"] == 0 for plan in plans)
    assert all(plan["reroute_available"] is False for plan in plans)
    assert all(
        plan["maintenance_window"]["start"]
        < plan["maintenance_window"]["end"]
        for plan in plans
    )
    assert len(
        {
            (plan["maintenance_window"]["start"], plan["assigned_crew_id"])
            for plan in plans
        }
    ) == len(plans)


def test_stage_three_simulates_persisted_plan_and_records_feedback(
    client: TestClient,
) -> None:
    created = client.post("/create-maintenance", json=_maintenance_payload())
    assert created.status_code == 201, created.text
    generated = client.post(
        "/generate-alternatives",
        json={
            "maintenance_id": "M001",
            "top_n": 3,
            "max_train_delay_min": 360,
            "solver_timeout_seconds": 10,
        },
    )
    assert generated.status_code == 200, generated.text
    plans = generated.json()["alternatives"]
    assert plans
    plan_id = plans[0]["plan_id"]
    assert plan_id.startswith("P")

    simulated = client.post(
        "/simulate-plan",
        json={
            "plan_id": plan_id,
            "simulation_date": "2026-09-01",
            "random_seed": 42,
        },
    )
    assert simulated.status_code == 200, simulated.text
    body = simulated.json()
    assert body["plan_id"] == plan_id
    assert body["kpis"]["conflicts_detected"] == 0
    assert body["kpis"]["maintenance_completed"] is True
    assert body["kpis"]["trains_simulated"] > 0
    assert all(
        result["section_events"]
        for result in body["train_results"]
    )

    feedback = client.get("/feedback-stats")
    assert feedback.status_code == 200
    assert feedback.json()["total_simulations"] == 1
    assert feedback.json()["data_source"] == "DETERMINISTIC_SIMULATION"
    health = client.get("/health").json()
    assert health["plans_stored"] == len(plans)
    assert health["feedback_rows"] == 1


def test_stage_three_rejects_unknown_plan_and_invalid_feedback_limit(
    client: TestClient,
) -> None:
    assert client.post(
        "/simulate-plan",
        json={"plan_id": "P999", "simulation_date": "2026-09-01"},
    ).status_code == 404
    assert client.get("/feedback-stats", params={"last_n": 0}).status_code == 422


def test_stage_two_validation_and_no_feasible_plan_response(
    client: TestClient,
) -> None:
    assert client.post(
        "/create-maintenance",
        json=_maintenance_payload(asset_id="AST-99-99"),
    ).status_code == 404
    assert client.post(
        "/create-maintenance",
        json=_maintenance_payload(preferred_start_time="2026-09-01T08:00:00"),
    ).status_code == 422

    created = client.post(
        "/create-maintenance",
        json=_maintenance_payload(
            minimum_duration_min=720,
            preferred_start_time="2026-09-01T08:00:00+05:30",
            earliest_start_time="2026-09-01T06:00:00+05:30",
            latest_end_time="2026-09-01T18:00:00+05:30",
        ),
    )
    assert created.status_code == 201
    mismatch = client.post(
        "/detect-conflicts",
        json={
            "maintenance_id": "M001",
            "section_id": "SEC-RE-AWR",
            "start_time": "2026-09-01T08:00:00+05:30",
            "end_time": "2026-09-01T09:00:00+05:30",
        },
    )
    assert mismatch.status_code == 422

    no_plan = client.post(
        "/generate-alternatives", json={"maintenance_id": "M001", "top_n": 3}
    )
    assert no_plan.status_code == 200
    assert no_plan.json() == {
        "maintenance_id": "M001",
        "alternatives_generated": 0,
        "alternatives": [],
        "status": "NO_FEASIBLE_PLAN",
    }


@pytest.mark.parametrize(
    ("asset_id", "expected_section"),
    [
        ("AST-01-01", SECTION_IDS[0]),
        ("AST-02-01", SECTION_IDS[1]),
        ("AST-03-01", SECTION_IDS[2]),
        ("AST-04-01", SECTION_IDS[3]),
    ],
)
def test_optimizer_generates_safe_plans_for_all_four_sections(
    client: TestClient, asset_id: str, expected_section: str
) -> None:
    created = client.post(
        "/create-maintenance", json=_maintenance_payload(asset_id=asset_id)
    )
    assert created.status_code == 201, created.text
    assert created.json()["section_id"] == expected_section
    response = client.post(
        "/generate-alternatives",
        json={"maintenance_id": "M001", "top_n": 3, "max_train_delay_min": 360},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["alternatives_generated"] == 3
    assert all(plan["safety_conflicts"] == 0 for plan in body["alternatives"])
