import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, api, ensureCsrf, getCookie } from "./client";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("klien API", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockReset();
    document.cookie = "csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  });
  afterEach(() => vi.unstubAllGlobals());

  it("membaca cookie dengan nilai berisi tanda sama dengan", () => {
    document.cookie = "csrftoken=abc=def";
    expect(getCookie("csrftoken")).toBe("abc=def");
  });

  it("GET tidak mengirim header CSRF maupun body", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }));
    await api.get("/api/meta/");
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("GET");
    expect(init.body).toBeUndefined();
    expect(init.headers).not.toHaveProperty("X-CSRFToken");
  });

  it("POST mengirim JSON dan token CSRF dari cookie", async () => {
    document.cookie = "csrftoken=tok123";
    fetchMock.mockResolvedValue(jsonResponse({ id: 1 }, 201));
    await api.post("/api/investigations/", { name: "A" });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/investigations/");
    expect(init.credentials).toBe("same-origin");
    expect(init.headers).toMatchObject({
      "Content-Type": "application/json",
      "X-CSRFToken": "tok123",
    });
    expect(init.body).toBe(JSON.stringify({ name: "A" }));
  });

  it("POST tanpa body tetap mengirim JSON kosong", async () => {
    document.cookie = "csrftoken=tok";
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    await expect(api.post("/api/auth/logout/")).resolves.toBeUndefined();
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.body).toBe("{}");
  });

  it("meminta cookie CSRF dulu bila belum ada", async () => {
    fetchMock.mockImplementationOnce(async () => {
      document.cookie = "csrftoken=baru";
      return jsonResponse({ detail: "ok" });
    });
    await expect(ensureCsrf()).resolves.toBe("baru");
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/csrf/", { credentials: "same-origin" });
  });

  it("galat domain membawa status, kode, dan existing_id", async () => {
    document.cookie = "csrftoken=t";
    fetchMock.mockResolvedValue(
      jsonResponse({ detail: "Sudah terdaftar.", code: "duplicate_target", existing_id: 7 }, 409),
    );
    const error = await api.post("/x", {}).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 409, code: "duplicate_target", existingId: 7 });
    expect((error as ApiError).message).toBe("Sudah terdaftar.");
  });

  it("meratakan galat validasi per-field", async () => {
    document.cookie = "csrftoken=t";
    fetchMock.mockResolvedValue(
      jsonResponse({ name: ["Wajib diisi."], url: ["Tidak valid."] }, 400),
    );
    const error = (await api.post("/x", {}).catch((e: unknown) => e)) as ApiError;
    expect(error.message).toBe("name: Wajib diisi. url: Tidak valid.");
  });

  it("memberi pesan jelas bila server tidak terjangkau", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const error = (await api.get("/api/meta/").catch((e: unknown) => e)) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(0);
    expect(error.message).toContain("Tidak dapat menghubungi server");
  });

  it("badan non-JSON pada galat memakai pesan umum", async () => {
    fetchMock.mockResolvedValue(new Response("<html>oops</html>", { status: 502 }));
    const error = (await api.get("/api/meta/").catch((e: unknown) => e)) as ApiError;
    expect(error.status).toBe(502);
    expect(error.message).toBe("Permintaan gagal (502).");
  });
});
