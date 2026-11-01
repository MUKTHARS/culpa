import { api } from "./client";

export interface Me {
  login_required: boolean;
  authenticated: boolean;
  username: string | null;
}

export const authApi = {
  login: (username: string, password: string) =>
    api.post<{ token: string; username: string }>("/auth/login", { username, password }),
  logout: () => api.post<{ ok: boolean }>("/auth/logout"),
  me: () => api.get<Me>("/auth/me"),
};
