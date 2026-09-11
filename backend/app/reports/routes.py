"""Compact, supervisor-scoped operational reports using SQL aggregates."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from backend.app.auth.service import require_roles
from backend.app.db.base import get_db
from backend.app.db.models import Checklist, Crew, WorkOrder

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/planned-vs-actual")
def planned_vs_actual(_: Crew = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(select(WorkOrder.work_order_number, WorkOrder.estimated_duration_min, WorkOrder.actual_duration_min, WorkOrder.variance_minutes, WorkOrder.status).where(WorkOrder.actual_duration_min.is_not(None)).order_by(WorkOrder.updated_at.desc()).limit(500)).all()
    return [{"work_order_number": number, "planned_minutes": planned, "actual_minutes": actual, "variance_minutes": variance, "status": status} for number, planned, actual, variance, status in rows]


@router.get("/crew-utilization")
def crew_utilization(_: Crew = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(select(WorkOrder.assigned_crew_id, func.count(WorkOrder.id), func.coalesce(func.sum(WorkOrder.actual_duration_min), 0), func.coalesce(func.sum(WorkOrder.overtime_minutes), 0)).where(WorkOrder.assigned_crew_id.is_not(None)).group_by(WorkOrder.assigned_crew_id)).all()
    return [{"crew_id": crew_id, "work_orders": count, "worked_minutes": int(minutes or 0), "overtime_minutes": int(overtime or 0)} for crew_id, count, minutes, overtime in rows]


@router.get("/completion-rate")
def completion_rate(_: Crew = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)) -> dict:
    total, completed, verified = db.execute(select(func.count(WorkOrder.id), func.sum(case((WorkOrder.status.in_(("COMPLETED", "VERIFIED")), 1), else_=0)), func.sum(case((WorkOrder.status == "VERIFIED", 1), else_=0)))).one()
    return {"total": int(total or 0), "completed": int(completed or 0), "verified": int(verified or 0), "completion_rate": round((int(completed or 0) / total) * 100, 2) if total else 0}


@router.get("/safety-compliance")
def safety_compliance(_: Crew = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)) -> dict:
    total, signed = db.execute(select(func.count(Checklist.id), func.sum(case((Checklist.is_mandatory.is_(True) & Checklist.signed_at.is_not(None), 1), else_=0))).where(Checklist.is_mandatory.is_(True))).one()
    return {"mandatory_checklists": int(total or 0), "signed_checklists": int(signed or 0), "compliance_rate": round((int(signed or 0) / total) * 100, 2) if total else 100}


@router.get("/cost-analysis")
def cost_analysis(_: Crew = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)) -> dict:
    material, equipment = db.execute(select(func.coalesce(func.sum(WorkOrder.material_cost), 0), func.coalesce(func.sum(WorkOrder.equipment_cost), 0))).one()
    return {"material_cost": float(material or 0), "equipment_cost": float(equipment or 0), "total_cost": float(material or 0) + float(equipment or 0)}
