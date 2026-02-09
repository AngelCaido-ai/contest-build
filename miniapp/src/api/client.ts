const API_BASE = import.meta.env.VITE_API_BASE || "";

let authToken = localStorage.getItem("token") ?? "";

export function setAuthToken(token: string) {
  authToken = token;
  localStorage.setItem("token", token);
}

export function getAuthToken() {
  return authToken;
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = { ...(options.headers ?? {}) } as Record<string, string>;
  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`;
  }
  if (!headers["Content-Type"] && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail =
      typeof data?.detail === "string" ? data.detail : `API error ${res.status}`;
    throw new Error(detail);
  }
  return data as T;
}
