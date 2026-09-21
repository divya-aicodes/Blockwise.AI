"""Focused tests for execution readiness, routing and simulation invariants."""
from __future__ import annotations

from datetime import date, datetime, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.auth.service import admin_or_anonymous, current_crew
from backend.app.db.base import get_db
from backend.app.db.base import Base
from backend.app.db.models import Crew, Notification, WorkOrder
from backend.app.graph.railway_graph import RailwayGraph
from backend.app.main import create_application
from backend.app.repository import CsvRepository
from backend.app.simulation.scenario_runner import run_scenario
from backend.app.work_orders.readiness import validate_execution_readiness
from backend.app.work_orders.service import assign, create_from_plan


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session


def _crew(
    employee_id: str,
    *,
    role: str = "GANG",
    skill: str = "TRACK",
    department_id: str | None = None,
    provider_type: str | None = None,
    provider_id: str | None = None,
) -> Crew:
    return Crew(
        employee_id=employee_id,
        email=f"{employee_id.lower()}@example.test",
        password_hash="not-used-in-unit-tests",
        full_name=employee_id,
        role=role,
        primary_skill=skill,
        department_id=department_id,
        provider_type=provider_type,
        provider_id=provider_id,
        shift_start=time(6, 0),
        shift_end=time(18, 0),
        availability="AVAILABLE",
        is_active=True,
    )


def _plan(plan_id: str = "P900", maintenance_id: str = "M900") -> dict:
    return {
        "plan_id": plan_id,
        "maintenance_id": maintenance_id,
        "maintenance_window": {
            "start": "2026-09-01T08:00:00+05:30",
            "end": "2026-09-01T09:00:00+05:30",
        },
        "affected_trains": [],
        "total_train_delay_min": 0,
        "safety_conflicts": 0,
    }


def _requirement(maintenance_id: str = "M900") -> dict:
    return {
        "maintenance_id": maintenance_id,
        "asset_id": "AST-01-01",
        "asset_type": "TRACK",
        "section_id": "SEC-NDLS-RE",
        "required_skill": "TRACK",
        "urgency": "HIGH",
        "minimum_duration_min": 60,
    }


def test_departmental_assignment_is_ready_and_notifications_are_targeted(db: Session) -> None:
    supervisor = _crew("EMP-SUP", role="ADMIN", department_id="ENG")
    worker = _crew("EMP-WORKER", department_id="ENG")
    unrelated = _crew("EMP-OTHER", department_id="SIGNAL")
    db.add_all([supervisor, worker, unrelated])
    db.commit()

    plan = _plan()
    order = create_from_plan(
        db,
        plan=plan,
        requirement=_requirement(),
        actor=supervisor,
        execution={"execution_mode": "DEPARTMENTAL", "department_id": "ENG"},
    )
    assigned = assign(
        db,
        order.id,
        worker.employee_id,
        supervisor,
        plan=plan,
        approved=True,
    )
    readiness = validate_execution_readiness(db, assigned, plan=plan, approved=True)

    assert assigned.execution_mode == "DEPARTMENTAL"
    assert readiness["executable"] is True
    recipients = set(db.scalars(select(Notification.user_id)).all())
    assert recipients == {worker.id, supervisor.id}
    assert unrelated.id not in recipients


def test_amc_assignment_rejects_unrelated_team_and_accepts_matching_team(db: Session) -> None:
    supervisor = _crew("EMP-ADMIN", role="ADMIN")
    internal_worker = _crew("EMP-INTERNAL")
    amc_worker = _crew(
        "EMP-AMC",
        provider_type="AMC_CAMC",
        provider_id="AMC-7",
    )
    amc_manager = _crew(
        "EMP-AMC-MGR",
        role="SUPERVISOR",
        provider_type="AMC_CAMC",
        provider_id="AMC-7",
    )
    db.add_all([supervisor, internal_worker, amc_worker, amc_manager])
    db.commit()

    plan = _plan("P901", "M901")
    order = create_from_plan(
        db,
        plan=plan,
        requirement=_requirement("M901"),
        actor=supervisor,
        execution={"execution_mode": "AMC_CAMC", "amc_id": "AMC-7"},
    )
    with pytest.raises(ValueError, match="not affiliated"):
        assign(
            db,
            order.id,
            internal_worker.employee_id,
            supervisor,
            plan=plan,
            approved=True,
        )
    db.rollback()

    assigned = assign(
        db,
        order.id,
        amc_worker.employee_id,
        supervisor,
        plan=plan,
        approved=True,
    )
    readiness = validate_execution_readiness(db, assigned, plan=plan, approved=True)
    recipients = set(db.scalars(select(Notification.user_id)).all())

    assert readiness["executable"] is True
    assert amc_worker.id in recipients
    assert amc_manager.id in recipients
    assert internal_worker.id not in recipients


