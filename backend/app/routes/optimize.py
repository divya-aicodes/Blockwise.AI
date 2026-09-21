"""Maintenance requirement, conflict, and optimization endpoints."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.app.maintenance_repository import MaintenanceRepository
from backend.app.ml.duration_model import predict_maintenance_duration
from backend.app.optimization.scheduler import (
    ExistingMaintenanceWindow,
    JobSpec,
    OptimizationContext,
    generate_maintenance_alternatives,
)
from backend.app.optimization.scoring import rank_plans
from backend.app.repository import CsvRepository
from backend.app.schemas import (
    AlternativesResponse,
    ConflictResponse,
    CreateMaintenanceRequest,
    DetectConflictsRequest,
    GenerateAlternativesRequest,
    MaintenanceRecord,
)
from backend.app.simulation.conflict_detector import (
    LOCAL_TIMEZONE,
    detect_conflicts,
    require_timezone,
)
from backend.app.auth.service import admin_or_anonymous


router = APIRouter()


def _crew_has_skill(crew: dict[str, object], required_skill: str) -> bool:
    skills = {str(crew.get("primary_skill", "")).upper()}
    skills.update(
        skill.strip().upper()
        for skill in str(crew.get("secondary_skills", "")).split("|")
        if skill.strip()
    )
    return required_skill.upper() in skills


def _maintenance_or_404(request: Request, maintenance_id: str) -> dict[str, object]:
    repository: MaintenanceRepository = request.app.state.maintenance_repository
    record = repository.get(maintenance_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Maintenance requirement not found")
    return record


@router.post(
    "/create-maintenance",
    response_model=MaintenanceRecord,
    status_code=status.HTTP_201_CREATED,
    tags=["optimization"],
)
def create_maintenance(
    payload: CreateMaintenanceRequest, request: Request,
    _: object = Depends(admin_or_anonymous),
) -> dict[str, object]:
    data: CsvRepository = request.app.state.repository
    asset = data.get_asset(payload.asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    required_skill = str(asset["asset_type"])
    eligible_sizes = [
        int(crew["crew_size"])
        for crew in data.crews
        if str(crew.get("availability")) in {"AVAILABLE", "LIMITED"}
        and _crew_has_skill(crew, required_skill)
    ]
    if not eligible_sizes:
        raise HTTPException(
            status_code=409,
            detail=f"No available crew has the required skill: {required_skill}",
        )

    if payload.minimum_duration_min is None:
        historical_duration = data.historical_duration(payload.job_type.value)
        representative_crew_size = round(sum(eligible_sizes) / len(eligible_sizes))
        predicted_duration = predict_maintenance_duration(
            {
                "job_type": payload.job_type.value,
                "asset_condition": float(asset["condition_score"]),
                "crew_size": representative_crew_size,
                "weather_condition": str(asset["weather_condition"]),
                "historical_duration": historical_duration,
            },
            model=request.app.state.duration_model,
        )
        minimum_duration = math.ceil(predicted_duration)
    else:
        minimum_duration = payload.minimum_duration_min

    horizon_min = (
        payload.latest_end_time - payload.earliest_start_time
    ).total_seconds() / 60
    if minimum_duration > horizon_min:
        raise HTTPException(
            status_code=422,
            detail="Planning horizon is shorter than the required maintenance duration",
        )
    repository: MaintenanceRepository = request.app.state.maintenance_repository
    return repository.create(
        asset_id=payload.asset_id,
        section_id=str(asset["section_id"]),
        required_skill=required_skill,
        job_type=payload.job_type.value,
        urgency=payload.urgency.value,
        risk_level=str(asset["risk_level"]),
        condition_score=float(asset["condition_score"]),
        minimum_duration_min=minimum_duration,
        preferred_start_time=payload.preferred_start_time,
        earliest_start_time=payload.earliest_start_time,
        latest_end_time=payload.latest_end_time,
        created_at=datetime.now(LOCAL_TIMEZONE),
        execution_mode=payload.execution_mode.value,
        department_id=payload.department_id,
        contract_id=payload.contract_id,
        amc_id=payload.amc_id,
        oem_service_id=payload.oem_service_id,
    )


@router.get(
    "/maintenance-requirements/{maintenance_id}",
    response_model=MaintenanceRecord,
    tags=["optimization"],
)
def get_maintenance_requirement(
    maintenance_id: str, request: Request,
    _: object = Depends(admin_or_anonymous),
) -> dict[str, object]:
    return _maintenance_or_404(request, maintenance_id)


@router.post(
    "/detect-conflicts", response_model=ConflictResponse, tags=["optimization"]
)
def detect_maintenance_conflicts(
    payload: DetectConflictsRequest, request: Request,
    _: object = Depends(admin_or_anonymous),
) -> ConflictResponse:
    maintenance = _maintenance_or_404(request, payload.maintenance_id)
    if payload.section_id.value != str(maintenance["section_id"]):
        raise HTTPException(
            status_code=422,
            detail="section_id does not match the maintenance asset section",
        )
    data: CsvRepository = request.app.state.repository
    movements = data.relevant_train_movements(
        section=payload.section_id.value,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )
    conflicts = detect_conflicts(
        {
            "maintenance_id": payload.maintenance_id,
            "section_id": payload.section_id.value,
            "start_time": payload.start_time,
            "end_time": payload.end_time,
        },
        movements,
    )
    return ConflictResponse(
        maintenance_id=payload.maintenance_id,
        section_id=payload.section_id,
        has_conflicts=bool(conflicts),
        conflict_count=len(conflicts),
        conflicts=[conflict.to_dict() for conflict in conflicts],
    )


@router.post(
    "/generate-alternatives",
    response_model=AlternativesResponse,
    tags=["optimization"],
)
def generate_alternatives(
    payload: GenerateAlternativesRequest, request: Request,
    _: object = Depends(admin_or_anonymous),
) -> AlternativesResponse:
    maintenance = _maintenance_or_404(request, payload.maintenance_id)
    earliest = require_timezone(
        datetime.fromisoformat(str(maintenance["earliest_start_time"])),
        "earliest_start_time",
    )
    preferred = require_timezone(
        datetime.fromisoformat(str(maintenance["preferred_start_time"])),
        "preferred_start_time",
    )
    latest = require_timezone(
        datetime.fromisoformat(str(maintenance["latest_end_time"])),
        "latest_end_time",
    )
    data: CsvRepository = request.app.state.repository
    section_id = str(maintenance["section_id"])
    movements = data.relevant_train_movements(
        section=section_id, start_time=earliest, end_time=latest
    )

    traffic_by_hour: dict[tuple[int, int], float] = {}
    cursor = earliest.replace(minute=0, second=0, microsecond=0)
    while cursor < latest:
        key = (cursor.weekday(), cursor.hour)
        traffic_by_hour[key] = (
            request.app.state.traffic_profile.get_expected_traffic(
                section_id, cursor.hour, cursor.weekday()
            )
        )
        cursor += timedelta(hours=1)

    existing_windows = tuple(
        ExistingMaintenanceWindow(
            maintenance_id=window.maintenance_id,
            section_id=window.section_id.value,
            start_time=window.start_time,
            end_time=window.end_time,
            assigned_crew_id=window.assigned_crew_id,
        )
        for window in payload.existing_windows
    )
    job_spec = JobSpec(
        maintenance_id=str(maintenance["maintenance_id"]),
        asset_id=str(maintenance["asset_id"]),
        section_id=section_id,
        job_type=str(maintenance["job_type"]),
        urgency=str(maintenance["urgency"]),
        required_skill=str(maintenance["required_skill"]),
        minimum_duration_min=int(maintenance["minimum_duration_min"]),
        preferred_start_time=preferred,
        earliest_start_time=earliest,
        latest_end_time=latest,
        risk_level=str(maintenance["risk_level"]),
        condition_score=float(maintenance["condition_score"]),
    )
    context = OptimizationContext(
        train_movements=tuple(movements),
        crews=tuple(data.list_crews()),
        traffic_by_hour=traffic_by_hour,
        existing_windows=existing_windows,
        max_train_delay_min=payload.max_train_delay_min,
        solver_timeout_seconds=payload.solver_timeout_seconds,
    )
    candidates = generate_maintenance_alternatives(
        job_spec, context, top_n=payload.top_n
    )
    ranked = rank_plans(candidates)
    ranked = request.app.state.plan_repository.save_many(ranked)
    return AlternativesResponse(
        maintenance_id=payload.maintenance_id,
        alternatives_generated=len(ranked),
        alternatives=ranked,
        status="FEASIBLE_PLANS" if ranked else "NO_FEASIBLE_PLAN",
    )
