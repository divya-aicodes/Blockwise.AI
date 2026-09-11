"""Transactional work-order state machine."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import AuditLog, Checklist, Crew, WorkOrder
from backend.app.notifications.service import create_notification

TRANSITIONS = {
    "DRAFT": {"ASSIGNED"}, "ASSIGNED": {"ACKNOWLEDGED"},
    "ACKNOWLEDGED": {"IN_PROGRESS"}, "IN_PROGRESS": {"PAUSED", "COMPLETED"},
    "PAUSED": {"IN_PROGRESS"}, "COMPLETED": {"VERIFIED", "REJECTED"},
}


def _audit(db: Session, actor: Crew, action: str, order: WorkOrder, before: str | None = None) -> None:
    db.add(AuditLog(user_id=actor.id, action=action, entity_type="WORK_ORDER", entity_id=order.id, before={"status": before} if before else None, after={"status": order.status, "work_order_number": order.work_order_number}))


def serialize(order: WorkOrder) -> dict:
    return {"id": order.id, "work_order_number": order.work_order_number, "plan_id": order.plan_id, "maintenance_id": order.maintenance_id, "title": order.title, "section_id": order.section_id, "asset_id": order.asset_id, "asset_type": order.asset_type, "required_skill": order.required_skill, "priority": order.priority, "status": order.status, "assigned_crew_id": order.assigned_crew_id, "supervisor_id": order.supervisor_id, "planned_start": order.planned_start.isoformat() if order.planned_start else None, "planned_end": order.planned_end.isoformat() if order.planned_end else None, "actual_start": order.actual_start.isoformat() if order.actual_start else None, "actual_end": order.actual_end.isoformat() if order.actual_end else None, "estimated_duration_min": order.estimated_duration_min, "actual_duration_min": order.actual_duration_min, "variance_minutes": order.variance_minutes, "overtime_minutes": order.overtime_minutes, "gps_start": order.gps_start, "gps_end": order.gps_end, "material_cost": float(order.material_cost or 0), "equipment_cost": float(order.equipment_cost or 0), "notes": order.notes, "rejection_reason": order.rejection_reason}


def calculate_metrics(order: WorkOrder) -> dict:
    planned = int(order.estimated_duration_min or 0)
    actual = int(order.actual_duration_min or 0)
    variance = actual - planned if order.actual_duration_min is not None else None
    return {"variance_minutes": variance, "overtime_minutes": max(0, variance or 0), "total_cost": float(order.material_cost or 0) + float(order.equipment_cost or 0)}


def create_from_plan(db: Session, *, plan: dict, requirement: dict, actor: Crew) -> WorkOrder:
    if plan.get("maintenance_id") != requirement.get("maintenance_id"):
        raise ValueError("Plan and maintenance requirement do not match")
    existing = db.scalar(select(WorkOrder).where(WorkOrder.plan_id == plan["plan_id"]))
    if existing:
        return existing
    window = plan["maintenance_window"]
    urgency = str(requirement.get("urgency", "NORMAL"))
    priority = "EMERGENCY" if urgency == "EMERGENCY" else "HIGH" if urgency == "HIGH" else "MEDIUM"
    order = WorkOrder(work_order_number=f"WO-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}", plan_id=plan["plan_id"], maintenance_id=requirement["maintenance_id"], title=f"Maintenance {requirement.get('asset_id', '')}", description="Approved maintenance work order; execution remains under railway possession controls.", section_id=str(requirement["section_id"]), asset_id=str(requirement.get("asset_id", "")), asset_type=str(requirement.get("asset_type", "")) or None, required_skill=str(requirement.get("required_skill", "TRACK")), priority=priority, status="DRAFT", planned_start=datetime.fromisoformat(window["start"]), planned_end=datetime.fromisoformat(window["end"]), estimated_duration_min=int(requirement.get("minimum_duration_min", 1)), created_by=actor.id)
    db.add(order)
    db.flush()
    templates = [("SAFETY", True, [{"id": "power_isolation", "text": "Power isolation confirmed", "required": True}, {"id": "possession", "text": "Track possession certificate obtained", "required": True}]), ("MATERIALS", False, [{"id": "materials", "text": "Required materials available", "required": False}]), ("EQUIPMENT", False, [{"id": "equipment", "text": "Required equipment inspected", "required": False}])]
    for kind, mandatory, items in templates:
        db.add(Checklist(work_order_id=order.id, type=kind, template_version="1.0", items=items, completed_items={}, is_mandatory=mandatory))
    _audit(db, actor, "WORK_ORDER_CREATED", order)
    db.commit()
    db.refresh(order)
    return order


def _get_order(db: Session, order_id: str) -> WorkOrder:
    order = db.get(WorkOrder, order_id)
    if not order:
        raise ValueError("Work order not found")
    return order


def _can_operate(order: WorkOrder, actor: Crew) -> bool:
    """Administrators can operate any order; workers are never called here."""
    return actor.role.upper() == "ADMIN" or order.assigned_crew_id == actor.id


def _transition(db: Session, order: WorkOrder, target: str, actor: Crew) -> WorkOrder:
    if target not in TRANSITIONS.get(order.status, set()):
        raise ValueError(f"Work order cannot move from {order.status} to {target}")
    before = order.status
    order.status = target
    order.updated_at = datetime.utcnow()
    _audit(db, actor, f"WORK_ORDER_{target}", order, before)
    db.commit()
    db.refresh(order)
    return order


def assign(db: Session, order_id: str, crew_employee_id: str, supervisor: Crew) -> WorkOrder:
    order = _get_order(db, order_id)
    crew = db.scalar(select(Crew).where(Crew.employee_id == crew_employee_id, Crew.is_active.is_(True)))
    if not crew:
        raise ValueError("Active crew member not found")
    if crew.primary_skill != order.required_skill and order.required_skill not in (crew.secondary_skills or []):
        raise ValueError("Crew member does not have the required skill")
    order.assigned_crew_id = crew.id
    order.supervisor_id = supervisor.id
    result = _transition(db, order, "ASSIGNED", supervisor)
    create_notification(db, user_id=crew.id, notif_type="WORK_ORDER_ASSIGNED", title="New planned work assigned", message=f"{order.work_order_number}: What: {order.title}. Where: {order.section_id} / asset {order.asset_id}. When: {order.planned_start:%d %b %Y, %H:%M}–{order.planned_end:%H:%M}. Priority: {order.priority}. Skill: {order.required_skill}. Plan: {order.plan_id} · Maintenance: {order.maintenance_id}.", payload={"work_order_id": order.id, "work_order_number": order.work_order_number, "title": order.title, "section_id": order.section_id, "asset_id": order.asset_id, "planned_start": order.planned_start.isoformat() if order.planned_start else None, "planned_end": order.planned_end.isoformat() if order.planned_end else None, "priority": order.priority, "required_skill": order.required_skill})
    return result


def acknowledge(db: Session, order_id: str, actor: Crew) -> WorkOrder:
    order = _get_order(db, order_id)
    if not _can_operate(order, actor):
        raise ValueError("Only the assigned crew member can acknowledge this order")
    return _transition(db, order, "ACKNOWLEDGED", actor)


def start(db: Session, order_id: str, actor: Crew, gps: dict) -> WorkOrder:
    order = _get_order(db, order_id)
    if not _can_operate(order, actor):
        raise ValueError("Only the assigned crew member can start this order")
    checklist = db.scalar(select(Checklist).where(Checklist.work_order_id == order.id, Checklist.type == "SAFETY"))
    completed = checklist.completed_items if checklist else {}
    required = [item["id"] for item in (checklist.items if checklist else []) if item.get("required")]
    if checklist and any(not completed.get(item_id) for item_id in required):
        raise ValueError("Complete all mandatory safety checklist items before starting")
    order.actual_start = datetime.utcnow()
    order.gps_start = gps
    order.evidence = {**(order.evidence or {}), "start_gps": gps}
    return _transition(db, order, "IN_PROGRESS", actor)


def pause(db: Session, order_id: str, actor: Crew, reason: str) -> WorkOrder:
    order = _get_order(db, order_id)
    if not _can_operate(order, actor):
        raise ValueError("Only the assigned crew member can pause this order")
    order.notes = f"{order.notes or ''}\nPaused: {reason}".strip()
    return _transition(db, order, "PAUSED", actor)


def resume(db: Session, order_id: str, actor: Crew) -> WorkOrder:
    order = _get_order(db, order_id)
    if not _can_operate(order, actor):
        raise ValueError("Only the assigned crew member can resume this order")
    return _transition(db, order, "IN_PROGRESS", actor)


def complete(db: Session, order_id: str, actor: Crew, gps: dict, notes: str, photos: list[str]) -> WorkOrder:
    order = _get_order(db, order_id)
    if not _can_operate(order, actor):
        raise ValueError("Only the assigned crew member can complete this order")
    order.actual_end = datetime.utcnow()
    order.actual_duration_min = max(0, round((order.actual_end - order.actual_start).total_seconds() / 60)) if order.actual_start else 0
    order.notes = f"{order.notes or ''}\n{notes}".strip()
    order.gps_end = gps
    order.evidence = {**(order.evidence or {}), "end_gps": gps, "photos": photos}
    metrics = calculate_metrics(order)
    order.variance_minutes = metrics["variance_minutes"]
    order.overtime_minutes = metrics["overtime_minutes"]
    result = _transition(db, order, "COMPLETED", actor)
    if order.supervisor_id:
        create_notification(db, user_id=order.supervisor_id, notif_type="APPROVAL_REQUIRED", title="Verification required", message=f"{order.work_order_number} is ready for verification.", payload={"work_order_id": order.id})
    return result


def verify(db: Session, order_id: str, actor: Crew, approved: bool, comments: str) -> WorkOrder:
    order = _get_order(db, order_id)
    if actor.role.upper() != "ADMIN" and order.supervisor_id != actor.id:
        raise ValueError("Only the assigned supervisor can verify this order")
    order.notes = f"{order.notes or ''}\nVerification: {comments}".strip()
    if not approved:
        order.rejection_reason = comments or "Supervisor rejected completion"
    result = _transition(db, order, "VERIFIED" if approved else "REJECTED", actor)
    if order.assigned_crew_id:
        create_notification(db, user_id=order.assigned_crew_id, notif_type="WORK_ORDER_UPDATED", title="Work order verified" if approved else "Work order rejected", message=f"{order.work_order_number} was {'verified' if approved else 'rejected'}.", payload={"work_order_id": order.id, "status": order.status})
    return result
