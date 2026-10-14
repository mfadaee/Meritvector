"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, getToken, post, setToken } from "./api";

export type Me = {
  user_id: string;
  display_name: string;
  role: "employee" | "manager" | "hr_reviewer" | "admin" | "researcher";
  employee_id: string | null;
  tenant: { id: string; name: string; is_synthetic: boolean; assessment_enabled: boolean; as_of: string };
  employee: { job_family: string; level: string; business_unit: string } | null;
  direct_reports: number;
  permissions: Record<string, boolean>;
};

type AuthState = {
  me: Me | null;
  ready: boolean;
  login: (userId: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
};

const Ctx = createContext<AuthState>({ me: null, ready: false, login: async () => {}, logout: () => {}, refresh: async () => {} });

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setMe(null);
      setReady(true);
      return;
    }
    try {
      setMe(await api<Me>("/auth/me"));
    } catch {
      setToken(null);
      setMe(null);
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(
    async (userId: string) => {
      const r = await post<{ token: string }>("/auth/demo-login", { user_id: userId });
      setToken(r.token);
      await refresh();
    },
    [refresh],
  );

  const logout = useCallback(() => {
    setToken(null);
    setMe(null);
  }, []);

  return <Ctx.Provider value={{ me, ready, login, logout, refresh }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);

export const ROLE_LABEL: Record<string, string> = {
  employee: "Employee",
  manager: "Manager",
  hr_reviewer: "HR reviewer",
  admin: "Administrator",
  researcher: "Researcher",
};
