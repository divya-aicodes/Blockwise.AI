export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type SectionId =
  | "SEC-NDLS-RE"
  | "SEC-RE-AWR"
  | "SEC-AWR-BKI"
  | "SEC-BKI-JP";
export interface Section {
  id: SectionId;
  from: string;
  to: string;
  distance: number;
  start: number;
  end: number;
}
export interface Asset {
  asset_id: string;
  asset_type: string;
  section_id: SectionId;
  age_years: number;
  condition_score: number;
  previous_failures: number;
  days_since_maintenance: number;
  criticality: RiskLevel;
  weather_condition: string;
  risk_level: RiskLevel;
}
export interface RiskPrediction {
  risk_level: RiskLevel;
  probabilities: Record<RiskLevel, number>;
}
export interface Health {
  status: string;
  assets_loaded: number;
  train_movements_loaded: number;
  maintenance_requirements: number;
  plans_stored: number;
  feedback_rows: number;
}
export interface MaintenanceInput {
  asset_id: string;
  job_type: string;
  urgency: string;
  preferred_start_time: string;
  earliest_start_time: string;
  latest_end_time: string;
  minimum_duration_min?: number;
}
export interface MaintenanceRequirement extends MaintenanceInput {
  maintenance_id: string;
  version: number;
  section_id: SectionId;
  required_skill: string;
  risk_level: RiskLevel;
  condition_score: number;
  minimum_duration_min: number;
  status: string;
  created_at: string;
}
export interface Conflict {
  maintenance_id: string;
  train_id: string;
  section_id: SectionId;
  train_entry_time: string;
  train_exit_time: string;
  maintenance_start: string;
  maintenance_end: string;
  overlap_start: string;
  overlap_end: string;
  overlap_duration_min: number;
  train_priority: string;
  conflict_type: string;
}
export interface ConflictResponse {
  maintenance_id: string;
  section_id: SectionId;
  has_conflicts: boolean;
  conflict_count: number;
  conflicts: Conflict[];
}
export interface TrainAdjustment {
  train_id: string;
  priority: string;
  original_entry_time: string;
  original_exit_time: string;
  adjusted_entry_time: string;
  adjusted_exit_time: string;
  delay_added_min: number;
}
export interface AlternativePlan {
  plan_id: string;
  maintenance_id: string;
  maintenance_window: { start: string; end: string };
  assigned_crew_id: string;
  affected_trains: TrainAdjustment[];
  total_train_delay_min: number;
  priority_weighted_train_delay_min: number;
  maintenance_delay_min: number;
  risk_reduction_estimate: number;
  risk_delay_penalty: number;
  crew_cost: number;
  reroute_available: boolean;
  safety_conflicts: number;
  overall_score: number;
  rank: number;
}
export interface AlternativesResponse {
  maintenance_id: string;
  alternatives_generated: number;
  alternatives: AlternativePlan[];
  status: string;
}
export interface SimulationEvent {
  train_id: string;
  section_id: SectionId;
  scheduled_entry_time: string;
  scheduled_exit_time: string;
  simulated_entry_time: string;
  simulated_exit_time: string;
  planned_delay_min: number;
  additional_wait_min: number;
  delay_added_min: number;
  total_delay_min: number;
}
export interface Train {
  train_id: string;
  priority: string;
  planned_delay_min: number;
  additional_simulation_wait_min: number;
  total_delay_min: number;
  completion_status: string;
  section_events: SimulationEvent[];
}
export interface SimulationResult {
  plan_id: string;
  maintenance_id: string;
  section_id: SectionId;
  simulation_date: string;
  random_seed: number;
  kpis: {
    total_delay_min: number;
    max_single_train_delay_min: number;
    average_delay_min: number;
    affected_trains_count: number;
    affected_train_ids: string[];
    conflicts_detected: number;
    maintenance_completed: boolean;
    maintenance_completion_time: string | null;
    trains_simulated: number;
    maintenance_start_time: string | null;
    maintenance_end_time: string | null;
    predicted_maintenance_duration_min: number;
    simulated_maintenance_duration_min: number;
  };
  maintenance: {
    maintenance_id: string;
    plan_id: string;
    section_id: SectionId;
    planned_start: string;
    planned_end: string;
    simulated_start: string | null;
    simulated_end: string | null;
    predicted_duration_min: number;
    simulated_duration_min: number;
    duration_variation_min: number;
    completion_status: string;
  };
  train_results: Train[];
  safety_events: {
    time_min: number;
    section_id: SectionId;
    type: string;
    train_id?: string;
  }[];
  maintenance_events: {
    event: string;
    time_min: number;
    section_id: SectionId;
  }[];
}
export interface FeedbackStats {
  total_simulations: number;
  duration_mae_min: number;
  delay_mae_min: number;
  mean_duration_error_min: number;
  mean_delay_error_min: number;
  scope: string;
  data_source: string;
}
export type Decision = "APPROVED" | "MODIFY" | "REJECTED";
export interface PlanDecision {
  plan_id: string;
  maintenance_id: string;
  decision: Decision;
  decision_id: string;
  recorded_at: string;
  evidence_hash: string;
  execution_started: boolean;
}
export interface Traffic {
  section_id: SectionId;
  hour: number;
  weekday: number;
  expected_trains_per_hour: number;
}
