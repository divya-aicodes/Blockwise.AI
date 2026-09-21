import { create } from "zustand";
import { authApi, clearTokens, getAccessToken, storeTokens } from "../api/auth";
import { errorMessage } from "../api/client";
import type { AuthUser } from "../types/api";

interface AuthState {
  user: AuthUser | null;
  initializing: boolean;
  error: string | null;
  loadMe: () => Promise<AuthUser | null>;
  login: (employeeId: string, password: string) => Promise<AuthUser | null>;
  logout: () => void;
}

export const roleHome = (role?: string) =>
  role === "ADMIN" ? "/admin" : role === "SUPERVISOR" ? "/supervisor" : "/crew";

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  initializing: true,
  error: null,
  loadMe: async () => {
    if (!getAccessToken()) {
      set({ user: null, initializing: false });
      return null;
    }
    try {
      const user = await authApi.me();
      set({ user, initializing: false, error: null });
      return user;
    } catch {
      clearTokens();
      set({ user: null, initializing: false });
      return null;
    }
  },
  login: async (employeeId, password) => {
    set({ error: null });
    try {
      const tokens = await authApi.login(employeeId.trim(), password);
      storeTokens(tokens);
      const user = await authApi.me();
      set({ user, initializing: false });
      return user;
    } catch (error) {
      set({ error: errorMessage(error), user: null, initializing: false });
      return null;
    }
  },
  logout: () => {
    clearTokens();
    set({ user: null, error: null });
  },
}));
