/**
 * Klien API. Sesi Django + CSRF: cookie `csrftoken` dibaca dan dikirim sebagai X-CSRFToken pada
 * setiap permintaan yang mengubah data. Tidak ada token yang disimpan di localStorage.
 */

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly existingId?: number;

  constructor(status: number, message: string, code?: string, existingId?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.existingId = existingId;
  }
}

export function getCookie(name: string): string | null {
  for (const part of document.cookie.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return decodeURIComponent(rest.join("="));
  }
  return null;
}

export async function ensureCsrf(): Promise<string> {
  const existing = getCookie("csrftoken");
  if (existing) return existing;
  await fetch("/api/auth/csrf/", { credentials: "same-origin" });
  const token = getCookie("csrftoken");
  if (!token) throw new ApiError(0, "Tidak dapat memperoleh token keamanan (CSRF).");
  return token;
}

/** Ratakan galat validasi DRF ({field: [pesan]}) atau {detail} menjadi satu kalimat. */
function messageFrom(data: unknown, fallback: string): string {
  if (data && typeof data === "object") {
    const record = data as Record<string, unknown>;
    if (typeof record.detail === "string") return record.detail;
    const parts = Object.entries(record).flatMap(([field, value]) =>
      Array.isArray(value) ? value.map((v) => `${field}: ${String(v)}`) : [],
    );
    if (parts.length > 0) return parts.join(" ");
  }
  return fallback;
}

export async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const init: RequestInit = { method, headers, credentials: "same-origin" };

  if (method !== "GET") {
    headers["Content-Type"] = "application/json";
    headers["X-CSRFToken"] = await ensureCsrf();
    // Selalu kirim JSON (walau kosong): parser API hanya menerima JSON.
    init.body = JSON.stringify(body ?? {});
  }

  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new ApiError(0, "Tidak dapat menghubungi server. Periksa koneksi Anda.");
  }

  if (response.status === 204) return undefined as T;

  let data: unknown = null;
  try {
    data = await response.json();
  } catch {
    // Badan bukan JSON; gunakan pesan umum di bawah.
  }

  if (!response.ok) {
    const record = (data && typeof data === "object" ? data : {}) as Record<string, unknown>;
    throw new ApiError(
      response.status,
      messageFrom(data, `Permintaan gagal (${response.status}).`),
      typeof record.code === "string" ? record.code : undefined,
      typeof record.existing_id === "number" ? record.existing_id : undefined,
    );
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
};
