import { api } from "./client";
import type { FeedbackStats, SimulationResult } from "../types";

export const simulationApi = {
  run: async (payload: { plan_id: string; simulation_date: string; random_seed: number }) =>
    (await api.post<SimulationResult>("/simulate-plan", payload)).data,
  feedback: async () => (await api.get<FeedbackStats>("/feedback-stats")).data,
};
