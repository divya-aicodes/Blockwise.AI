"""Authenticated work-order endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth.service import current_crew, require_roles
from backend.app.db.base import get_db
from backend.app.db.models import Crew, WorkOrder
from backend.app.work_orders.service import assign, acknowledge, complete, create_from_plan, pause, resume, serialize, start, verify

router = APIRouter(prefix="/work-orders", tags=["work-orders"])


class CreateRequest(BaseModel):
    plan_id: str = Field(pattern=r"^P\d{3,}$")
    maintenance_id: str = Field(pattern=r"^M\d{3,}$")


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
    approved = any(r.get("plan_id") == payload.plan_id and r.get("maintenance_id") == payload.maintenance_id and r.get("decision") == "APPROVED" for r in request.app.state.decision_store.records)
    if not approved:
        raise HTTPException(409, "Only an approved plan can create a work order")
    try:
        return serialize(create_from_plan(db, plan=plan, requirement=requirement, actor=actor))
    except ValueError as exc:
        raise fail(exc) from exc


@router.get("")
def list_orders(status: str | None = Query(default=None, max_length=20), crew_id: str | None = Query(default=None, max_length=36), actor: Crew = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)):
    query = select(WorkOrder)
    if crew_id:
        query = query.where(WorkOrder.assigned_crew_id == crew_id)
    if status:
        query = query.where(WorkOrder.status == status.upper())
    return [serialize(order) for order in db.scalars(query.order_by(WorkOrder.created_at.desc())).all()]


@router.get("/{order_id}")
def get(order_id: str, _: Crew = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)):
    order = db.get(WorkOrder, order_id)
    if not order:
        raise HTTPException(404, "Work order not found")
    return serialize(order)


@router.post("/{order_id}/assign")
def assign_order(order_id: str, payload: AssignRequest, actor: Crew = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)):
    try:
        return serialize(assign(db, order_id, payload.crew_employee_id, actor))
    except ValueError as exc:
        raise fail(exc) from exc


@router.post("/{order_id}/acknowledge")
def acknowledge_order(order_id: str, actor: Crew = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)):
    try:
        return serialize(acknowledge(db, order_id, actor))
    except ValueError as exc:
        raise fail(exc) from exc


@router.post("/{order_id}/start")
def start_order(order_id: str, payload: StartRequest, actor: Crew = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)):
    try:
        return serialize(start(db, order_id, actor, payload.model_dump()))
    except ValueError as exc:
        raise fail(exc) from exc


@router.post("/{order_id}/pause")
def pause_order(order_id: str, payload: PauseRequest, actor: Crew = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)):
    try:
        return serialize(pause(db, order_id, actor, payload.reason))
    except ValueError as exc:
        raise fail(exc) from exc


@router.post("/{order_id}/resume")
def resume_order(order_id: str, actor: Crew = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)):
    try:
        return serialize(resume(db, order_id, actor))
    except ValueError as exc:
        raise fail(exc) from exc


@router.post("/{order_id}/complete")
def complete_order(order_id: str, payload: CompleteRequest, actor: Crew = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)):
    try:
        return serialize(complete(db, order_id, actor, {"latitude": payload.latitude, "longitude": payload.longitude}, payload.notes, payload.photos))
    except ValueError as exc:
        raise fail(exc) from exc


@router.post("/{order_id}/verify")
def verify_order(order_id: str, payload: VerifyRequest, actor: Crew = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)):
    try:
        return serialize(verify(db, order_id, actor, payload.approved, payload.comments))
    except ValueError as exc:
        raise fail(exc) from exc
