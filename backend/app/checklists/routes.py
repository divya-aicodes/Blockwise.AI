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

router = APIRouter(prefix="/checklists", tags=["checklists"])


class ItemRequest(BaseModel):
    item_id: str = Field(min_length=1, max_length=64)
    value: bool
    note: str = Field(default="", max_length=500)


@router.get("/templates")
def list_templates(_: Crew = Depends(require_roles("ADMIN"))) -> list[dict]:
    return get_templates()


@router.post("/{wo_id}")
def create_for_wo(wo_id: str, _: Crew = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)) -> dict:
    try:
        return {"checklists": [serialize(item) for item in create_for_work_order(db, wo_id)]}
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/work-order/{wo_id}")
def list_for_work_order(wo_id: str, _: Crew = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)) -> dict:
    order = db.get(WorkOrder, wo_id)
    if not order:
        raise HTTPException(404, "Work order not found")
    return {"checklists": [serialize(item) for item in db.scalars(select(Checklist).where(Checklist.work_order_id == wo_id).order_by(Checklist.type)).all()]}


@router.post("/{checklist_id}/item")
def update_checklist_item(checklist_id: str, payload: ItemRequest, _: Crew = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)) -> dict:
    try:
        return serialize(update_item(db, checklist_id, payload.item_id, payload.value, payload.note))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/{checklist_id}/sign-off")
def sign_off_checklist(checklist_id: str, actor: Crew = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)) -> dict:
    try:
        return serialize(sign_off(db, checklist_id, actor))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/{checklist_id}/validate")
def validate(checklist_id: str, _: Crew = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)) -> dict:
    try:
        valid, incomplete = validate_mandatory_complete(db, checklist_id)
        return {"valid": valid, "incomplete": incomplete}
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
