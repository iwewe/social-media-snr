import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { InvestigationDetail } from "../api/types";
import { detail, mockApi } from "../test/factories";
import { AnalysisPage } from "./AnalysisPage";

vi.mock("cytoscape", () => ({
  default: () => ({ on: vi.fn(), destroy: vi.fn(), nodes: () => ({ forEach: vi.fn() }) }),
}));
afterEach(() => vi.unstubAllGlobals());

const FINDING = {
  id: 3,
  title: "Pola balasan serupa",
  status: "DRAFT",
  confidence: "LOW",
  synthetic_data: true,
  platform: "x",
  created_by: "analis",
  created_at: "2026-10-17T01:00:00Z",
  supersedes: null,
  superseded_by: null,
  tier: 4,
  tier_label: "Temuan",
  category: "reviewed_finding",
  category_label: "Temuan yang telah ditinjau",
};

function open(role: InvestigationDetail["my_role"], runs: unknown[], tab = "responses") {
  mockApi({
    "GET /api/investigations/1/": () => ({ body: detail(role) }),
    "GET /api/investigations/1/analysis-runs/": () => ({ body: { results: runs } }),
    "GET /api/investigations/1/findings/": () => ({ body: { results: [FINDING] } }),
  });
  return render(
    <MemoryRouter initialEntries={[`/investigations/1/analysis?tab=${tab}`]}>
      <Routes>
        <Route path="/investigations/:id/analysis" element={<AnalysisPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("AnalysisPage", () => {
  it("tanpa analisis: menjelaskan cara menjalankannya, tanpa angka palsu", async () => {
    open("OWNER", []);
    expect(await screen.findByText(/Belum ada analisis klasifikasi respons/)).toBeInTheDocument();
    expect(screen.getByText("manage.py run_analyses")).toBeInTheDocument();
  });

  it("menampilkan tiga kategori secara konsisten dan keempat tab", async () => {
    open("OWNER", []);
    await screen.findByText(/Belum ada analisis/);
    for (const name of ["Respons", "Jaringan", "Profil akun", "Temuan"]) {
      expect(screen.getByRole("tab", { name })).toBeInTheDocument();
    }
    expect(screen.getAllByText("Fakta observasi").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Hasil mesin").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Temuan yang telah ditinjau").length).toBeGreaterThan(0);
  });

  it("tab temuan: draf tetap ditandai draf dan data sintetis diberi tanda", async () => {
    open("OWNER", [], "findings");
    expect(await screen.findByText(/#3 Pola balasan serupa/)).toBeInTheDocument();
    expect(screen.getByText("Draf temuan (belum ditinjau)")).toBeInTheDocument();
    expect(screen.getByText(/data sintetis/)).toBeInTheDocument();
  });

  it("Pembaca tidak melihat tombol buat temuan", async () => {
    open("VIEWER", [], "findings");
    await screen.findByText(/#3 Pola balasan serupa/);
    expect(screen.queryByRole("button", { name: "Buat temuan baru" })).toBeNull();
  });

  it("Anggota dapat membuka formulir dengan empat sumbu bukti dan empat hipotesis alternatif", async () => {
    open("MEMBER", [], "findings");
    await userEvent.click(await screen.findByRole("button", { name: "Buat temuan baru" }));
    expect(screen.getByRole("form", { name: "Temuan baru" })).toBeInTheDocument();
    for (const axis of ["integrity", "provenance", "completeness", "relevance"]) {
      expect(document.querySelector(`[data-axis="${axis}"]`)).not.toBeNull();
    }
    expect(document.querySelectorAll("[data-alternative]").length).toBe(4);
  });

  it("tidak ada elemen UI bertema skor atau peringkat kecurigaan", async () => {
    open("OWNER", [], "findings");
    await waitFor(() => expect(screen.getByText(/#3 Pola balasan serupa/)).toBeInTheDocument());
    const text = (document.body.textContent ?? "").toLowerCase();
    for (const bad of ["skor", "peringkat", "mencurigakan", "paling curiga", "buzzer score"]) {
      expect(text).not.toContain(bad);
    }
  });
});
