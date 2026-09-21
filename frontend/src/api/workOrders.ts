import { api } from "./client";
import type { Checklist, CrewMember, ExecutionSummary, WorkOrder } from "../types/api";

export const workOrdersApi = {
  list: async (status?: string) =>
    (await api.get<WorkOrder[]>("/work-orders", { params: status ? { status } : undefined })).data,
  get: async (id: string) => (await api.get<WorkOrder>(`/work-orders/${id}`)).data,
  summary: async (id: string) =>
    (await api.get<ExecutionSummary>(`/work-orders/${id}/execution-summary`)).data,
  activeCrew: async () => (await api.get<CrewMember[]>("/auth/active")).data,
  assign: async (id: string, crew_employee_id: string) =>
    (await api.post<WorkOrder>(`/work-orders/${id}/assign`, { crew_employee_id })).data,
  acknowledge: async (id: string) =>
    (await api.post<WorkOrder>(`/work-orders/${id}/acknowledge`)).data,
  start: async (id: string, latitude: number, longitude: number) =>
    (await api.post<WorkOrder>(`/work-orders/${id}/start`, { latitude, longitude })).data,
  pause: async (id: string, reason: string) =>
    (await api.post<WorkOrder>(`/work-orders/${id}/pause`, { reason })).data,
  resume: async (id: string) =>
    (await api.post<WorkOrder>(`/work-orders/${id}/resume`)).data,
  complete: async (id: string, payload: { latitude: number; longitude: number; notes: string; photos: string[] }) =>
    (await api.post<WorkOrder>(`/work-orders/${id}/complete`, payload)).data,
  verify: async (id: string, approved: boolean, comments: string) =>
    (await api.post<WorkOrder>(`/work-orders/${id}/verify`, { approved, comments })).data,
  checklists: async (id: string) =>
    (await api.get<{ checklists: Checklist[] }>(`/checklists/work-order/${id}`)).data.checklists,
  updateChecklist: async (id: string, item_id: string, value: boolean, note = "") =>
    (await api.post<Checklist>(`/checklists/${id}/item`, { item_id, value, note })).data,
  signOff: async (id: string) =>
    (await api.post<Checklist>(`/checklists/${id}/sign-off`)).data,
};
