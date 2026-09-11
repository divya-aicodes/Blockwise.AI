import { create } from "zustand";
import { api, errorMessage } from "../api/client";
import { authConfig, tokenKey } from "../auth";
import type {
  Asset,
  Health,
  RiskPrediction,
  MaintenanceRequirement,
  MaintenanceInput,
  ConflictResponse,
  AlternativePlan,
  AlternativesResponse,
  SimulationResult,
  FeedbackStats,
  PlanDecision,
  Decision,
} from "../types";
import { operatingDate } from "../lib";
interface AppState {
  assets: Asset[];
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
  guideOpen: boolean;
  demo: boolean;
  initialize: () => Promise<void>;
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
  decide: (decision: Decision) => Promise<boolean>;
  setError: (error: string | null) => void;
  setGuide: (open: boolean) => void;
  startDemo: () => void;
}
export const useAppStore = create<AppState>((set, get) => ({
  assets: [],
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
  guideOpen: false,
  demo: false,
  initialize: async () => {
    try {
      const [health, assets] = await Promise.all([
        api.get<Health>("/health"),
        api.get<Asset[]>("/assets"),
      ]);
      set({
        health: health.data,
        assets: assets.data,
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
      const {
        age_years,
        condition_score,
        previous_failures,
        days_since_maintenance,
        criticality,
        weather_condition,
      } = asset;
      const { data } = await api.post<RiskPrediction>("/predict-risk", {
        age_years,
        condition_score,
        previous_failures,
        days_since_maintenance,
        criticality,
        weather_condition,
      });
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
      const { data } = await api.post<MaintenanceRequirement>(
        "/create-maintenance",
        input,
      );
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
      const { data } = await api.post<ConflictResponse>("/detect-conflicts", {
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
      const { data } = await api.post<AlternativesResponse>(
        "/generate-alternatives",
        {
          maintenance_id: m.maintenance_id,
          top_n: 5,
          max_train_delay_min: 360,
          solver_timeout_seconds: 10,
        },
      );
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
      const { data } = await api.post<SimulationResult>("/simulate-plan", {
        plan_id: id,
        simulation_date: operatingDate(plan.maintenance_window.start),
        random_seed: 42,
      });
      set((s) => ({ simulations: { ...s.simulations, [id]: data } }));
      try {
        const feedback = await api.get<FeedbackStats>("/feedback-stats");
        set({ feedback: feedback.data });
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
  decide: async (decision) => {
    const s = get(),
      p = s.plans.find((p) => p.plan_id === s.selectedPlanId);
    if (!p || s.busy) return false;
    set({ busy: "Recording human decision…", error: null });
    try {
      const { data } = await api.post<PlanDecision>("/plan-decision", {
        plan_id: p.plan_id,
        maintenance_id: p.maintenance_id,
        decision,
      }, localStorage.getItem(tokenKey) ? authConfig() : undefined);
      set((s) => ({ decisions: { ...s.decisions, [p.plan_id]: data } }));
      return true;
    } catch (e) {
      set({ error: errorMessage(e) });
      return false;
    } finally {
      set({ busy: null });
    }
  },
  setError: (error) => set({ error }),
  setGuide: (guideOpen) => set({ guideOpen }),
  startDemo: () => {
    const a = [...get().assets].sort(
      (a, b) =>
        ({ CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 })[b.risk_level] -
          { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 }[a.risk_level] ||
        a.asset_id.localeCompare(b.asset_id),
    )[0];
    if (a) set({ selectedAssetId: a.asset_id, demo: true, guideOpen: true });
  },
}));
