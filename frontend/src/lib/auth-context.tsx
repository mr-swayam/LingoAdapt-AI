"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import * as authApi from "@/lib/auth-api";
import type { User, UserPreferences } from "@/types/auth";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

type AuthContextValue = {
  status: AuthStatus;
  user: User | null;
  accessToken: string | null;
  signup: (input: {
    email: string;
    password: string;
    native_language: string;
    target_language: string;
    daily_goal_xp: number;
  }) => Promise<void>;
  login: (input: { email: string; password: string }) => Promise<void>;
  logout: () => Promise<void>;
  updatePreferences: (input: Partial<UserPreferences>) => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    authApi
      .refresh()
      .then((res) => {
        if (cancelled) return;
        setUser(res.user);
        setAccessToken(res.access_token);
        setStatus("authenticated");
      })
      .catch(() => {
        if (cancelled) return;
        setStatus("unauthenticated");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const signup = useCallback<AuthContextValue["signup"]>(async (input) => {
    const res = await authApi.signup(input);
    setUser(res.user);
    setAccessToken(res.access_token);
    setStatus("authenticated");
  }, []);

  const login = useCallback<AuthContextValue["login"]>(async (input) => {
    const res = await authApi.login(input);
    setUser(res.user);
    setAccessToken(res.access_token);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      setUser(null);
      setAccessToken(null);
      setStatus("unauthenticated");
    }
  }, []);

  const updatePreferences = useCallback<AuthContextValue["updatePreferences"]>(
    async (input) => {
      if (!accessToken) throw new Error("Not authenticated");
      const preferences = await authApi.updatePreferences(accessToken, input);
      setUser((prev) => (prev ? { ...prev, preferences } : prev));
    },
    [accessToken],
  );

  const value = useMemo<AuthContextValue>(
    () => ({ status, user, accessToken, signup, login, logout, updatePreferences }),
    [status, user, accessToken, signup, login, logout, updatePreferences],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
