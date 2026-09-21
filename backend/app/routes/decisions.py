"""Human decisions with immutable planning and simulation evidence."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field
from sqlalchemy import select

from backend.app.schemas import ExecutionMode, StrictModel
from backend.app.simulation.conflict_detector import LOCAL_TIMEZONE
from backend.app.simulation.scenario_runner import run_scenario
from backend.app.auth.service import admin_or_anonymous
from backend.app.db.models import Crew, WorkOrder


class DecisionRequest(StrictModel):
    plan_id: str = Field(pattern=r"^P\d{3,}$")
    maintenance_id: str = Field(pattern=r"^M\d{3,}$")
    decision: Literal["APPROVED", "MODIFY", "REJECTED"]
    execution_mode: ExecutionMode = ExecutionMode.departmental
    department_id: str | None = Field(default=None, max_length=64)
    contract_id: str | None = Field(default=None, max_length=64)
    amc_id: str | None = Field(default=None, max_length=64)
    oem_service_id: str | None = Field(default=None, max_length=64)


class DecisionStore:
    """Atomic single-process demo store. Each decision keeps its evidence snapshot."""

    def __init__(self, path: Path):
        self.path = path
        self.lock = RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.records = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        if not isinstance(self.records, list):
            raise ValueError("Plan decisions must be a JSON list")

    def record(self, payload: DecisionRequest, plan: dict, simulation: dict | None) -> dict:
        execution = {
            "execution_mode": payload.execution_mode.value,
            "department_id": payload.department_id,
            "contract_id": payload.contract_id,
            "amc_id": payload.amc_id,
            "oem_service_id": payload.oem_service_id,
        }
        snapshot = {"plan": plan, "simulation": simulation, "execution": execution}
        digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
        with self.lock:
            for record in reversed(self.records):
                if record["plan_id"] == payload.plan_id:
                    if record["decision"] == payload.decision and record["evidence_hash"] == digest:
                        return record
                    break
            result = {
                **payload.model_dump(mode="json"), "decision_id": f"D{len(self.records) + 1:04d}",
                "recorded_at": datetime.now(LOCAL_TIMEZONE).isoformat(),
                "evidence_hash": digest, "evidence": snapshot,
                "execution_started": False,
            }
            records = [*self.records, result]
            temporary_path = None
            try:
                with NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent, delete=False) as output:
                    temporary_path = Path(output.name)
                    json.dump(records, output, indent=2)
                os.replace(temporary_path, self.path)
            finally:
                if temporary_path is not None and temporary_path.exists():
                    temporary_path.unlink()
            self.records = records
            return result


router = APIRouter(tags=["human decisions"])


@router.post("/plan-decision")
def plan_decision(
    payload: DecisionRequest,
    request: Request,
    actor: Crew | None = Depends(admin_or_anonymous),
) -> dict:
    plan = request.app.state.plan_repository.get(payload.plan_id)
    if plan is None:
        raise HTTPException(404, "Optimization plan not found")
    if plan["maintenance_id"] != payload.maintenance_id:
        raise HTTPException(422, "Plan and maintenance requirement do not match")
    requirement = request.app.state.maintenance_repository.get(payload.maintenance_id)
    if requirement is None:
        raise HTTPException(404, "Maintenance requirement not found")
    simulation = None
    if payload.decision == "APPROVED":
        if plan["safety_conflicts"]:
            raise HTTPException(409, "Unsafe plans cannot be approved")
        # Revalidate the exact stored plan on its operating date before recording approval.
        operating_date = datetime.fromisoformat(plan["maintenance_window"]["start"]).astimezone(LOCAL_TIMEZONE).date()
        try:
            result = run_scenario(plan, operating_date, maintenance_requirement=requirement,
                                  repository=request.app.state.repository, railway_graph=request.app.state.graph,
                                  random_seed=42)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if result["kpis"]["conflicts_detected"] or not result["kpis"]["maintenance_completed"]:
            raise HTTPException(409, "Approval requires completed maintenance and zero simulated safety conflicts")
        simulation = {"simulation_date": result["simulation_date"], "random_seed": 42,
                      "kpis": result["kpis"], "maintenance": result["maintenance"]}
    if payload.decision == "APPROVED" and actor is not None:
        from backend.app.db.base import SessionLocal

        db = SessionLocal()
        try:
            existing = db.scalar(
                select(WorkOrder).where(WorkOrder.plan_id == payload.plan_id)
            )
            if existing and existing.execution_mode != payload.execution_mode.value:
                raise HTTPException(
                    409, "Execution mode cannot be changed after work-order creation"
                )
            expected_reference = {
                "DEPARTMENTAL": payload.department_id,
                "WORKS_CONTRACT": payload.contract_id,
                "AMC_CAMC": payload.amc_id,
                "OEM_AUTHORIZED": payload.oem_service_id,
                "EMERGENCY": None,
            }[payload.execution_mode.value]
            stored_reference = (
                existing.department_id
                if existing and existing.execution_mode == "DEPARTMENTAL"
                else existing.contract_id
                if existing and existing.execution_mode == "WORKS_CONTRACT"
                else existing.amc_id
                if existing and existing.execution_mode == "AMC_CAMC"
                else existing.oem_service_id
                if existing and existing.execution_mode == "OEM_AUTHORIZED"
                else None
            )
            if existing and expected_reference != stored_reference:
                raise HTTPException(
                    409, "Execution provider cannot be changed after work-order creation"
                )
        finally:
            db.close()
    try:
        decision = request.app.state.decision_store.record(payload, plan, simulation)
        if payload.decision == "APPROVED" and actor is not None:
            from backend.app.db.base import SessionLocal
            from backend.app.work_orders.service import create_from_plan, serialize
            db = SessionLocal()
            try:
                work_order = create_from_plan(
                    db, plan=plan, requirement=requirement, actor=actor,
                    execution={
                        "execution_mode": payload.execution_mode.value,
                        "department_id": payload.department_id,
                        "contract_id": payload.contract_id,
                        "amc_id": payload.amc_id,
                        "oem_service_id": payload.oem_service_id,
                    },
                )
                decision = {**decision, "work_order": serialize(work_order)}
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
            finally:
                db.close()
        return decision
    except OSError as exc:
        raise HTTPException(503, "Human decision could not be persisted") from exc
