import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from "react";
import { apiFetch, setAuthToken, getAuthToken } from "../api/client";
import type { User } from "../types";

type AuthContextValue = {
  token: string;
  user: User | null;
  isReady: boolean;
  authenticate: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be inside AuthProvider");
  return ctx;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState(getAuthToken());
  const [user, setUser] = useState<User | null>(null);
  const [isReady, setIsReady] = useState(false);

  const fetchProfile = useCallback(async () => {
    try {
      const me = await apiFetch<User>("/auth/me");
      setUser(me);
    } catch {
      /* token expired or invalid — ignore */
    }
  }, []);

  const authenticate = useCallback(async () => {
    try {
      const tg = window.Telegram?.WebApp;
      const initData = tg?.initData ?? "";
      if (!initData) {
        if (getAuthToken()) {
          await fetchProfile();
        }
        setIsReady(true);
        return;
      }
      const res = await fetch(
        `${import.meta.env.VITE_API_BASE || "https://85-239-58-214.nip.io"}/auth/miniapp`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ init_data: initData }),
        },
      );
      if (!res.ok) {
        if (getAuthToken()) {
          await fetchProfile();
        }
        setIsReady(true);
        return;
      }
      const data = await res.json();
      setAuthToken(data.token);
      setToken(data.token);
      if (data.user) setUser(data.user);
      setIsReady(true);
    } catch {
      setIsReady(true);
    }
  }, [fetchProfile]);

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (tg?.ready) tg.ready();
    authenticate();
  }, [authenticate]);

  return (
    <AuthContext.Provider value={{ token, user, isReady, authenticate }}>
      {children}
    </AuthContext.Provider>
  );
}
