import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
export const api = axios.create({ baseURL: "/api", timeout: 65000 });

const ACCESS_KEY = "railway_access_token";
const REFRESH_KEY = "railway_refresh_token";
let refreshPromise: Promise<string> | null = null;

api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem(ACCESS_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const request = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;
    const isAuthRoute = request?.url?.includes("/auth/login") || request?.url?.includes("/auth/refresh");
    const refreshToken = sessionStorage.getItem(REFRESH_KEY);
    if (error.response?.status !== 401 || !request || request._retried || isAuthRoute || !refreshToken) {
      return Promise.reject(error);
    }
    request._retried = true;
    try {
      refreshPromise ??= axios
        .post("/api/auth/refresh", { refresh_token: refreshToken })
        .then(({ data }) => {
          sessionStorage.setItem(ACCESS_KEY, data.access_token);
          sessionStorage.setItem(REFRESH_KEY, data.refresh_token);
          return data.access_token as string;
        })
        .finally(() => { refreshPromise = null; });
      const token = await refreshPromise;
      request.headers.Authorization = `Bearer ${token}`;
      return api(request);
    } catch (refreshError) {
      sessionStorage.removeItem(ACCESS_KEY);
      sessionStorage.removeItem(REFRESH_KEY);
      localStorage.removeItem(REFRESH_KEY);
      window.dispatchEvent(new Event("railway-auth-changed"));
      return Promise.reject(refreshError);
    }
  },
);
export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail: unknown = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail))
      return detail
        .map((item: { msg?: string }) => item.msg || "Invalid input")
        .join("; ");
    if (!error.response)
      return "Backend unavailable. Check the connection and try again.";
    return `Request failed (${error.response.status}). Please try again.`;
  }
  return error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";
}
