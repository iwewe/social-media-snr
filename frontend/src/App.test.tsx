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

  const respond = (me: object) =>
    fetchMock.mockImplementation(async (url: string) => {
      const body = url === "/api/auth/me/" ? me : url === "/api/investigations/" ? [] : {};
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });

  it("super admin melihat tautan Akun di bilah atas; pengguna biasa tidak", async () => {
    respond({ username: "admin", is_staff: true, is_superuser: true });
    const view = renderAt("/");
    expect(await screen.findByRole("link", { name: "Akun" })).toHaveAttribute("href", "/users");
    view.unmount();
    respond({ username: "analis", is_staff: false, is_superuser: false });
    renderAt("/");
    await screen.findByRole("heading", { name: "Investigasi" });
    expect(screen.queryByRole("link", { name: "Akun" })).toBeNull();
  });

  it("halaman /users menolak pengguna biasa dengan pesan jelas", async () => {
    respond({ username: "analis", is_staff: false, is_superuser: false });
    renderAt("/users");
    expect(await screen.findByRole("alert")).toHaveTextContent("khusus super admin");
  });
});
