"""Execution-ready recommendation assembled from existing planning evidence."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth.service import require_roles
from backend.app.db.base import get_db
from backend.app.db.models import Crew, WorkOrder
from backend.app.schemas import ExecutionMode, StrictModel
from backend.app.simulation.conflict_detector import LOCAL_TIMEZONE
from backend.app.simulation.scenario_runner import run_scenario
from backend.app.work_orders.readiness import (
    latest_decision_record,
    validate_execution_readiness,
)

router = APIRouter(prefix="/planning", tags=["planning"])


class RecommendationRequest(StrictModel):
    maintenance_id: str = Field(pattern=r"^M\d{3,}$")
    plan_id: str = Field(pattern=r"^P\d{3,}$")
    execution_mode: ExecutionMode = ExecutionMode.departmental
    department_id: str | None = Field(default=None, max_length=64)
    contract_id: str | None = Field(default=None, max_length=64)
    amc_id: str | None = Field(default=None, max_length=64)
    oem_service_id: str | None = Field(default=None, max_length=64)


def _requested_reference(payload: RecommendationRequest) -> str | None:
    return {
        ExecutionMode.departmental: payload.department_id,
        ExecutionMode.works_contract: payload.contract_id,
        ExecutionMode.amc_camc: payload.amc_id,
        ExecutionMode.oem_authorized: payload.oem_service_id,
        ExecutionMode.emergency: None,
    }[payload.execution_mode]


def _stored_reference(order: WorkOrder) -> str | None:
    return {
        "DEPARTMENTAL": order.department_id,
        "WORKS_CONTRACT": order.contract_id,
        "AMC_CAMC": order.amc_id,
        "OEM_AUTHORIZED": order.oem_service_id,
        "EMERGENCY": None,
    }.get(order.execution_mode)


@router.post("/recommendation")
def planning_recommendation(
    payload: RecommendationRequest,
    request: Request,
    _: Crew = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
) -> dict:
    requirement = request.app.state.maintenance_repository.get(payload.maintenance_id)
    if requirement is None:
        raise HTTPException(404, "Maintenance requirement not found")
    plan = request.app.state.plan_repository.get(payload.plan_id)
    if plan is None:
        raise HTTPException(404, "Optimization plan not found")
    if str(plan.get("maintenance_id")) != payload.maintenance_id:
        raise HTTPException(422, "Plan and maintenance requirement do not match")

    order = db.scalar(select(WorkOrder).where(WorkOrder.plan_id == payload.plan_id))
    if order and order.maintenance_id != payload.maintenance_id:
        raise HTTPException(409, "Stored work order does not match the maintenance requirement")
    if order and order.execution_mode != payload.execution_mode.value:
        raise HTTPException(409, "Execution mode cannot be changed after work-order creation")
    requested_reference = _requested_reference(payload)
    if order and requested_reference and requested_reference != _stored_reference(order):
        raise HTTPException(409, "Execution provider cannot be changed after work-order creation")

    decision = latest_decision_record(
        request.app.state.decision_store.records,
        payload.plan_id,
        payload.maintenance_id,
    )
    approval_status = str(decision.get("decision")) if decision else "NOT_REVIEWED"
    if approval_status == "APPROVED":
        approved_mode = str(decision.get("execution_mode") or "DEPARTMENTAL")
        if payload.execution_mode.value != approved_mode:
            raise HTTPException(409, "Execution mode does not match the approved decision")
        for field in ("department_id", "contract_id", "amc_id", "oem_service_id"):
            approved_reference = decision.get(field)
            if getattr(payload, field) != approved_reference:
                raise HTTPException(409, f"{field} does not match the approved decision")
    approved = approval_status == "APPROVED"
    reasons: list[str]
    crew: dict | None = None
    if order:
        readiness = validate_execution_readiness(
            db, order, plan=plan, approved=approved
        )
        assigned = db.get(Crew, order.assigned_crew_id) if order.assigned_crew_id else None
        if assigned:
            crew = {
                "id": assigned.id,
                "employee_id": assigned.employee_id,
                "name": assigned.full_name,
                "primary_skill": assigned.primary_skill,
            }
        reasons = list(readiness["resource_reasons"])
    else:
        missing_reference = (
            payload.execution_mode in {
                ExecutionMode.works_contract,
                ExecutionMode.amc_camc,
                ExecutionMode.oem_authorized,
            }
            and not requested_reference
        )
        reasons = ["Approved work order has not been created", "No crew is assigned"]
        if missing_reference:
            reasons.append(f"{payload.execution_mode.value} reference is missing")
        if not approved:
            reasons.append("Plan has not been approved")
        readiness = {
            "manpower_available": False,
            "equipment_available": False,
            "materials_available": False,
            "resource_conflict": True,
            "resource_conflicts": reasons,
            "validation_status": "NOT_READY",
            "executable": False,
        }

    operating_date = datetime.fromisoformat(
        plan["maintenance_window"]["start"]
    ).astimezone(LOCAL_TIMEZONE).date()
    try:
        simulation = run_scenario(
            plan,
            operating_date,
            maintenance_requirement=requirement,
            repository=request.app.state.repository,
            railway_graph=request.app.state.graph,
            random_seed=42,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    safety_conflicts = int(plan.get("safety_conflicts", 0))
    return {
        "maintenance_id": payload.maintenance_id,
        "plan_id": payload.plan_id,
        "work_order_id": order.id if order else None,
        "recommended_window": plan["maintenance_window"],
        "execution_mode": payload.execution_mode.value,
        "crew": crew,
        "manpower_available": readiness["manpower_available"],
        "equipment_available": readiness["equipment_available"],
        "materials_available": readiness["materials_available"],
        "resource_conflict": readiness["resource_conflict"],
        "expected_delay_min": int(plan["total_train_delay_min"]),
        "simulation_delay_min": int(simulation["kpis"]["total_delay_min"]),
        "safety_conflicts": safety_conflicts,
        "risk_reduction": float(plan["risk_reduction_estimate"]),
        "recommendation_reasons": reasons,
        "validation_status": readiness["validation_status"],
        "approval_status": approval_status,
        "executable": bool(readiness["executable"] and safety_conflicts == 0),
    }
