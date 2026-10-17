import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthContext } from "../auth/context";
import { account, mockApi } from "../test/factories";
import { UsersPage } from "./UsersPage";

afterEach(() => vi.unstubAllGlobals());

function page(superuser: boolean) {
  const value = {
    user: { username: "admin", is_staff: superuser, is_superuser: superuser },
    login: async () => {},
    logout: async () => {},
  };
  return render(
    <MemoryRouter>
      <AuthContext.Provider value={value}>
        <UsersPage />
      </AuthContext.Provider>
    </MemoryRouter>,
  );
}

const rows = [
  account(),
  account({
    id: 2,
    username: "sari",
    is_superuser: false,
    last_login: null,
    active_memberships: 3,
  }),
  account({ id: 3, username: "lama", is_superuser: false, is_active: false }),
];
const LIST = "GET /api/users/";

describe("UsersPage", () => {
  it("non-superuser: ditolak di tampilan dan TIDAK memanggil API", () => {
    const { calls } = mockApi({});
    page(false);
    expect(screen.getByRole("alert")).toHaveTextContent("khusus super admin");
    expect(calls).toEqual([]);
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("menampilkan akun, status, masuk terakhir, dan jumlah investigasi", async () => {
    mockApi({ [LIST]: () => ({ body: rows }) });
    page(true);
    const table = await screen.findByRole("table", { name: "Akun pengguna" });
    const sari = within(table).getByText("sari").closest("tr")!;
    expect(sari).toHaveTextContent("Aktif");
    expect(sari).toHaveTextContent("belum pernah");
    expect(sari).toHaveTextContent("3");
    expect(within(table).getByText("lama").closest("tr")).toHaveTextContent("Nonaktif");
    expect(within(table).getByText("admin").closest("tr")).toHaveTextContent("(Anda)");
    expect(within(table).getByText("admin").closest("tr")).toHaveTextContent("Super admin");
  });

  it("tidak dapat menonaktifkan akun sendiri", async () => {
    mockApi({ [LIST]: () => ({ body: rows }) });
    page(true);
    await screen.findByRole("table", { name: "Akun pengguna" });
    expect(screen.getByRole("button", { name: "Nonaktifkan admin" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Nonaktifkan sari" })).toBeEnabled();
  });

  it("membuat akun: kirim nama (dipangkas) dan kata sandi, kosongkan isian, jangan menampilkan kata sandi", async () => {
    const secret = "Sandi-awal-yang-kuat-42!";
    let n = 0;
    const { fetchMock } = mockApi({
      [LIST]: () => ({
        body:
          ++n === 1 ? rows : [...rows, account({ id: 9, username: "baru", is_superuser: false })],
      }),
      "POST /api/users/": () => ({
        status: 201,
        body: account({ id: 9, username: "baru", is_superuser: false }),
      }),
    });
    page(true);
    await screen.findByRole("table", { name: "Akun pengguna" });
    await userEvent.type(screen.getByLabelText("Nama pengguna"), "  baru  ");
    await userEvent.type(screen.getByLabelText("Kata sandi awal"), secret);
    await userEvent.click(screen.getByRole("button", { name: "Buat akun" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Akun baru dibuat");
    const post = fetchMock.mock.calls.find((c) => c[1]?.method === "POST")!;
    expect(JSON.parse(String(post[1]?.body))).toEqual({ username: "baru", password: secret });
    expect(screen.getByLabelText("Nama pengguna")).toHaveValue("");
    expect(screen.getByLabelText("Kata sandi awal")).toHaveValue("");
    expect(document.body.textContent).not.toContain(secret);
    await waitFor(() => expect(screen.getByText("baru")).toBeInTheDocument());
  });

  it("kata sandi awal bertipe password dan tidak diisi otomatis browser", async () => {
    mockApi({ [LIST]: () => ({ body: rows }) });
    page(true);
    await screen.findByRole("table", { name: "Akun pengguna" });
    const input = screen.getByLabelText("Kata sandi awal");
    expect(input).toHaveAttribute("type", "password");
    expect(input).toHaveAttribute("autocomplete", "new-password");
  });

  it("galat validasi server (kata sandi lemah) ditampilkan", async () => {
    mockApi({
      [LIST]: () => ({ body: rows }),
      "POST /api/users/": () => ({
        status: 400,
        body: { password: ["Kata sandi ini terlalu umum."] },
      }),
    });
    page(true);
    await screen.findByRole("table", { name: "Akun pengguna" });
    await userEvent.type(screen.getByLabelText("Nama pengguna"), "baru");
    await userEvent.type(screen.getByLabelText("Kata sandi awal"), "123");
    await userEvent.click(screen.getByRole("button", { name: "Buat akun" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("terlalu umum");
  });

  it("tombol Buat akun nonaktif sampai nama dan kata sandi terisi", async () => {
    mockApi({ [LIST]: () => ({ body: rows }) });
    page(true);
    await screen.findByRole("table", { name: "Akun pengguna" });
    expect(screen.getByRole("button", { name: "Buat akun" })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Nama pengguna"), "baru");
    expect(screen.getByRole("button", { name: "Buat akun" })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Kata sandi awal"), "x");
    expect(screen.getByRole("button", { name: "Buat akun" })).toBeEnabled();
  });

  it("menonaktifkan dan mengaktifkan akun", async () => {
    const { fetchMock } = mockApi({
      [LIST]: () => ({ body: rows }),
      "POST /api/users/2/activation/": () => ({
        body: account({ id: 2, username: "sari", is_active: false }),
      }),
      "POST /api/users/3/activation/": () => ({
        body: account({ id: 3, username: "lama", is_active: true }),
      }),
    });
    page(true);
    await userEvent.click(await screen.findByRole("button", { name: "Nonaktifkan sari" }));
    expect(await screen.findByRole("status")).toHaveTextContent("sari dinonaktifkan");
    await userEvent.click(screen.getByRole("button", { name: "Aktifkan lama" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("lama diaktifkan"));
    const bodies = fetchMock.mock.calls
      .filter((c) => c[1]?.method === "POST")
      .map((c) => JSON.parse(String(c[1]?.body)));
    expect(bodies).toEqual([{ active: false }, { active: true }]);
  });

  it("mengatur kata sandi: formulir muncul, kirim, menutup, dan tidak menampilkan kata sandi", async () => {
    const secret = "Sandi-pengganti-yang-kuat-7!";
    const { fetchMock } = mockApi({
      [LIST]: () => ({ body: rows }),
      "POST /api/users/2/password/": () => ({ status: 204, body: null }),
    });
    page(true);
    await userEvent.click(await screen.findByRole("button", { name: "Atur kata sandi sari" }));
    await userEvent.type(screen.getByLabelText("Kata sandi baru"), secret);
    await userEvent.click(screen.getByRole("button", { name: "Simpan kata sandi" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Kata sandi sari diganti");
    expect(screen.queryByLabelText("Kata sandi baru")).toBeNull();
    expect(document.body.textContent).not.toContain(secret);
    const post = fetchMock.mock.calls.find((c) => c[1]?.method === "POST")!;
    expect(JSON.parse(String(post[1]?.body))).toEqual({ password: secret });
  });

  it("galat server saat memuat ditampilkan", async () => {
    mockApi({
      [LIST]: () => ({
        status: 403,
        body: {
          detail: "Hanya super admin yang dapat mengelola akun pengguna.",
          code: "superuser_required",
        },
      }),
    });
    page(true);
    expect(await screen.findByRole("alert")).toHaveTextContent("Hanya super admin");
  });
});
