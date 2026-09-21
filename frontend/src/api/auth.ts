import { api } from "./client";
import type { AuthTokens, AuthUser, CrewMember } from "../types/api";

const ACCESS_KEY = "railway_access_token";
const REFRESH_KEY = "railway_refresh_token";

export const getAccessToken = () => sessionStorage.getItem(ACCESS_KEY);
export const getRefreshToken = () => sessionStorage.getItem(REFRESH_KEY);

export function storeTokens(tokens: AuthTokens): void {
  sessionStorage.setItem(ACCESS_KEY, tokens.access_token);
  sessionStorage.setItem(REFRESH_KEY, tokens.refresh_token);
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
  notifyAuthChanged();
}

export function clearTokens(): void {
  sessionStorage.removeItem(ACCESS_KEY);
  sessionStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
  notifyAuthChanged();
}

export function notifyAuthChanged(): void {
  window.dispatchEvent(new Event("railway-auth-changed"));
}

export const authApi = {
  login: async (employee_id: string, password: string) =>
    (await api.post<AuthTokens>("/auth/login", { employee_id, password })).data,
  register: async (payload: Record<string, unknown>) =>
    (await api.post("/auth/register", payload)).data,
  me: async () => (await api.get<AuthUser>("/auth/me")).data,
  pending: async () => (await api.get<CrewMember[]>("/auth/pending")).data,
  active: async () => (await api.get<CrewMember[]>("/auth/active")).data,
  approve: async (employee_id: string) =>
    (await api.post("/auth/approve", { employee_id })).data,
};
