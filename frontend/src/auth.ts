import type { AxiosRequestConfig } from "axios";

export const tokenKey = "railway_access_token";

export type AuthUser = {
  employee_id: string;
  full_name: string;
  role: string;
  primary_skill?: string;
  availability?: string;
  is_active?: boolean;
};

export const authConfig = (): AxiosRequestConfig => ({
  headers: { Authorization: `Bearer ${localStorage.getItem(tokenKey) || ""}` },
});

export function notifyAuthChanged(): void {
  window.dispatchEvent(new Event("railway-auth-changed"));
}
