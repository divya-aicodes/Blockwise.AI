"""Strict request and response schemas for both backend stages."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SectionId(str, Enum):
    ndls_re = "SEC-NDLS-RE"
    re_awr = "SEC-RE-AWR"
    awr_bki = "SEC-AWR-BKI"
    bki_jp = "SEC-BKI-JP"


class Criticality(str, Enum):
    low = "LOW"
    medium = "MEDIUM"
    high = "HIGH"
    critical = "CRITICAL"


class WeatherCondition(str, Enum):
    clear = "CLEAR"
    cloudy = "CLOUDY"
    light_rain = "LIGHT_RAIN"
    heavy_rain = "HEAVY_RAIN"
    fog = "FOG"


class JobType(str, Enum):
    inspection = "INSPECTION"
    preventive = "PREVENTIVE"
    corrective = "CORRECTIVE"
    emergency = "EMERGENCY"


class Urgency(str, Enum):
    low = "LOW"
    normal = "NORMAL"
    high = "HIGH"
    emergency = "EMERGENCY"


class ExecutionMode(str, Enum):
    departmental = "DEPARTMENTAL"
    works_contract = "WORKS_CONTRACT"
    amc_camc = "AMC_CAMC"
    oem_authorized = "OEM_AUTHORIZED"
    emergency = "EMERGENCY"


def _aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a UTC offset")
    return value


class AssetRiskRequest(StrictModel):
    age_years: int = Field(ge=0, le=100)
    condition_score: float = Field(ge=0, le=100)
    previous_failures: int = Field(ge=0, le=100)
    days_since_maintenance: int = Field(ge=0, le=3650)
    criticality: Criticality
    weather_condition: WeatherCondition


class AssetRiskResponse(StrictModel):
    risk_level: str
    probabilities: dict[str, float]


class DurationRequest(StrictModel):
    job_type: JobType
    asset_condition: float = Field(ge=0, le=100)
    crew_size: int = Field(ge=1, le=50)
    weather_condition: WeatherCondition
    historical_duration: float = Field(gt=0, le=1440)


class DurationResponse(StrictModel):
    predicted_duration_min: float = Field(gt=0)


class AssetRecord(StrictModel):
    asset_id: str
    asset_type: str
    section_id: SectionId
    age_years: int
    condition_score: float
    previous_failures: int
    days_since_maintenance: int
    criticality: Criticality
    weather_condition: WeatherCondition
    risk_level: str


class TrainRecord(StrictModel):
    train_id: str
    train_name: str
    train_type: str
    section_id: SectionId
    date: str
    scheduled_entry_time: str
    scheduled_exit_time: str
    actual_entry_time: str
    actual_exit_time: str
    delay_min: int = Field(ge=0)
    priority: str


class TrafficResponse(StrictModel):
    section_id: SectionId
    hour: int = Field(ge=0, le=23)
    weekday: int = Field(ge=0, le=6)
    expected_trains_per_hour: float = Field(ge=0)


class HealthResponse(StrictModel):
    status: str
    assets_loaded: int = Field(ge=0)
    train_movements_loaded: int = Field(ge=0)
    graph_loaded: bool
    risk_model_loaded: bool
    duration_model_loaded: bool
    traffic_profile_loaded: bool
    maintenance_repository_loaded: bool
    maintenance_requirements: int = Field(ge=0)
    plan_repository_loaded: bool
    plans_stored: int = Field(ge=0)
    feedback_store_loaded: bool
    feedback_rows: int = Field(ge=0)


class CreateMaintenanceRequest(StrictModel):
    asset_id: str = Field(pattern=r"^AST-\d{2}-\d{2}$")
    job_type: JobType
    urgency: Urgency
    minimum_duration_min: int | None = Field(default=None, gt=0, le=720)
    preferred_start_time: datetime
    earliest_start_time: datetime
    latest_end_time: datetime
    execution_mode: ExecutionMode = ExecutionMode.departmental
    department_id: str | None = Field(default=None, max_length=64)
    contract_id: str | None = Field(default=None, max_length=64)
    amc_id: str | None = Field(default=None, max_length=64)
    oem_service_id: str | None = Field(default=None, max_length=64)

    @field_validator(
        "preferred_start_time", "earliest_start_time", "latest_end_time"
    )
    @classmethod
    def timestamps_have_offsets(cls, value: datetime, info: object) -> datetime:
        return _aware(value, getattr(info, "field_name", "timestamp"))

    @model_validator(mode="after")
    def planning_window_is_valid(self) -> "CreateMaintenanceRequest":
        if not self.earliest_start_time <= self.preferred_start_time < self.latest_end_time:
            raise ValueError(
                "Require earliest_start_time <= preferred_start_time < latest_end_time"
            )
        if self.minimum_duration_min is not None:
            horizon = (
                self.latest_end_time - self.earliest_start_time
            ).total_seconds() / 60
            if horizon < self.minimum_duration_min:
                raise ValueError("Planning horizon is shorter than minimum duration")
        return self


class MaintenanceRecord(StrictModel):
    maintenance_id: str = Field(pattern=r"^M\d{3,}$")
    version: int = Field(ge=1)
    asset_id: str
    section_id: SectionId
    required_skill: str
    job_type: JobType
    urgency: Urgency
    risk_level: str
    condition_score: float = Field(ge=0, le=100)
    minimum_duration_min: int = Field(gt=0)
    preferred_start_time: datetime
    earliest_start_time: datetime
    latest_end_time: datetime
    status: str
    created_at: datetime
    execution_mode: ExecutionMode = ExecutionMode.departmental
    department_id: str | None = None
    contract_id: str | None = None
    amc_id: str | None = None
    oem_service_id: str | None = None


class DetectConflictsRequest(StrictModel):
    maintenance_id: str = Field(pattern=r"^M\d{3,}$")
    section_id: SectionId
    start_time: datetime
    end_time: datetime

    @field_validator("start_time", "end_time")
    @classmethod
    def timestamps_have_offsets(cls, value: datetime, info: object) -> datetime:
        return _aware(value, getattr(info, "field_name", "timestamp"))

    @model_validator(mode="after")
    def end_follows_start(self) -> "DetectConflictsRequest":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self


class ConflictRecord(StrictModel):
    maintenance_id: str
    train_id: str
    section_id: SectionId
    train_entry_time: datetime
    train_exit_time: datetime
    maintenance_start: datetime
    maintenance_end: datetime
    overlap_start: datetime
    overlap_end: datetime
    overlap_duration_min: int = Field(gt=0)
    train_priority: str
    conflict_type: str


class ConflictResponse(StrictModel):
    maintenance_id: str
    section_id: SectionId
    has_conflicts: bool
    conflict_count: int = Field(ge=0)
    conflicts: list[ConflictRecord]


class ExistingWindowRequest(StrictModel):
    maintenance_id: str = Field(min_length=1, max_length=64)
    section_id: SectionId
    start_time: datetime
    end_time: datetime
    assigned_crew_id: str | None = Field(default=None, min_length=1, max_length=32)

    @field_validator("start_time", "end_time")
    @classmethod
    def timestamps_have_offsets(cls, value: datetime, info: object) -> datetime:
        return _aware(value, getattr(info, "field_name", "timestamp"))

    @model_validator(mode="after")
    def end_follows_start(self) -> "ExistingWindowRequest":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self


class GenerateAlternativesRequest(StrictModel):
    maintenance_id: str = Field(pattern=r"^M\d{3,}$")
    top_n: int = Field(default=5, ge=1, le=5)
    max_train_delay_min: int = Field(default=240, ge=0, le=360)
    solver_timeout_seconds: float = Field(default=2.0, gt=0, le=10)
    existing_windows: list[ExistingWindowRequest] = Field(
        default_factory=list, max_length=50
    )


class AffectedTrain(StrictModel):
    train_id: str
    priority: str
    original_entry_time: datetime
    original_exit_time: datetime
    adjusted_entry_time: datetime
    adjusted_exit_time: datetime
    delay_added_min: int = Field(ge=0)


class MaintenanceWindow(StrictModel):
    start: datetime
    end: datetime


class AlternativePlan(StrictModel):
    plan_id: str = Field(pattern=r"^P\d{3,}$")
    maintenance_id: str
    maintenance_window: MaintenanceWindow
    assigned_crew_id: str
    affected_trains: list[AffectedTrain]
    total_train_delay_min: int = Field(ge=0)
    priority_weighted_train_delay_min: int = Field(ge=0)
    maintenance_delay_min: int = Field(ge=0)
    risk_reduction_estimate: float = Field(ge=0, le=100)
    risk_delay_penalty: float = Field(ge=0)
    crew_cost: float = Field(ge=0)
    reroute_available: bool
    safety_conflicts: int = Field(ge=0)
    overall_score: float = Field(ge=0)
    rank: int = Field(ge=1)


class AlternativesResponse(StrictModel):
    maintenance_id: str
    alternatives_generated: int = Field(ge=0)
    alternatives: list[AlternativePlan]
    status: str


class SimulatePlanRequest(StrictModel):
    plan_id: str = Field(pattern=r"^P\d{3,}$")
    simulation_date: date
    random_seed: int = Field(default=42, ge=0, le=2_147_483_647)


class SimulatedSectionEvent(StrictModel):
    train_id: str
    section_id: SectionId
    scheduled_entry_time: datetime
    scheduled_exit_time: datetime
    simulated_entry_time: datetime
    simulated_exit_time: datetime
    planned_delay_min: int = Field(ge=0)
    additional_wait_min: int = Field(ge=0)
    delay_added_min: int = Field(ge=0)
    total_delay_min: int = Field(ge=0)


class SimulatedTrainResult(StrictModel):
    train_id: str
    priority: str
    planned_delay_min: int = Field(ge=0)
    additional_simulation_wait_min: int = Field(ge=0)
    total_delay_min: int = Field(ge=0)
    completion_status: str
    section_events: list[SimulatedSectionEvent]


class SimulationKPIs(StrictModel):
    total_delay_min: int = Field(ge=0)
    max_single_train_delay_min: int = Field(ge=0)
    average_delay_min: float = Field(ge=0)
    affected_trains_count: int = Field(ge=0)
    affected_train_ids: list[str]
    conflicts_detected: int = Field(ge=0)
    maintenance_completed: bool
    maintenance_completion_time: datetime | None
    trains_simulated: int = Field(ge=0)
    maintenance_start_time: datetime | None
    maintenance_end_time: datetime | None
    predicted_maintenance_duration_min: int = Field(gt=0)
    simulated_maintenance_duration_min: int = Field(gt=0)


class SimulatedMaintenance(StrictModel):
    maintenance_id: str
    plan_id: str
    section_id: SectionId
    planned_start: datetime
    planned_end: datetime
    simulated_start: datetime | None
    simulated_end: datetime | None
    predicted_duration_min: int = Field(gt=0)
    simulated_duration_min: int = Field(gt=0)
    duration_variation_min: int
    completion_status: str


class SafetyEvent(StrictModel):
    time_min: float = Field(ge=0)
    section_id: SectionId
    type: str
    train_id: str | None = None


class MaintenanceSimulationEvent(StrictModel):
    event: str
    time_min: float = Field(ge=0)
    section_id: SectionId
    maintenance_id: str | None = None
    plan_id: str | None = None
    execution_mode: ExecutionMode | None = None
    assigned_crew_id: str | None = None


class SimulationExecutionContext(StrictModel):
    execution_mode: ExecutionMode
    assigned_crew_id: str | None = None
    supervisor_id: str | None = None
    department_id: str | None = None
    contract_id: str | None = None
    amc_id: str | None = None
    oem_service_id: str | None = None
    resource_validation: dict[str, object]
    safety_validation: dict[str, object]
    expected_train_delay_min: int = Field(ge=0)
    simulated_train_delay_min: int = Field(ge=0)
    executable: bool


class SimulationResponse(StrictModel):
    plan_id: str
    maintenance_id: str
    section_id: SectionId
    simulation_date: date
    random_seed: int = Field(ge=0)
    kpis: SimulationKPIs
    maintenance: SimulatedMaintenance
    train_results: list[SimulatedTrainResult]
    safety_events: list[SafetyEvent]
    maintenance_events: list[MaintenanceSimulationEvent]
    execution_context: SimulationExecutionContext | None = None


class FeedbackStatsResponse(StrictModel):
    total_simulations: int = Field(ge=0)
    duration_mae_min: float = Field(ge=0)
    delay_mae_min: float = Field(ge=0)
    mean_duration_error_min: float
    mean_delay_error_min: float
    scope: str
    data_source: str
