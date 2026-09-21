"""Authenticated work-order endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth.service import current_crew, require_roles
from backend.app.db.base import get_db
from backend.app.db.models import Crew, WorkOrder
from backend.app.simulation.conflict_detector import LOCAL_TIMEZONE
from backend.app.simulation.scenario_runner import run_scenario
from backend.app.work_orders.readiness import latest_decision_record, latest_decision_status, validate_execution_readiness
from backend.app.work_orders.service import assign, acknowledge, can_access_work_order, complete, create_from_plan, pause, resume, serialize, start, verify

router = APIRouter(prefix="/work-orders", tags=["work-orders"])


class CreateRequest(BaseModel):
    plan_id: str = Field(pattern=r"^P\d{3,}$")
    maintenance_id: str = Field(pattern=r"^M\d{3,}$")
    execution_mode: Literal["DEPARTMENTAL", "WORKS_CONTRACT", "AMC_CAMC", "OEM_AUTHORIZED", "EMERGENCY"] = "DEPARTMENTAL"
    department_id: str | None = Field(default=None, max_length=64)
    contract_id: str | None = Field(default=None, max_length=64)
    amc_id: str | None = Field(default=None, max_length=64)
    oem_service_id: str | None = Field(default=None, max_length=64)


class AssignRequest(BaseModel):
    crew_employee_id: str = Field(min_length=3, max_length=20)


class StartRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class PauseRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=500)


class CompleteRequest(StartRequest):
    notes: str = Field(default="", max_length=2000)
    photos: list[str] = Field(default_factory=list, max_length=10)


class VerifyRequest(BaseModel):
    approved: bool
    comments: str = Field(default="", max_length=2000)


def fail(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


@router.post("", status_code=201)
def create(payload: CreateRequest, request: Request, actor: Crew = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)):
    plan = request.app.state.plan_repository.get(payload.plan_id)
    requirement = request.app.state.maintenance_repository.get(payload.maintenance_id)
    if not plan or not requirement:
        raise HTTPException(404, "Approved plan or maintenance requirement not found")
    decision = latest_decision_record(
        request.app.state.decision_store.records,
        payload.plan_id,
        payload.maintenance_id,
    )
    approval_status = str(decision.get("decision")) if decision else "NOT_REVIEWED"
    approved = approval_status == "APPROVED"
    if not approved:
        raise HTTPException(409, "Only an approved plan can create a work order")
    approved_mode = str(decision.get("execution_mode") or "DEPARTMENTAL")
    if payload.execution_mode != approved_mode:
        raise HTTPException(409, "Work-order execution mode must match the approved decision")
    for field in ("department_id", "contract_id", "amc_id", "oem_service_id"):
        approved_reference = decision.get(field)
        if getattr(payload, field) != approved_reference:
            raise HTTPException(409, f"{field} must match the approved decision")
    try:
        return serialize(create_from_plan(db, plan=plan, requirement=requirement, actor=actor, execution=payload.model_dump(exclude={"plan_id", "maintenance_id"})))
    except ValueError as exc:
        raise fail(exc) from exc


@router.get("")
def list_orders(status: str | None = Query(default=None, max_length=20), crew_id: str | None = Query(default=None, max_length=36), actor: Crew = Depends(current_crew), db: Session = Depends(get_db)):
    query = select(WorkOrder)
    if actor.role.upper() == "ADMIN" and crew_id:
        query = query.where(WorkOrder.assigned_crew_id == crew_id)
    if status:
        query = query.where(WorkOrder.status == status.upper())
    orders = db.scalars(query.order_by(WorkOrder.created_at.desc())).all()
    if actor.role.upper() != "ADMIN":
        orders = [order for order in orders if can_access_work_order(order, actor)]
    return [serialize(order) for order in orders]


def _authorized_order(db: Session, order_id: str, actor: Crew) -> WorkOrder:
    order = db.get(WorkOrder, order_id)
    if not order:
        raise HTTPException(404, "Work order not found")
    if not can_access_work_order(order, actor):
        raise HTTPException(403, "Work order access denied")
    return order


@router.get("/{order_id}/execution-summary")
def execution_summary(order_id: str, request: Request, actor: Crew = Depends(current_crew), db: Session = Depends(get_db)) -> dict:
    order = _authorized_order(db, order_id, actor)
    plan = request.app.state.plan_repository.get(str(order.plan_id)) if order.plan_id else None
    requirement = request.app.state.maintenance_repository.get(str(order.maintenance_id)) if order.maintenance_id else None
    approval_status = latest_decision_status(
        request.app.state.decision_store.records,
        order.plan_id,
        order.maintenance_id,
    )
    approved = approval_status == "APPROVED"
    readiness = validate_execution_readiness(db, order, plan=plan, approved=approved)
    crew = db.get(Crew, order.assigned_crew_id) if order.assigned_crew_id else None
    supervisor = db.get(Crew, order.supervisor_id) if order.supervisor_id else None
    simulation_summary = None
    if plan and requirement:
        operating_date = datetime.fromisoformat(plan["maintenance_window"]["start"]).astimezone(LOCAL_TIMEZONE).date()
        result = run_scenario(plan, operating_date, maintenance_requirement=requirement, repository=request.app.state.repository, railway_graph=request.app.state.graph, random_seed=42)
        simulation_summary = {"simulation_date": result["simulation_date"], "kpis": result["kpis"], "maintenance": result["maintenance"]}
    return {
        "work_order": serialize(order),
        "who": {"crew": {"id": crew.id, "employee_id": crew.employee_id, "name": crew.full_name} if crew else None, "supervisor": {"id": supervisor.id, "employee_id": supervisor.employee_id, "name": supervisor.full_name} if supervisor else None, "department_id": order.department_id, "provider_reference": order.contract_id or order.amc_id or order.oem_service_id},
        "what": {"activity": order.title, "instructions": order.description},
        "where": {"asset_id": order.asset_id, "section_id": order.section_id, "location": None, "chainage": None},
        "when": {"reporting_time": order.planned_start.isoformat() if order.planned_start else None, "planned_start": order.planned_start.isoformat() if order.planned_start else None, "planned_end": order.planned_end.isoformat() if order.planned_end else None},
        "how": {"instructions": order.description, "safety_requirements": "Complete mandatory safety checklist before start"},
        "resources": readiness,
        "execution_status": {"execution_mode": order.execution_mode, "approval_status": approval_status, "simulation_summary": simulation_summary, "safety_validation": {"valid": bool(plan) and int(plan.get("safety_conflicts", 1)) == 0, "safety_conflicts": int(plan.get("safety_conflicts", 0)) if plan else None}, "recommendation_reasons": readiness["resource_reasons"], "executable": readiness["executable"]},
    }


@router.get("/{order_id}")
def get(order_id: str, actor: Crew = Depends(current_crew), db: Session = Depends(get_db)):
    return serialize(_authorized_order(db, order_id, actor))


@router.post("/{order_id}/assign")
def assign_order(order_id: str, payload: AssignRequest, request: Request, actor: Crew = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)):
    try:
        order = db.get(WorkOrder, order_id)
        if not order:
            raise ValueError("Work order not found")
        plan = request.app.state.plan_repository.get(str(order.plan_id)) if order.plan_id else None
        approved = latest_decision_status(
            request.app.state.decision_store.records,
            order.plan_id,
            order.maintenance_id,
        ) == "APPROVED"
        return serialize(assign(
            db,
            order_id,
            payload.crew_employee_id,
            actor,
            plan=plan,
            approved=approved,
        ))
    except ValueError as exc:
        raise fail(exc) from exc


@router.post("/{order_id}/acknowledge")
def acknowledge_order(order_id: str, actor: Crew = Depends(current_crew), db: Session = Depends(get_db)):
    try:
        return serialize(acknowledge(db, order_id, actor))
    except ValueError as exc:
        raise fail(exc) from exc


@router.post("/{order_id}/start")
def start_order(order_id: str, payload: StartRequest, actor: Crew = Depends(current_crew), db: Session = Depends(get_db)):
    try:
        return serialize(start(db, order_id, actor, payload.model_dump()))
    except ValueError as exc:
        raise fail(exc) from exc


@router.post("/{order_id}/pause")
def pause_order(order_id: str, payload: PauseRequest, actor: Crew = Depends(current_crew), db: Session = Depends(get_db)):
    try:
        return serialize(pause(db, order_id, actor, payload.reason))
    except ValueError as exc:
        raise fail(exc) from exc


@router.post("/{order_id}/resume")
def resume_order(order_id: str, actor: Crew = Depends(current_crew), db: Session = Depends(get_db)):
    try:
        return serialize(resume(db, order_id, actor))
    except ValueError as exc:
        raise fail(exc) from exc


@router.post("/{order_id}/complete")
def complete_order(order_id: str, payload: CompleteRequest, actor: Crew = Depends(current_crew), db: Session = Depends(get_db)):
    try:
        return serialize(complete(db, order_id, actor, {"latitude": payload.latitude, "longitude": payload.longitude}, payload.notes, payload.photos))
    except ValueError as exc:
        raise fail(exc) from exc


@router.post("/{order_id}/verify")
def verify_order(order_id: str, payload: VerifyRequest, actor: Crew = Depends(current_crew), db: Session = Depends(get_db)):
    try:
        return serialize(verify(db, order_id, actor, payload.approved, payload.comments))
    except ValueError as exc:
        raise fail(exc) from exc
