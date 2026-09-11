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

from backend.app.schemas import StrictModel
from backend.app.simulation.conflict_detector import LOCAL_TIMEZONE
from backend.app.simulation.scenario_runner import run_scenario
from backend.app.auth.service import admin_or_anonymous
from backend.app.db.models import Crew


class DecisionRequest(StrictModel):
    plan_id: str = Field(pattern=r"^P\d{3,}$")
    maintenance_id: str = Field(pattern=r"^M\d{3,}$")
    decision: Literal["APPROVED", "MODIFY", "REJECTED"]


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
        snapshot = {"plan": plan, "simulation": simulation}
        digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
        with self.lock:
            for record in reversed(self.records):
                if record["plan_id"] == payload.plan_id:
                    if record["decision"] == payload.decision and record["evidence_hash"] == digest:
                        return record
                    break
            result = {
                **payload.model_dump(), "decision_id": f"D{len(self.records) + 1:04d}",
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
    try:
        decision = request.app.state.decision_store.record(payload, plan, simulation)
        if payload.decision == "APPROVED" and actor is not None:
            from backend.app.db.base import SessionLocal
            from backend.app.work_orders.service import create_from_plan, serialize
            db = SessionLocal()
            try:
                work_order = create_from_plan(db, plan=plan, requirement=requirement, actor=actor)
                decision = {**decision, "work_order": serialize(work_order)}
            finally:
                db.close()
        return decision
    except OSError as exc:
        raise HTTPException(503, "Human decision could not be persisted") from exc
