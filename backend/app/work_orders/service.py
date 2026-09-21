"""Transactional work-order state machine."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import AuditLog, Checklist, Crew, WorkOrder
from backend.app.notifications.service import create_targeted_notifications
from backend.app.work_orders.readiness import EXECUTION_MODES, validate_execution_readiness

TRANSITIONS = {
    "DRAFT": {"ASSIGNED"}, "ASSIGNED": {"ACKNOWLEDGED"},
    "ACKNOWLEDGED": {"IN_PROGRESS"}, "IN_PROGRESS": {"PAUSED", "COMPLETED"},
    "PAUSED": {"IN_PROGRESS"}, "COMPLETED": {"VERIFIED", "REJECTED"},
}


def _audit(db: Session, actor: Crew, action: str, order: WorkOrder, before: str | None = None) -> None:
    db.add(AuditLog(user_id=actor.id, action=action, entity_type="WORK_ORDER", entity_id=order.id, before={"status": before} if before else None, after={"status": order.status, "work_order_number": order.work_order_number}))


def serialize(order: WorkOrder) -> dict:
    return {"id": order.id, "work_order_number": order.work_order_number, "plan_id": order.plan_id, "maintenance_id": order.maintenance_id, "title": order.title, "section_id": order.section_id, "asset_id": order.asset_id, "asset_type": order.asset_type, "required_skill": order.required_skill, "priority": order.priority, "status": order.status, "execution_mode": order.execution_mode, "department_id": order.department_id, "contract_id": order.contract_id, "amc_id": order.amc_id, "oem_service_id": order.oem_service_id, "assigned_crew_id": order.assigned_crew_id, "supervisor_id": order.supervisor_id, "planned_start": order.planned_start.isoformat() if order.planned_start else None, "planned_end": order.planned_end.isoformat() if order.planned_end else None, "actual_start": order.actual_start.isoformat() if order.actual_start else None, "actual_end": order.actual_end.isoformat() if order.actual_end else None, "estimated_duration_min": order.estimated_duration_min, "actual_duration_min": order.actual_duration_min, "variance_minutes": order.variance_minutes, "overtime_minutes": order.overtime_minutes, "gps_start": order.gps_start, "gps_end": order.gps_end, "material_cost": float(order.material_cost or 0), "equipment_cost": float(order.equipment_cost or 0), "notes": order.notes, "rejection_reason": order.rejection_reason}


def calculate_metrics(order: WorkOrder) -> dict:
    planned = int(order.estimated_duration_min or 0)
    actual = int(order.actual_duration_min or 0)
    variance = actual - planned if order.actual_duration_min is not None else None
    return {"variance_minutes": variance, "overtime_minutes": max(0, variance or 0), "total_cost": float(order.material_cost or 0) + float(order.equipment_cost or 0)}


def can_access_work_order(order: WorkOrder, actor: Crew) -> bool:
    """Authorize only administrators or users related to the work order."""
    if actor.role.upper() == "ADMIN":
        return True
    if actor.id in {order.assigned_crew_id, order.supervisor_id}:
        return True
    if actor.provider_type and actor.provider_id:
        reference = {
            "WORKS_CONTRACT": order.contract_id,
            "AMC_CAMC": order.amc_id,
            "OEM_AUTHORIZED": order.oem_service_id,
        }.get(actor.provider_type)
        if order.execution_mode == actor.provider_type and reference == actor.provider_id:
            return True
    return bool(
        actor.role.upper() == "SUPERVISOR"
        and actor.department_id
        and order.execution_mode == "DEPARTMENTAL"
        and order.department_id == actor.department_id
    )


def create_from_plan(db: Session, *, plan: dict, requirement: dict, actor: Crew, execution: dict | None = None) -> WorkOrder:
    if plan.get("maintenance_id") != requirement.get("maintenance_id"):
        raise ValueError("Plan and maintenance requirement do not match")
    existing = db.scalar(select(WorkOrder).where(WorkOrder.plan_id == plan["plan_id"]))
    if existing:
        requested_mode = str((execution or {}).get("execution_mode") or requirement.get("execution_mode") or "DEPARTMENTAL")
        if existing.execution_mode != requested_mode:
            raise ValueError("Execution mode cannot be changed after work-order creation")
        requested_reference = {
            "DEPARTMENTAL": (execution or {}).get("department_id"),
            "WORKS_CONTRACT": (execution or {}).get("contract_id"),
            "AMC_CAMC": (execution or {}).get("amc_id"),
            "OEM_AUTHORIZED": (execution or {}).get("oem_service_id"),
            "EMERGENCY": None,
        }.get(requested_mode)
        stored_reference = {
            "DEPARTMENTAL": existing.department_id,
            "WORKS_CONTRACT": existing.contract_id,
            "AMC_CAMC": existing.amc_id,
            "OEM_AUTHORIZED": existing.oem_service_id,
            "EMERGENCY": None,
        }.get(existing.execution_mode)
        if requested_reference != stored_reference:
            raise ValueError("Execution provider cannot be changed after work-order creation")
        return existing
    window = plan["maintenance_window"]
    urgency = str(requirement.get("urgency", "NORMAL"))
    priority = "EMERGENCY" if urgency == "EMERGENCY" else "HIGH" if urgency == "HIGH" else "MEDIUM"
    execution = execution or {}
    mode = str(execution.get("execution_mode") or requirement.get("execution_mode") or "DEPARTMENTAL")
    if mode not in EXECUTION_MODES:
        raise ValueError("Unsupported execution mode")
    def execution_value(field: str) -> object:
        return execution[field] if field in execution else requirement.get(field)

    order = WorkOrder(work_order_number=f"WO-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}", plan_id=plan["plan_id"], maintenance_id=requirement["maintenance_id"], title=f"Maintenance {requirement.get('asset_id', '')}", description="Approved maintenance work order; execution remains under railway possession controls.", section_id=str(requirement["section_id"]), asset_id=str(requirement.get("asset_id", "")), asset_type=str(requirement.get("asset_type", "")) or None, required_skill=str(requirement.get("required_skill", "TRACK")), priority=priority, status="DRAFT", execution_mode=mode, department_id=execution_value("department_id") or None, contract_id=execution_value("contract_id") or None, amc_id=execution_value("amc_id") or None, oem_service_id=execution_value("oem_service_id") or None, planned_start=datetime.fromisoformat(window["start"]), planned_end=datetime.fromisoformat(window["end"]), estimated_duration_min=int(requirement.get("minimum_duration_min", 1)), created_by=actor.id)
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


def assign(
    db: Session,
    order_id: str,
    crew_employee_id: str,
    supervisor: Crew,
    *,
    plan: dict | None = None,
    approved: bool = False,
) -> WorkOrder:
    order = _get_order(db, order_id)
    crew = db.scalar(select(Crew).where(Crew.employee_id == crew_employee_id, Crew.is_active.is_(True)))
    if not crew:
        raise ValueError("Active crew member not found")
    if crew.primary_skill != order.required_skill and order.required_skill not in (crew.secondary_skills or []):
        raise ValueError("Crew member does not have the required skill")
    if crew.availability not in {"AVAILABLE", "LIMITED"}:
        raise ValueError("Crew member is not available")
    reference = {"WORKS_CONTRACT": order.contract_id, "AMC_CAMC": order.amc_id, "OEM_AUTHORIZED": order.oem_service_id}.get(order.execution_mode)
    if order.execution_mode in {"WORKS_CONTRACT", "AMC_CAMC", "OEM_AUTHORIZED"}:
        if not reference:
            raise ValueError(f"{order.execution_mode} reference is required before assignment")
        if crew.provider_type != order.execution_mode or crew.provider_id != reference:
            raise ValueError("Crew member is not affiliated with the selected service provider")
    if order.execution_mode == "DEPARTMENTAL" and order.department_id and crew.department_id != order.department_id:
        raise ValueError("Crew member is not part of the selected department")
    previous_crew_id = order.assigned_crew_id
    previous_supervisor_id = order.supervisor_id
    order.assigned_crew_id = crew.id
    order.supervisor_id = supervisor.id
    db.flush()
    readiness = validate_execution_readiness(
        db, order, plan=plan, approved=approved
    )
    if not readiness["executable"]:
        order.assigned_crew_id = previous_crew_id
        order.supervisor_id = previous_supervisor_id
        db.flush()
        raise ValueError(
            "Assignment is not execution-ready: "
            + "; ".join(readiness["resource_conflicts"])
        )
    result = _transition(db, order, "ASSIGNED", supervisor)
    create_targeted_notifications(db, work_order=order, event="WORK_ORDER_ASSIGNED", title="New planned work assigned", message=f"{order.work_order_number}: What: {order.title}. Where: {order.section_id} / asset {order.asset_id}. When: {order.planned_start:%d %b %Y, %H:%M}–{order.planned_end:%H:%M}. Priority: {order.priority}. Skill: {order.required_skill}. Plan: {order.plan_id} · Maintenance: {order.maintenance_id}.", next_action="ACKNOWLEDGE_WORK_ORDER", priority="HIGH")
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
    if not checklist or not checklist.is_mandatory:
        raise ValueError("Mandatory safety checklist is missing")
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
        create_targeted_notifications(db, work_order=order, event="WORK_ORDER_COMPLETED", title="Verification required", message=f"{order.work_order_number} is ready for verification.", next_action="VERIFY_WORK_ORDER", priority="HIGH")
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
        create_targeted_notifications(db, work_order=order, event="WORK_ORDER_VERIFIED" if approved else "WORK_ORDER_REJECTED", title="Work order verified" if approved else "Work order rejected", message=f"{order.work_order_number} was {'verified' if approved else 'rejected'}.", next_action="CLOSE_WORK_ORDER" if approved else "REVIEW_REJECTION", priority="HIGH")
    return result
