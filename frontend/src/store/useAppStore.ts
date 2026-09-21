import { create } from "zustand";
import { errorMessage } from "../api/client";
import { planningApi } from "../api/planning";
import { simulationApi } from "../api/simulation";
import type {
  Asset,
  Health,
  RiskPrediction,
  MaintenanceRequirement,
  MaintenanceInput,
  ConflictResponse,
  AlternativePlan,
  SimulationResult,
  FeedbackStats,
  PlanDecision,
  Decision,
  CorridorData,
  TrainRecord,
  CrewRecord,
  TimetableRecord,
  WeatherRecord,
  MaintenanceHistoryRecord,
} from "../types";
import { operatingDate } from "../lib";

interface AppState {
  assets: Asset[];
  corridorData: CorridorData | null;
  trains: TrainRecord[];
  crews: CrewRecord[];
  timetable: TimetableRecord[];
  weather: WeatherRecord[];
  maintenanceHistory: MaintenanceHistoryRecord[];
  datasets: Record<string, number | string> | null;
  health: Health | null;
  connected: boolean;
  initializing: boolean;
  bootError: string | null;
  selectedAssetId: string | null;
  risks: Record<string, RiskPrediction>;
  maintenance: MaintenanceRequirement | null;
  conflicts: ConflictResponse | null;
  plans: AlternativePlan[];
  selectedPlanId: string | null;
  comparison: string[];
  simulations: Record<string, SimulationResult>;
  decisions: Record<string, PlanDecision>;
  feedback: FeedbackStats | null;
  busy: string | null;
  error: string | null;
  sheetOpen: boolean;
  initialize: (refreshFiles?: boolean) => Promise<void>;
  selectAsset: (id: string) => void;
  predictRisk: (asset: Asset) => Promise<void>;
  openSheet: () => void;
  closeSheet: () => void;
  createMaintenance: (input: MaintenanceInput) => Promise<boolean>;
  detect: () => Promise<void>;
  generate: () => Promise<void>;
  selectPlan: (id: string) => void;
  toggleCompare: (id: string) => void;
  simulate: (id: string) => Promise<boolean>;
  decide: (decision: Decision, execution?: { execution_mode: string; department_id?: string | null; contract_id?: string | null; amc_id?: string | null; oem_service_id?: string | null }) => Promise<PlanDecision | null>;
  setError: (error: string | null) => void;
  selectHighestRisk: () => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  assets: [],
  corridorData: null,
  trains: [],
  crews: [],
  timetable: [],
  weather: [],
  maintenanceHistory: [],
  datasets: null,
  health: null,
  connected: false,
  initializing: true,
  bootError: null,
  selectedAssetId: null,
  risks: {},
  maintenance: null,
  conflicts: null,
  plans: [],
  selectedPlanId: null,
  comparison: [],
  simulations: {},
  decisions: {},
  feedback: null,
  busy: null,
  error: null,
  sheetOpen: false,
  initialize: async (refreshFiles = false) => {
    set({ initializing: true, bootError: null });
    try {
      const { health, assets, corridor, trains, crews, timetable, weather, maintenanceHistory, datasets } = await planningApi.bootstrap(refreshFiles);
      set({
        health,
        assets,
        corridorData: corridor,
        trains,
        crews,
        timetable,
        weather,
        maintenanceHistory,
        datasets: datasets ?? get().datasets,
        connected: true,
        initializing: false,
        bootError: null,
      });
    } catch (e) {
      set({
        connected: false,
        initializing: false,
        bootError: errorMessage(e),
      });
    }
  },
  selectAsset: (id) => set({ selectedAssetId: id, error: null }),
  predictRisk: async (asset) => {
    if (get().busy) return;
    set({ busy: "Calculating asset risk…", error: null });
    try {
      const data = await planningApi.predictRisk(asset);
      set((s) => ({ risks: { ...s.risks, [asset.asset_id]: data } }));
    } catch (e) {
      set({ error: errorMessage(e) });
    } finally {
      set({ busy: null });
    }
  },
  openSheet: () => set({ sheetOpen: true, error: null }),
  closeSheet: () => set({ sheetOpen: false, error: null }),
  createMaintenance: async (input) => {
    if (get().busy) return false;
    set({ busy: "Creating maintenance requirement…", error: null });
    try {
      const data = await planningApi.createMaintenance(input);
      set({
        maintenance: data,
        conflicts: null,
        plans: [],
        comparison: [],
        selectedPlanId: null,
        sheetOpen: false,
      });
      await get().initialize();
      return true;
    } catch (e) {
      set({ error: errorMessage(e) });
      return false;
    } finally {
      set({ busy: null });
    }
  },
  detect: async () => {
    const m = get().maintenance;
    if (!m || get().busy) return;
    set({ busy: "Detecting schedule conflicts…", error: null });
    try {
      const data = await planningApi.detectConflicts({
        maintenance_id: m.maintenance_id,
        section_id: m.section_id,
        start_time: m.preferred_start_time,
        end_time: new Date(
          Date.parse(m.preferred_start_time) + m.minimum_duration_min * 60000,
        ).toISOString(),
      });
      set({ conflicts: data });
    } catch (e) {
      set({ error: errorMessage(e) });
    } finally {
      set({ busy: null });
    }
  },
  generate: async () => {
    const m = get().maintenance;
    if (!m || get().busy) return;
    set({ busy: "Optimizing maintenance alternatives…", error: null });
    try {
      const data = await planningApi.generateAlternatives(m.maintenance_id);
      set({
        plans: data.alternatives,
        selectedPlanId: data.alternatives[0]?.plan_id || null,
        comparison: [],
        error: data.alternatives.length
          ? null
          : "No feasible plan. Adjust the planning horizon or duration and try again.",
      });
    } catch (e) {
      set({ error: errorMessage(e) });
    } finally {
      set({ busy: null });
    }
  },
  selectPlan: (id) => set({ selectedPlanId: id, error: null }),
  toggleCompare: (id) =>
    set((s) => ({
      comparison: s.comparison.includes(id)
        ? s.comparison.filter((p) => p !== id)
        : [...s.comparison, id],
    })),
  simulate: async (id) => {
    const plan = get().plans.find((p) => p.plan_id === id);
    if (!plan || get().busy) return false;
    set({
      busy: "Running digital-twin simulation…",
      error: null,
      selectedPlanId: id,
    });
    try {
      const data = await simulationApi.run({
        plan_id: id,
        simulation_date: operatingDate(plan.maintenance_window.start),
        random_seed: 42,
      });
      set((s) => ({ simulations: { ...s.simulations, [id]: data } }));
      try {
        const feedback = await simulationApi.feedback();
        set({ feedback });
      } catch (e) {
        set({
          feedback: null,
          error:
            "Simulation completed. Feedback statistics: " + errorMessage(e),
        });
      }
      return true;
    } catch (e) {
      set({ error: errorMessage(e) });
      return false;
    } finally {
      set({ busy: null });
    }
  },
  decide: async (decision, execution) => {
    const s = get(),
      p = s.plans.find((p) => p.plan_id === s.selectedPlanId);
    if (!p || s.busy) return null;
    set({ busy: "Recording human decision…", error: null });
    try {
      const data = await planningApi.decide({
        plan_id: p.plan_id,
        maintenance_id: p.maintenance_id,
        decision,
        ...(execution || {}),
      });
      set((s) => ({ decisions: { ...s.decisions, [p.plan_id]: data } }));
      return data;
    } catch (e) {
      set({ error: errorMessage(e) });
      return null;
    } finally {
      set({ busy: null });
    }
  },
  setError: (error) => set({ error }),
  selectHighestRisk: () => {
    const a = [...get().assets].sort(
      (a, b) =>
        ({ CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 })[b.risk_level] -
          { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 }[a.risk_level] ||
        a.asset_id.localeCompare(b.asset_id),
    )[0];
    if (a) set({ selectedAssetId: a.asset_id });
  },
}));
