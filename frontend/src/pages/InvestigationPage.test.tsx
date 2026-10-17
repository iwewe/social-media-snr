import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { InvestigationDetail } from "../api/types";
import { AuthContext } from "../auth/context";
import { detail, member, mockApi } from "../test/factories";
import { InvestigationPage } from "./InvestigationPage";

afterEach(() => vi.unstubAllGlobals());

const META = {
  platforms: [{ value: "x", label: "X" }],
  target_types: [{ value: "post", label: "Posting" }],
  initial_stances: [{ value: "PRO", label: "PRO" }],
};

function open(role: InvestigationDetail["my_role"]) {
  mockApi({
    "GET /api/investigations/1/": () => ({ body: detail(role) }),
    "GET /api/meta/": () => ({ body: META }),
    "GET /api/investigations/1/members/": () => ({
      body: [member(), member({ user_id: 2, username: "sari", role: "VIEWER" })],
    }),
    "GET /api/targets/1/inspections/": () => ({ body: [] }),
  });
  const value = {
    user: { username: "pemilik", is_staff: false, is_superuser: role === "ADMIN" },
    login: async () => {},
    logout: async () => {},
  };
  return render(
    <MemoryRouter initialEntries={["/investigations/1"]}>
      <AuthContext.Provider value={value}>
        <Routes>
          <Route path="/investigations/:id" element={<InvestigationPage />} />
          <Route path="/" element={<p>beranda</p>} />
        </Routes>
      </AuthContext.Provider>
    </MemoryRouter>,
  );
}

const FORMS = [/Tambah issue/, /Daftarkan target/];

describe("InvestigationPage sesuai peran", () => {
  it("Pembaca: catatan hanya-baca, tanpa formulir tulis, Inspect nonaktif, tim tak dapat diubah", async () => {
    open("VIEWER");
    expect(await screen.findByRole("heading", { name: /Uji tim/ })).toBeInTheDocument();
    expect(screen.getByText("Pembaca", { selector: ".badge" })).toHaveAttribute(
      "data-role",
      "VIEWER",
    );
    const note = document.querySelector("[data-readonly]")!;
    expect(note).toHaveTextContent("Anda berperan Pembaca");
    expect(note.querySelector("strong")).toBeNull(); // CSS .message > strong memecah baris
    expect(note.children).toHaveLength(1); // hanya satu penanda inline
    for (const name of FORMS) expect(screen.queryByRole("heading", { name })).toBeNull();
    expect(screen.queryByText("Simpan proposition")).toBeNull();
    expect(screen.queryByRole("button", { name: "Revisi catatan" })).toBeNull();
    const card = document.querySelector("article.card[aria-label^='Target']") as HTMLElement;
    expect(await within(card).findByRole("button", { name: "Inspect" })).toBeDisabled();
    expect(within(card).getByRole("button", { name: "Inspect" })).toHaveAttribute(
      "title",
      expect.stringContaining("Pembaca"),
    );
    expect(await screen.findByRole("table", { name: "Anggota" })).toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "Tambah anggota" })).toBeNull();
  });

  it.each(["MEMBER", "OWNER", "ADMIN"] as const)(
    "%s: formulir tulis dan Inspect tersedia",
    async (role) => {
      open(role);
      await screen.findByRole("heading", { name: /Uji tim/ });
      for (const name of FORMS) expect(screen.getByRole("heading", { name })).toBeInTheDocument();
      expect(document.querySelector("[data-readonly]")).toBeNull();
      expect(screen.getByRole("button", { name: "Revisi catatan" })).toBeInTheDocument();
      const card = document.querySelector("article.card[aria-label^='Target']") as HTMLElement;
      expect(await within(card).findByRole("button", { name: "Inspect" })).toBeEnabled();
    },
  );

  it("Anggota melihat tim tetapi tidak dapat mengelolanya; Pemilik dan Super admin dapat", async () => {
    open("MEMBER");
    await screen.findByRole("table", { name: "Anggota" });
    expect(screen.queryByRole("form", { name: "Tambah anggota" })).toBeNull();
    expect(screen.queryByRole("combobox", { name: /^Peran / })).toBeNull();
  });

  it.each(["OWNER", "ADMIN"] as const)("%s: panel tim dapat mengelola", async (role) => {
    open(role);
    await screen.findByRole("table", { name: "Anggota" });
    expect(screen.getByRole("form", { name: "Tambah anggota" })).toBeInTheDocument();
  });

  it("lencana peran mengikuti peran (Super admin tampil sebagai 'Super admin')", async () => {
    open("ADMIN");
    await screen.findByRole("heading", { name: /Uji tim/ });
    expect(screen.getByText("Super admin", { selector: ".badge" })).toHaveAttribute(
      "data-role",
      "ADMIN",
    );
  });
});
