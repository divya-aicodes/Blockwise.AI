"""Stage 3 deterministic digital-twin and feedback endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.app.schemas import (
    FeedbackStatsResponse,
    SimulatePlanRequest,
    SimulationResponse,
)
from backend.app.simulation.conflict_detector import LOCAL_TIMEZONE
from backend.app.simulation.scenario_runner import run_scenario
from backend.app.auth.service import admin_or_anonymous


router = APIRouter(tags=["simulation"])


@router.post("/simulate-plan", response_model=SimulationResponse)
def simulate_stored_plan(
    payload: SimulatePlanRequest, request: Request,
    _: object = Depends(admin_or_anonymous),
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
