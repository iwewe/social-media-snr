import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { AuthProvider } from "./auth/AuthContext";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("App (rute dan sesi)", () => {
  const fetchMock = vi.fn();
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockReset();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("mengalihkan pengguna anonim ke halaman login", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "Autentikasi tidak diberikan." }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );
    renderAt("/investigations/5");
    expect(await screen.findByRole("heading", { name: "Masuk ke SNR" })).toBeInTheDocument();
    // Tidak ada data investigasi yang diminta sebelum login.
    const urls = fetchMock.mock.calls.map((c) => c[0] as string);
    expect(urls).toEqual(["/api/auth/me/"]);
  });

  it("menampilkan daftar investigasi untuk pengguna yang sudah login", async () => {
    fetchMock.mockImplementation(async (url: string) => {
      const body =
        url === "/api/auth/me/"
          ? { username: "analis", is_staff: false }
          : url === "/api/investigations/"
            ? []
            : {};
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    renderAt("/");
    expect(await screen.findByRole("heading", { name: "Investigasi" })).toBeInTheDocument();
    expect(screen.getByText("analis")).toBeInTheDocument();
    expect(await screen.findByText(/Belum ada investigasi/)).toBeInTheDocument();
  });
});
