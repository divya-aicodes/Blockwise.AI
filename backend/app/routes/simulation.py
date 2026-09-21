"""Stage 3 deterministic digital-twin and feedback endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.schemas import (
    FeedbackStatsResponse,
    SimulatePlanRequest,
    SimulationResponse,
)
from backend.app.simulation.conflict_detector import LOCAL_TIMEZONE
from backend.app.simulation.scenario_runner import run_scenario
from backend.app.auth.service import admin_or_anonymous
from backend.app.db.base import get_db
from backend.app.db.models import WorkOrder
from backend.app.work_orders.readiness import (
    latest_decision_record,
    validate_execution_readiness,
)


router = APIRouter(tags=["simulation"])


@router.post("/simulate-plan", response_model=SimulationResponse)
def simulate_stored_plan(
    payload: SimulatePlanRequest, request: Request,
    _: object = Depends(admin_or_anonymous),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    plan = request.app.state.plan_repository.get(payload.plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Optimization plan not found")
    maintenance = request.app.state.maintenance_repository.get(
        str(plan["maintenance_id"])
    )
    if maintenance is None:
        raise HTTPException(
            status_code=409,
            detail="The plan's maintenance requirement is unavailable",
        )
    try:
        result = run_scenario(
            plan,
            payload.simulation_date,
            maintenance_requirement=maintenance,
            repository=request.app.state.repository,
            railway_graph=request.app.state.graph,
            random_seed=payload.random_seed,
        )
        simulated_maintenance = result["maintenance"]
        kpis = result["kpis"]
        request.app.state.feedback_store.record_feedback(
            timestamp=datetime.now(LOCAL_TIMEZONE),
            maintenance_id=str(result["maintenance_id"]),
            plan_id=str(result["plan_id"]),
            section_id=str(result["section_id"]),
            predicted_duration_min=float(
                simulated_maintenance["predicted_duration_min"]
            ),
            simulated_actual_duration_min=float(
                simulated_maintenance["simulated_duration_min"]
            ),
            predicted_total_delay_min=float(plan["total_train_delay_min"]),
            simulated_actual_total_delay_min=float(kpis["total_delay_min"]),
        )

        order = db.scalar(
            select(WorkOrder).where(WorkOrder.plan_id == payload.plan_id)
        )
        decision = latest_decision_record(
            request.app.state.decision_store.records,
            payload.plan_id,
            str(plan["maintenance_id"]),
        )
        approval_status = str(decision.get("decision")) if decision else "NOT_REVIEWED"
        if order:
            resource_validation = validate_execution_readiness(
                db,
                order,
                plan=plan,
                approved=approval_status == "APPROVED",
            )
            execution_mode = order.execution_mode
            assigned_crew_id = order.assigned_crew_id
            supervisor_id = order.supervisor_id
            department_id = order.department_id
            contract_id = order.contract_id
            amc_id = order.amc_id
            oem_service_id = order.oem_service_id
        else:
            approved_execution = decision if approval_status == "APPROVED" else {}
            execution_mode = str(
                approved_execution.get("execution_mode")
                or maintenance.get("execution_mode")
                or "DEPARTMENTAL"
            )
            assigned_crew_id = None
            supervisor_id = None
            department_id = approved_execution.get("department_id") or maintenance.get("department_id") or None
            contract_id = approved_execution.get("contract_id") or maintenance.get("contract_id") or None
            amc_id = approved_execution.get("amc_id") or maintenance.get("amc_id") or None
            oem_service_id = approved_execution.get("oem_service_id") or maintenance.get("oem_service_id") or None
            resource_validation = {
                "manpower_available": False,
                "required_manpower": None,
                "assigned_manpower": 0,
                "equipment_available": False,
                "required_equipment": [],
                "materials_available": False,
                "required_materials": [],
                "resource_conflict": True,
                "resource_conflicts": [
                    "Approved work order has not been created",
                    "No crew is assigned",
                ],
                "resource_reasons": [
                    "Approved work order has not been created",
                    "No crew is assigned",
                ],
                "validation_status": "NOT_READY",
                "executable": False,
            }
        safety_validation = {
            "valid": int(plan.get("safety_conflicts", 0)) == 0
            and int(kpis["conflicts_detected"]) == 0,
            "planned_safety_conflicts": int(plan.get("safety_conflicts", 0)),
            "simulated_safety_conflicts": int(kpis["conflicts_detected"]),
        }
        result["execution_context"] = {
            "execution_mode": execution_mode,
            "assigned_crew_id": assigned_crew_id,
            "supervisor_id": supervisor_id,
            "department_id": department_id,
            "contract_id": contract_id,
            "amc_id": amc_id,
            "oem_service_id": oem_service_id,
            "resource_validation": resource_validation,
            "safety_validation": safety_validation,
            "expected_train_delay_min": int(plan["total_train_delay_min"]),
            "simulated_train_delay_min": int(kpis["total_delay_min"]),
            "executable": bool(
                resource_validation["executable"] and safety_validation["valid"]
            ),
        }
        for event in result["maintenance_events"]:
            event.update(
                {
                    "maintenance_id": str(plan["maintenance_id"]),
                    "plan_id": payload.plan_id,
                    "execution_mode": execution_mode,
                    "assigned_crew_id": assigned_crew_id,
                }
            )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=503, detail="Simulation feedback could not be persisted"
        ) from exc
    return result


@router.get("/feedback-stats", response_model=FeedbackStatsResponse)
def feedback_stats(
    request: Request,
    last_n: int | None = Query(default=None, ge=1, le=10_000),
    _: object = Depends(admin_or_anonymous),
) -> dict[str, object]:
    return request.app.state.feedback_store.get_feedback_stats(last_n=last_n)
