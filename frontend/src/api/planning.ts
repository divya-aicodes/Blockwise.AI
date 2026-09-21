import { api } from "./client";
import type {
  AlternativesResponse,
  Asset,
  ConflictResponse,
  CorridorData,
  CrewRecord,
  Decision,
  Health,
  MaintenanceInput,
  MaintenanceRequirement,
  PlanDecision,
  RiskPrediction,
  TimetableRecord,
  TrainRecord,
  WeatherRecord,
  MaintenanceHistoryRecord,
} from "../types";

export const planningApi = {
  refreshData: async () =>
    (await api.post<{ status: string; datasets: Record<string, number | string> }>("/data/refresh")).data,
  bootstrap: async (refreshFiles = false) => {
    const refresh = refreshFiles ? await planningApi.refreshData() : null;
    const [health, assets, corridor, trains, crews, timetable, weather, maintenanceHistory] = await Promise.all([
      api.get<Health>("/health"),
      api.get<Asset[]>("/assets"),
      api.get<CorridorData>("/corridor").catch(() => ({ data: null as CorridorData | null })),
      api.get<TrainRecord[]>("/trains").catch(() => ({ data: [] as TrainRecord[] })),
      api.get<CrewRecord[]>("/crews").catch(() => ({ data: [] as CrewRecord[] })),
      api.get<TimetableRecord[]>("/timetable").catch(() => ({ data: [] as TimetableRecord[] })),
      api.get<WeatherRecord[]>("/weather").catch(() => ({ data: [] as WeatherRecord[] })),
      api.get<MaintenanceHistoryRecord[]>("/maintenance-history").catch(() => ({ data: [] as MaintenanceHistoryRecord[] })),
    ]);
    return {
      health: health.data,
      assets: assets.data,
      corridor: corridor.data,
      trains: trains.data,
      crews: crews.data,
      timetable: timetable.data,
      weather: weather.data,
      maintenanceHistory: maintenanceHistory.data,
      datasets: refresh?.datasets ?? null,
    };
  },
  predictRisk: async (asset: Asset) => {
    const { age_years, condition_score, previous_failures, days_since_maintenance, criticality, weather_condition } = asset;
    return (await api.post<RiskPrediction>("/predict-risk", { age_years, condition_score, previous_failures, days_since_maintenance, criticality, weather_condition })).data;
  },
  createMaintenance: async (input: MaintenanceInput) =>
    (await api.post<MaintenanceRequirement>("/create-maintenance", input)).data,
  detectConflicts: async (payload: { maintenance_id: string; section_id: string; start_time: string; end_time: string }) =>
    (await api.post<ConflictResponse>("/detect-conflicts", payload)).data,
  generateAlternatives: async (maintenance_id: string) =>
    (await api.post<AlternativesResponse>("/generate-alternatives", { maintenance_id, top_n: 5, max_train_delay_min: 360, solver_timeout_seconds: 10 })).data,
  decide: async (payload: {
    plan_id: string;
    maintenance_id: string;
    decision: Decision;
    execution_mode?: string;
    department_id?: string | null;
    contract_id?: string | null;
    amc_id?: string | null;
    oem_service_id?: string | null;
  }) => (await api.post<PlanDecision>("/plan-decision", payload)).data,
};
