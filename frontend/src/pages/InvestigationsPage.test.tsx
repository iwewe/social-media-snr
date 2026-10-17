import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { InvestigationSummary } from "../api/types";
import { mockApi } from "../test/factories";
import { InvestigationsPage } from "./InvestigationsPage";

afterEach(() => vi.unstubAllGlobals());

const item = (over: Partial<InvestigationSummary> = {}): InvestigationSummary => ({
  id: 1,
  name: "Tim A",
  description: "",
  created_at: "2026-10-16T05:00:00Z",
  created_by: "pemilik",
  issue_count: 2,
  target_count: 3,
  my_role: "OWNER",
  member_count: 4,
  ...over,
});

function open(items: InvestigationSummary[]) {
  mockApi({ "GET /api/investigations/": () => ({ body: items }) });
  return render(
    <MemoryRouter>
      <InvestigationsPage />
    </MemoryRouter>,
  );
}

describe("InvestigationsPage", () => {
  it("menampilkan lencana peran dan jumlah anggota tiap investigasi", async () => {
    open([
      item(),
      item({ id: 2, name: "Tim B", my_role: "VIEWER", member_count: 1 }),
      item({ id: 3, name: "Tim C", my_role: "ADMIN" }),
    ]);
    const a = (await screen.findByRole("link", { name: "Tim A" })).closest("li")!;
    expect(a.querySelector(".badge.role")).toHaveTextContent("Pemilik");
    expect(a).toHaveTextContent("4 anggota");
    expect(
      screen.getByRole("link", { name: "Tim B" }).closest("li")!.querySelector(".badge.role"),
    ).toHaveTextContent("Pembaca");
    expect(
      screen.getByRole("link", { name: "Tim C" }).closest("li")!.querySelector(".badge.role"),
    ).toHaveTextContent("Super admin");
  });

  it("daftar kosong menjelaskan cara memperoleh akses", async () => {
    open([]);
    expect(
      await screen.findByText(/Belum ada investigasi yang dapat Anda lihat/),
    ).toBeInTheDocument();
    expect(screen.getByText(/minta Pemilik investigasi menambahkan Anda/)).toBeInTheDocument();
  });

  it("formulir pembuatan tetap tersedia (pembuat menjadi Pemilik)", async () => {
    open([]);
    expect(await screen.findByRole("heading", { name: "Buat investigasi" })).toBeInTheDocument();
  });
});
