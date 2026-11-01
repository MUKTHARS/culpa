import { API_URL, SESSION_TOKEN_KEY, SESSION_USER_KEY } from "@/constants/config";
import { ROUTES } from "@/constants/routes";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

function sessionToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(SESSION_TOKEN_KEY);
  } catch {
    return null;
  }
}

/** Session missing or expired: forget it and send the analyst to the login page, then back here. */
function goToLogin() {
  if (typeof window === "undefined" || window.location.pathname === ROUTES.login) return;
  try {
    window.localStorage.removeItem(SESSION_TOKEN_KEY);
    window.localStorage.removeItem(SESSION_USER_KEY);
  } catch {
    /* storage unavailable */
  }
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.assign(`${ROUTES.login}?next=${next}`);
}

const RETRYABLE = new Set([502, 503, 504]);

async function request<T>(method: string, path: string, body?: unknown, attempt = 0): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = sessionToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    if (method === "GET" && attempt < 2) {
      await new Promise((r) => setTimeout(r, 300 * 2 ** attempt));
      return request<T>(method, path, body, attempt + 1);
    }
    throw new ApiError(0, "NetworkError", `Cannot reach the Culpa API at ${API_URL}. Is it running?`);
  }

  if (!res.ok) {
    if (method === "GET" && RETRYABLE.has(res.status) && attempt < 2) {
      await new Promise((r) => setTimeout(r, 300 * 2 ** attempt));
      return request<T>(method, path, body, attempt + 1);
    }
    let code = "HttpError";
    let message = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      code = data.error ?? code;
      message = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail ?? data);
    } catch {
      /* non-JSON error body */
    }
    if (res.status === 401 && !path.startsWith("/auth/")) goToLogin();
    throw new ApiError(res.status, code, message);
  }
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body ?? {}),
};

export const fetcher = <T>(path: string) => api.get<T>(path);
