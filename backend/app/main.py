"""FastAPI application with validated input and preloaded read-only services."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date as Date
import os
from pathlib import Path
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import (
    DATA_DIR,
    DURATION_MODEL_PATH,
    GRAPH_PATH,
    MAINTENANCE_REQUESTS_PATH,
    FEEDBACK_PATH,
    PLAN_STORE_PATH,
    RISK_MODEL_PATH,
    TRAFFIC_PROFILE_PATH,
)
from backend.app.graph.railway_graph import RailwayGraph
from backend.app.maintenance_repository import MaintenanceRepository
from backend.app.plan_repository import PlanRepository
from backend.app.ml.duration_model import (
    load_duration_model,
    predict_maintenance_duration,
)
from backend.app.ml.risk_model import load_risk_model, predict_asset_risk
from backend.app.ml.traffic_model import load_traffic_profile
from backend.app.repository import CsvRepository
from backend.app.routes.optimize import router as optimize_router
from backend.app.routes.simulation import router as simulation_router
from backend.app.routes.decisions import DecisionStore, router as decisions_router
from backend.app.routes.planning import router as planning_router
from backend.app.auth.routes import router as auth_router
from backend.app.work_orders.routes import router as work_orders_router
from backend.app.checklists.routes import router as checklists_router
from backend.app.notifications.routes import router as notifications_router
from backend.app.reports.routes import router as reports_router
from backend.app.schemas import (
    AssetRecord,
    AssetRiskRequest,
    AssetRiskResponse,
    DurationRequest,
    DurationResponse,
    HealthResponse,
    SectionId,
    TrafficResponse,
    TrainRecord,
)
from backend.app.simulation.feedback_store import FeedbackStore
from backend.app.db.base import init_db
from backend.app.auth.service import admin_or_anonymous


def create_application(
    *,
    data_dir: str | Path = DATA_DIR,
    risk_model_path: str | Path = RISK_MODEL_PATH,
    duration_model_path: str | Path = DURATION_MODEL_PATH,
    traffic_profile_path: str | Path = TRAFFIC_PROFILE_PATH,
    graph_path: str | Path = GRAPH_PATH,
    maintenance_requests_path: str | Path | None = None,
    plan_store_path: str | Path | None = None,
    feedback_path: str | Path | None = None,
) -> FastAPI:
    """Create an independently configurable application for production and tests."""

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        try:
            init_db()
            application.state.repository = CsvRepository.from_data_dir(data_dir)
            application.state.graph = RailwayGraph.load_graph(graph_path)
            application.state.risk_model = load_risk_model(risk_model_path)
            application.state.duration_model = load_duration_model(duration_model_path)
            application.state.traffic_profile = load_traffic_profile(traffic_profile_path)
            resolved_maintenance_path = (
                Path(maintenance_requests_path)
                if maintenance_requests_path is not None
                else Path(data_dir) / MAINTENANCE_REQUESTS_PATH.name
            )
            application.state.maintenance_repository = MaintenanceRepository(
                resolved_maintenance_path
            )
            storage_directory = resolved_maintenance_path.parent
            resolved_plan_path = (
                Path(plan_store_path)
                if plan_store_path is not None
                else storage_directory / PLAN_STORE_PATH.name
            )
            resolved_feedback_path = (
                Path(feedback_path)
                if feedback_path is not None
                else storage_directory / FEEDBACK_PATH.name
            )
            application.state.plan_repository = PlanRepository(resolved_plan_path)
            application.state.feedback_store = FeedbackStore(resolved_feedback_path)
            application.state.decision_store = DecisionStore(storage_directory / "plan_decisions.json")
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise RuntimeError(
                "Application artifacts are unavailable or invalid; run the pipeline first"
            ) from exc
        yield

    application = FastAPI(
        title="BLOCKWISE — Railway Maintenance Decision-Support Backend",
        version="4.0.0",
        description=(
            "Stage 1 synthetic data and prediction APIs with Stage 2 conflict "
            "detection and planning, Stage 3 simulation, and Stage 4 human decisions."
        ),
        lifespan=lifespan,
    )
    cors_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(",") if origin.strip()]
    application.add_middleware(CORSMiddleware, allow_origins=cors_origins, allow_credentials=True, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Authorization", "Content-Type"])

    @application.get("/assets", response_model=list[AssetRecord], tags=["data"])
    def list_assets(
        request: Request,
        _: object = Depends(admin_or_anonymous),
    ) -> list[dict[str, object]]:
        repository: CsvRepository = request.app.state.repository
        return repository.list_assets()

    @application.post("/data/refresh", tags=["data"])
    def refresh_operational_datasets(
        request: Request,
        _: object = Depends(admin_or_anonymous),
    ) -> dict[str, object]:
        """Atomically reload every file-backed source used by the application.

        Database-backed identity, work-order, checklist and notification data is
        already queried live and therefore does not require a reload.
        """
        resolved_maintenance_path = (
            Path(maintenance_requests_path)
            if maintenance_requests_path is not None
            else Path(data_dir) / MAINTENANCE_REQUESTS_PATH.name
        )
        storage_directory = resolved_maintenance_path.parent
        resolved_plan_path = (
            Path(plan_store_path)
            if plan_store_path is not None
            else storage_directory / PLAN_STORE_PATH.name
        )
        resolved_feedback_path = (
            Path(feedback_path)
            if feedback_path is not None
            else storage_directory / FEEDBACK_PATH.name
        )
        refreshed_repository = CsvRepository.from_data_dir(data_dir)
        refreshed_graph = RailwayGraph.load_graph(graph_path)
        refreshed_traffic = load_traffic_profile(traffic_profile_path)
        refreshed_maintenance = MaintenanceRepository(resolved_maintenance_path)
        refreshed_plans = PlanRepository(resolved_plan_path)
        refreshed_feedback = FeedbackStore(resolved_feedback_path)
        refreshed_decisions = DecisionStore(storage_directory / "plan_decisions.json")
        request.app.state.repository = refreshed_repository
        request.app.state.graph = refreshed_graph
        request.app.state.traffic_profile = refreshed_traffic
        request.app.state.maintenance_repository = refreshed_maintenance
        request.app.state.plan_repository = refreshed_plans
        request.app.state.feedback_store = refreshed_feedback
        request.app.state.decision_store = refreshed_decisions
        return {
            "status": "refreshed",
            "datasets": {
                "assets": len(refreshed_repository.assets),
                "train_movements": len(refreshed_repository.trains),
                "crew_roster": len(refreshed_repository.crews),
                "maintenance_history": len(refreshed_repository.maintenance_jobs),
                "weather_observations": len(refreshed_repository.weather),
                "timetable_services": len(refreshed_repository.timetable),
                "corridor_graph": len(refreshed_graph.get_all_sections()),
                "traffic_profile": "loaded",
                "maintenance_requirements": len(refreshed_maintenance),
                "optimization_plans": len(refreshed_plans),
                "simulation_feedback": len(refreshed_feedback),
                "plan_decisions": len(refreshed_decisions.records),
            },
        }

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    def health(request: Request) -> HealthResponse:
        repository: CsvRepository = request.app.state.repository
        return HealthResponse(
            status="ready",
            assets_loaded=len(repository.assets),
            train_movements_loaded=len(repository.trains),
            graph_loaded=request.app.state.graph is not None,
            risk_model_loaded=request.app.state.risk_model is not None,
            duration_model_loaded=request.app.state.duration_model is not None,
            traffic_profile_loaded=request.app.state.traffic_profile is not None,
            maintenance_repository_loaded=(
                request.app.state.maintenance_repository is not None
            ),
            maintenance_requirements=len(request.app.state.maintenance_repository),
            plan_repository_loaded=request.app.state.plan_repository is not None,
            plans_stored=len(request.app.state.plan_repository),
            feedback_store_loaded=request.app.state.feedback_store is not None,
            feedback_rows=len(request.app.state.feedback_store),
        )

    @application.get("/trains", response_model=list[TrainRecord], tags=["data"])
    def list_trains(
        request: Request,
        section: SectionId | None = Query(default=None),
        date: Date | None = Query(default=None),
        train_id: str | None = Query(default=None, min_length=5, max_length=32),
        _: object = Depends(admin_or_anonymous),
    ) -> list[dict[str, object]]:
        repository: CsvRepository = request.app.state.repository
        return repository.query_trains(
            section=section.value if section else None,
            movement_date=date.isoformat() if date else None,
            train_id=train_id,
        )

    @application.post(
        "/predict-risk", response_model=AssetRiskResponse, tags=["prediction"]
    )
    def predict_risk(
        payload: AssetRiskRequest,
        request: Request,
        _: object = Depends(admin_or_anonymous),
    ) -> AssetRiskResponse:
        try:
            risk_level, probabilities = predict_asset_risk(
                payload.model_dump(mode="json"), model=request.app.state.risk_model
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return AssetRiskResponse(
            risk_level=risk_level,
            probabilities=probabilities,
        )

    @application.post(
        "/predict-duration", response_model=DurationResponse, tags=["prediction"]
    )
    def predict_duration(
        payload: DurationRequest,
        request: Request,
        _: object = Depends(admin_or_anonymous),
    ) -> DurationResponse:
        try:
            predicted_duration = predict_maintenance_duration(
                payload.model_dump(mode="json"),
                model=request.app.state.duration_model,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return DurationResponse(predicted_duration_min=predicted_duration)

    @application.get(
        "/traffic/{section}", response_model=TrafficResponse, tags=["statistics"]
    )
    def traffic(
        section: SectionId,
        request: Request,
        hour: int = Query(ge=0, le=23),
        weekday: int = Query(ge=0, le=6),
        _: object = Depends(admin_or_anonymous),
    ) -> TrafficResponse:
        expected = request.app.state.traffic_profile.get_expected_traffic(
            section.value, hour, weekday
        )
        return TrafficResponse(
            section_id=section,
            hour=hour,
            weekday=weekday,
            expected_trains_per_hour=expected,
        )

    @application.get("/corridor", tags=["data"])
    def corridor_data(
        request: Request,
        _: object = Depends(admin_or_anonymous),
    ) -> dict[str, object]:
        graph: RailwayGraph = request.app.state.graph
        return {
            "sections": graph.get_all_sections(),
            "stations": [
                {"code": code, **dict(attrs)}
                for code, attrs in graph.graph.nodes(data=True)
            ],
        }

    @application.get("/crews", tags=["data"])
    def list_crews(
        request: Request,
        _: object = Depends(admin_or_anonymous),
    ) -> list[dict[str, object]]:
        repository: CsvRepository = request.app.state.repository
        return repository.list_crews()

    @application.get("/timetable", tags=["data"])
    def list_timetable(
        request: Request,
        _: object = Depends(admin_or_anonymous),
    ) -> list[dict[str, object]]:
        repository: CsvRepository = request.app.state.repository
        return [dict(row) for row in repository.timetable]

    @application.get("/weather", tags=["data"])
    def list_weather(
        request: Request,
        _: object = Depends(admin_or_anonymous),
    ) -> list[dict[str, object]]:
        repository: CsvRepository = request.app.state.repository
        return [dict(row) for row in repository.weather]

    @application.get("/maintenance-history", tags=["data"])
    def list_maintenance_history(
        request: Request,
        _: object = Depends(admin_or_anonymous),
    ) -> list[dict[str, object]]:
        repository: CsvRepository = request.app.state.repository
        return [dict(row) for row in repository.maintenance_jobs]

    application.include_router(optimize_router)
    application.include_router(simulation_router)
    application.include_router(decisions_router)
    application.include_router(planning_router)
    application.include_router(auth_router)
    application.include_router(work_orders_router)
    application.include_router(checklists_router)
    application.include_router(notifications_router)
    application.include_router(reports_router)
    return application


app = create_application()
