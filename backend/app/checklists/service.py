"""Checklist templates and safe sign-off rules for field work."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import Checklist, Crew, WorkOrder


TEMPLATES = (
    {
        "version": "1.0", "type": "SAFETY",
        "title": "Pre-start safety / काम शुरू करने से पहले सुरक्षा",
        "items": (
            {"id": "power_isolation", "text": "Power isolation confirmed / बिजली अलग होना सुनिश्चित", "required": True, "type": "checkbox"},
            {"id": "possession", "text": "Track possession certificate obtained / ट्रैक पॉज़ेशन प्रमाणपत्र प्राप्त", "required": True, "type": "checkbox"},
        ), "mandatory": True,
    },
    {
        "version": "1.0", "type": "MATERIALS", "title": "Materials / सामग्री",
        "items": ({"id": "materials", "text": "Required materials available / आवश्यक सामग्री उपलब्ध", "required": False, "type": "checkbox"},), "mandatory": False,
    },
    {
        "version": "1.0", "type": "EQUIPMENT", "title": "Equipment / उपकरण",
        "items": ({"id": "equipment", "text": "Equipment inspected / उपकरण की जांच", "required": False, "type": "checkbox"},), "mandatory": False,
    },
)


def get_templates(asset_type: str = "", job_type: str = "") -> list[dict]:
    return [dict(template, items=[dict(item) for item in template["items"]]) for template in TEMPLATES]


def serialize(checklist: Checklist) -> dict:
    return {
        "id": checklist.id, "work_order_id": checklist.work_order_id, "type": checklist.type,
        "template_version": checklist.template_version, "items": checklist.items or [],
        "completed_items": checklist.completed_items or {}, "is_mandatory": checklist.is_mandatory,
        "signed_by": checklist.signed_by, "signed_at": checklist.signed_at.isoformat() if checklist.signed_at else None,
    }


def create_for_work_order(db: Session, wo_id: str) -> list[Checklist]:
    if not db.get(WorkOrder, wo_id):
        raise ValueError("Work order not found")
    existing = list(db.scalars(select(Checklist).where(Checklist.work_order_id == wo_id).order_by(Checklist.type)).all())
    if existing:
        return existing
    result: list[Checklist] = []
    for template in TEMPLATES:
        checklist = Checklist(work_order_id=wo_id, type=template["type"], template_version=template["version"], items=[dict(item) for item in template["items"]], completed_items={}, is_mandatory=template["mandatory"])
        db.add(checklist)
        result.append(checklist)
    db.commit()
    for checklist in result:
        db.refresh(checklist)
    return result


def update_item(db: Session, checklist_id: str, item_id: str, value: bool, note: str | None = None) -> Checklist:
    checklist = db.get(Checklist, checklist_id)
    if not checklist:
        raise ValueError("Checklist not found")
    if checklist.signed_at:
        raise ValueError("Signed checklist cannot be changed")
    if not any(item.get("id") == item_id for item in (checklist.items or [])):
        raise ValueError("Checklist item not found")
    completed = dict(checklist.completed_items or {})
    completed[item_id] = {"value": bool(value), "note": (note or "").strip()}
    checklist.completed_items = completed
    db.commit()
    db.refresh(checklist)
    return checklist


def validate_mandatory_complete(db: Session, checklist_id: str) -> tuple[bool, list[str]]:
    checklist = db.get(Checklist, checklist_id)
    if not checklist:
        raise ValueError("Checklist not found")
    required = [item["id"] for item in (checklist.items or []) if item.get("required")]
    completed = checklist.completed_items or {}
    incomplete = [item_id for item_id in required if not bool((completed.get(item_id) or {}).get("value"))]
    return not incomplete, incomplete


def sign_off(db: Session, checklist_id: str, actor: Crew) -> Checklist:
    checklist = db.get(Checklist, checklist_id)
    if not checklist:
        raise ValueError("Checklist not found")
    work_order = db.get(WorkOrder, checklist.work_order_id)
    if not work_order or (actor.role.upper() != "ADMIN" and work_order.assigned_crew_id != actor.id and work_order.supervisor_id != actor.id):
        raise ValueError("Only assigned crew or supervisor can sign off this checklist")
    valid, incomplete = validate_mandatory_complete(db, checklist_id)
    if checklist.is_mandatory and not valid:
        raise ValueError("Complete mandatory items: " + ", ".join(incomplete))
    checklist.signed_by = actor.id
    checklist.signed_at = datetime.utcnow()
    db.commit()
    db.refresh(checklist)
    return checklist
