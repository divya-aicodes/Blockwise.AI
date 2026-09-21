"""Authenticated checklist endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.auth.service import current_crew, require_roles
from backend.app.checklists.service import create_for_work_order, get_templates, serialize, sign_off, update_item, validate_mandatory_complete
from backend.app.db.base import get_db
from backend.app.db.models import Checklist, Crew, WorkOrder
from backend.app.work_orders.service import can_access_work_order

router = APIRouter(prefix="/checklists", tags=["checklists"])


class ItemRequest(BaseModel):
    item_id: str = Field(min_length=1, max_length=64)
    value: bool
    note: str = Field(default="", max_length=500)


@router.get("/templates")
def list_templates(_: Crew = Depends(current_crew)) -> list[dict]:
    return get_templates()


def _authorize_work_order(order: WorkOrder | None, actor: Crew) -> WorkOrder:
    if not order:
        raise HTTPException(404, "Work order not found")
    if not can_access_work_order(order, actor):
        raise HTTPException(403, "Checklist access denied")
    return order


def _authorize_checklist(
    db: Session, checklist_id: str, actor: Crew, *, mutate: bool = False
) -> Checklist:
    checklist = db.get(Checklist, checklist_id)
    if not checklist:
        raise HTTPException(404, "Checklist not found")
    order = _authorize_work_order(db.get(WorkOrder, checklist.work_order_id), actor)
    if mutate and actor.role.upper() != "ADMIN" and actor.id not in {
        order.assigned_crew_id,
        order.supervisor_id,
    }:
        raise HTTPException(403, "Only assigned crew or supervisor can update this checklist")
    return checklist


@router.post("/{wo_id}")
def create_for_wo(wo_id: str, _: Crew = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)) -> dict:
    try:
        return {"checklists": [serialize(item) for item in create_for_work_order(db, wo_id)]}
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/work-order/{wo_id}")
def list_for_work_order(wo_id: str, actor: Crew = Depends(current_crew), db: Session = Depends(get_db)) -> dict:
    _authorize_work_order(db.get(WorkOrder, wo_id), actor)
    return {"checklists": [serialize(item) for item in db.scalars(select(Checklist).where(Checklist.work_order_id == wo_id).order_by(Checklist.type)).all()]}


@router.post("/{checklist_id}/item")
def update_checklist_item(checklist_id: str, payload: ItemRequest, actor: Crew = Depends(current_crew), db: Session = Depends(get_db)) -> dict:
    try:
        _authorize_checklist(db, checklist_id, actor, mutate=True)
        return serialize(update_item(db, checklist_id, payload.item_id, payload.value, payload.note))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/{checklist_id}/sign-off")
def sign_off_checklist(checklist_id: str, actor: Crew = Depends(current_crew), db: Session = Depends(get_db)) -> dict:
    try:
        _authorize_checklist(db, checklist_id, actor, mutate=True)
        return serialize(sign_off(db, checklist_id, actor))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/{checklist_id}/validate")
def validate(checklist_id: str, actor: Crew = Depends(current_crew), db: Session = Depends(get_db)) -> dict:
    try:
        _authorize_checklist(db, checklist_id, actor)
        valid, incomplete = validate_mandatory_complete(db, checklist_id)
        return {"valid": valid, "incomplete": incomplete}
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
