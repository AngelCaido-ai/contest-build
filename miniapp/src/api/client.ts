const API_BASE = import.meta.env.VITE_API_BASE || "https://85-239-58-214.nip.io";

export type UploadedMedia = {
  type: "photo" | "video" | "animation" | "document";
  file_id: string;
  message_id?: number | null;
};

let authToken = localStorage.getItem("token") ?? "";

export function setAuthToken(token: string) {
  authToken = token;
  localStorage.setItem("token", token);
}

export function getAuthToken() {
  return authToken;
}

export class NetworkError extends Error {
  constructor(message = "No internet connection") {
    super(message);
    this.name = "NetworkError";
  }
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

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch {
    throw new NetworkError();
  }

  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail =
      typeof data?.detail === "string" ? data.detail : `API error ${res.status}`;
    throw new Error(detail);
  }
  return data as T;
}

export async function uploadMedia(file: File): Promise<UploadedMedia> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await apiFetch<{ status: string } & UploadedMedia>("/deals/media/upload", {
    method: "POST",
    body: formData,
  });
  return {
    type: response.type,
    file_id: response.file_id,
    message_id: response.message_id ?? null,
  };
}