def test_execution_mode_metadata_alone_does_not_change_simulation(
    artifact_bundle: dict[str, object],
) -> None:
    repository = CsvRepository.from_data_dir(artifact_bundle["data_dir"])
    graph = RailwayGraph.load_graph(artifact_bundle["graph_path"])
    requirement = _requirement()
    plan = _plan()

    departmental = run_scenario(
        {**plan, "execution_mode": "DEPARTMENTAL"},
        date(2026, 9, 1),
        maintenance_requirement=requirement,
        repository=repository,
        railway_graph=graph,
        random_seed=42,
    )
    amc = run_scenario(
        {**plan, "execution_mode": "AMC_CAMC"},
        date(2026, 9, 1),
        maintenance_requirement=requirement,
        repository=repository,
        railway_graph=graph,
        random_seed=42,
    )

    assert departmental["kpis"] == amc["kpis"]
    assert departmental["maintenance"] == amc["maintenance"]


def test_recommendation_and_digital_twin_expose_execution_context(
    artifact_bundle: dict[str, object], tmp_path, monkeypatch,
) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    admin = _crew("EMP-API-ADMIN", role="ADMIN", department_id="ENG")
    worker = _crew("EMP-API-WORKER", department_id="ENG")
    admin.shift_start = worker.shift_start = time(0, 0)
    admin.shift_end = worker.shift_end = time(23, 59)
    session.add_all([admin, worker])
    session.commit()

    app = create_application(
        data_dir=artifact_bundle["data_dir"],
        graph_path=artifact_bundle["graph_path"],
        risk_model_path=artifact_bundle["risk_model_path"],
        duration_model_path=artifact_bundle["duration_model_path"],
        traffic_profile_path=artifact_bundle["traffic_profile_path"],
        maintenance_requests_path=tmp_path / "maintenance.csv",
    )

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[current_crew] = lambda: admin
    app.dependency_overrides[admin_or_anonymous] = lambda: admin
    monkeypatch.setattr(
        "backend.app.db.base.SessionLocal",
        lambda: Session(engine, expire_on_commit=False),
    )
    try:
        with TestClient(app) as client:
            maintenance_response = client.post(
                "/create-maintenance",
                json={
                    "asset_id": "AST-02-01",
                    "job_type": "INSPECTION",
                    "urgency": "HIGH",
                    "minimum_duration_min": 60,
                    "earliest_start_time": "2026-09-09T06:00:00+05:30",
                    "preferred_start_time": "2026-09-09T08:00:00+05:30",
                    "latest_end_time": "2026-09-09T22:00:00+05:30",
                    "execution_mode": "DEPARTMENTAL",
                    "department_id": "ENG",
                },
            )
            assert maintenance_response.status_code == 201
            requirement = maintenance_response.json()
            plans_response = client.post(
                "/generate-alternatives",
                json={
                    "maintenance_id": requirement["maintenance_id"],
                    "top_n": 1,
                    "solver_timeout_seconds": 10,
                    "max_train_delay_min": 360,
                },
            )
            assert plans_response.status_code == 200
            plan = plans_response.json()["alternatives"][0]
            worker.primary_skill = requirement["required_skill"]
            session.commit()
            approval = client.post(
                "/plan-decision",
                json={
                    "plan_id": plan["plan_id"],
                    "maintenance_id": requirement["maintenance_id"],
                    "decision": "APPROVED",
                    "execution_mode": "DEPARTMENTAL",
                    "department_id": "ENG",
                },
            )
            assert approval.status_code == 200, approval.text
            assert approval.json()["work_order"]["execution_mode"] == "DEPARTMENTAL"
            order = session.scalar(
                select(WorkOrder).where(WorkOrder.plan_id == plan["plan_id"])
            )
            assert order is not None
            assign(
                session,
                order.id,
                worker.employee_id,
                admin,
                plan=plan,
                approved=True,
            )

            recommendation = client.post(
                "/planning/recommendation",
                json={
                    "maintenance_id": requirement["maintenance_id"],
                    "plan_id": plan["plan_id"],
                    "execution_mode": "DEPARTMENTAL",
                    "department_id": "ENG",
                },
            )
            assert recommendation.status_code == 200, recommendation.text
            assert recommendation.json()["executable"] is True

            simulated = client.post(
                "/simulate-plan",
                json={
                    "plan_id": plan["plan_id"],
                    "simulation_date": "2026-09-09",
                    "random_seed": 42,
                },
            )
            assert simulated.status_code == 200, simulated.text
            context = simulated.json()["execution_context"]
            assert context["execution_mode"] == "DEPARTMENTAL"
            assert context["assigned_crew_id"] == worker.id
            assert context["executable"] is True
            assert all(
                event["execution_mode"] == "DEPARTMENTAL"
                for event in simulated.json()["maintenance_events"]
            )
    finally:
        session.close()
