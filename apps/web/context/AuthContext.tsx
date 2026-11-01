"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { authApi } from "@/api/auth";
import { SESSION_TOKEN_KEY, SESSION_USER_KEY } from "@/constants/config";

interface AuthState {
  username: string;
  loggedIn: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  username: "",
  loggedIn: false,
  login: async () => {},
  logout: async () => {},
});

function store(token: string, username: string) {
  try {
    if (token) {
      window.localStorage.setItem(SESSION_TOKEN_KEY, token);
      window.localStorage.setItem(SESSION_USER_KEY, username);
    } else {
      window.localStorage.removeItem(SESSION_TOKEN_KEY);
      window.localStorage.removeItem(SESSION_USER_KEY);
    }
  } catch {
    /* storage unavailable */
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [username, setUsername] = useState("");

  useEffect(() => {
    try {
      if (window.localStorage.getItem(SESSION_TOKEN_KEY)) {
        setUsername(window.localStorage.getItem(SESSION_USER_KEY) ?? "");
      }
    } catch {
      /* storage unavailable */
    }
  }, []);

  const login = useCallback(async (user: string, password: string) => {
    const res = await authApi.login(user, password);
    store(res.token, res.username);
    setUsername(res.username);
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      store("", "");
      setUsername("");
    }
  }, []);

  return (
    <AuthContext.Provider value={{ username, loggedIn: Boolean(username), login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
