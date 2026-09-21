"""Execution readiness checks shared by work orders, planning and simulation."""
from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import Checklist, Crew, WorkOrder

EXECUTION_MODES = {
    "DEPARTMENTAL", "WORKS_CONTRACT", "AMC_CAMC", "OEM_AUTHORIZED", "EMERGENCY"
}


def _shift_covers(start: datetime | None, end: datetime | None, shift_start: time, shift_end: time) -> bool:
    if start is None or end is None:
        return False
    shift_open = datetime.combine(start.date(), shift_start, tzinfo=start.tzinfo)
    shift_close = datetime.combine(start.date(), shift_end, tzinfo=start.tzinfo)
    if shift_end <= shift_start:
        shift_close += timedelta(days=1)
        if start < shift_open:
            shift_open -= timedelta(days=1)
            shift_close -= timedelta(days=1)
    return shift_open <= start and end <= shift_close


def latest_decision_record(
    records: list[dict[str, Any]], plan_id: str | None, maintenance_id: str | None
) -> dict[str, Any] | None:
    """Return the latest human decision for this exact plan/maintenance pair."""
    for record in reversed(records):
        if (
            record.get("plan_id") == plan_id
            and record.get("maintenance_id") == maintenance_id
        ):
            return record
    return None


def latest_decision_status(
    records: list[dict[str, Any]], plan_id: str | None, maintenance_id: str | None
) -> str:
    record = latest_decision_record(records, plan_id, maintenance_id)
    return str(record.get("decision") or "NOT_REVIEWED") if record else "NOT_REVIEWED"


def _mode_reference(order: WorkOrder) -> tuple[str | None, str | None]:
    if order.execution_mode == "WORKS_CONTRACT":
        return "WORKS_CONTRACT", order.contract_id
    if order.execution_mode == "AMC_CAMC":
        return "AMC_CAMC", order.amc_id
    if order.execution_mode == "OEM_AUTHORIZED":
        return "OEM_AUTHORIZED", order.oem_service_id
    return None, None


def validate_execution_readiness(
    db: Session,
    order: WorkOrder,
    *,
    plan: Mapping[str, Any] | None = None,
    approved: bool = False,
) -> dict[str, Any]:
    """Return evidence-backed readiness; missing required data never passes silently."""
    reasons: list[str] = []
    conflicts: list[str] = []
    crew = db.get(Crew, order.assigned_crew_id) if order.assigned_crew_id else None

    if order.execution_mode not in EXECUTION_MODES:
        conflicts.append("Unsupported execution mode")
    if not approved:
        conflicts.append("Plan has not been approved")
    if not plan or str(plan.get("maintenance_id")) != str(order.maintenance_id):
        conflicts.append("Approved plan and maintenance IDs do not match")
    elif int(plan.get("safety_conflicts", 0)) != 0:
        conflicts.append("Plan has unresolved safety conflicts")
    else:
        reasons.append("Selected plan has zero unresolved safety conflicts")

    manpower_available = crew is not None
    if crew is None:
        conflicts.append("No crew is assigned")
    else:
        skills = {str(crew.primary_skill).upper()}
        skills.update(str(item).upper() for item in (crew.secondary_skills or []))
        if not crew.is_active:
            manpower_available = False
            conflicts.append("Assigned crew account is inactive")
        if str(crew.availability).upper() not in {"AVAILABLE", "LIMITED"}:
            manpower_available = False
            conflicts.append("Assigned crew is unavailable")
        if str(order.required_skill).upper() not in skills:
            manpower_available = False
            conflicts.append("Assigned crew does not have the required skill")
        else:
            reasons.append("Assigned crew has the required skill")
        if not _shift_covers(order.planned_start, order.planned_end, crew.shift_start, crew.shift_end):
            manpower_available = False
            conflicts.append("Assigned crew shift does not cover the maintenance window")
        else:
            reasons.append("Assigned crew shift covers the maintenance window")

        provider_type, provider_id = _mode_reference(order)
        if provider_type:
            if not provider_id:
                manpower_available = False
                conflicts.append(f"{provider_type} reference is missing")
            elif crew.provider_type != provider_type or crew.provider_id != provider_id:
                manpower_available = False
                conflicts.append("Assigned crew is not affiliated with the selected provider")
            else:
                reasons.append("Assigned crew matches the selected service provider")
        elif order.execution_mode == "DEPARTMENTAL" and order.department_id:
            if crew.department_id != order.department_id:
                manpower_available = False
                conflicts.append("Assigned crew is not part of the selected department")
            else:
                reasons.append("Assigned crew matches the selected department")

    safety_checklist = db.scalar(
        select(Checklist).where(Checklist.work_order_id == order.id, Checklist.type == "SAFETY")
    )
    if safety_checklist is None or not safety_checklist.is_mandatory:
        conflicts.append("Mandatory safety checklist is missing")
    else:
        reasons.append("Mandatory safety checklist is available")

    evidence = order.evidence or {}
    required_manpower = evidence.get("required_manpower")
    if required_manpower not in (None, 1):
        manpower_available = False
        conflicts.append("Required manpower capacity cannot be validated from assigned-user records")
    required_equipment = list(evidence.get("required_equipment") or [])
    required_materials = list(evidence.get("required_materials") or [])
    equipment_available = not required_equipment or evidence.get("equipment_available") is True
    materials_available = not required_materials or evidence.get("materials_available") is True
    if required_equipment and not equipment_available:
        conflicts.append("Required equipment availability is not confirmed")
    elif not required_equipment:
        reasons.append("No equipment requirement is recorded")
    if required_materials and not materials_available:
        conflicts.append("Required material availability is not confirmed")
    elif not required_materials:
        reasons.append("No material requirement is recorded")

    resource_conflict = bool(conflicts)
    return {
        "manpower_available": manpower_available,
        "required_manpower": required_manpower,
        "assigned_manpower": 1 if crew else 0,
        "equipment_available": equipment_available,
        "required_equipment": required_equipment,
        "materials_available": materials_available,
        "required_materials": required_materials,
        "resource_conflict": resource_conflict,
        "resource_conflicts": conflicts,
        "resource_reasons": [*reasons, *conflicts],
        "validation_status": "READY" if not resource_conflict else "NOT_READY",
        "executable": not resource_conflict,
    }
