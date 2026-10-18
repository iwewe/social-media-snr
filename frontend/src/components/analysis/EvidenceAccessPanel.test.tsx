import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { EvidenceAccessPage, EvidenceAccessRow } from "../../api/types";
import { mockApi } from "../../test/factories";
import { EvidenceAccessPanel } from "./EvidenceAccessPanel";

afterEach(() => vi.unstubAllGlobals());

const row = (over: Partial<EvidenceAccessRow> = {}): EvidenceAccessRow => ({
  id: 3,
  at: "2026-10-19T01:00:00Z",
  user: "pembaca",
  purpose: "download",
  purpose_label: "Unduh isi artefak",
  result: "MATCH",
  artifact: { id: 7, kind: "screenshot", run_id: 2, run_sequence: 1 },
  ...over,
});
const page = (results: EvidenceAccessRow[], count = results.length): EvidenceAccessPage => ({
  count,
  page: 1,
  page_size: 20,
  results,
  notice: "Riwayat ini hanya dapat bertambah.",
});
const renderPanel = () =>
  render(
    <MemoryRouter>
      <EvidenceAccessPanel investigationId={1} />
    </MemoryRouter>,
  );

describe("EvidenceAccessPanel", () => {
  it("menampilkan siapa, keperluan, artefak, dan hasil", async () => {
    mockApi({
      "GET /api/investigations/1/evidence-access/?page=1&page_size=20": () => ({
        body: page([
          row(),
          row({
            id: 2,
            result: "MISMATCH",
            user: "pemilik",
            purpose: "verify",
            purpose_label: "Verifikasi hash satu artefak",
          }),
        ]),
      }),
    });
    renderPanel();
    const table = await screen.findByRole("table", { name: "Riwayat akses bukti" });
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(3);
    expect(within(rows[1]).getByText("pembaca")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Cocok")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Berbeda dari saat disimpan")).toBeInTheDocument();
    expect(within(rows[1]).getByRole("link", { name: "pemeriksaan #1" })).toHaveAttribute(
      "href",
      "/inspections/2",
    );
    expect(screen.getByText(/hanya dapat bertambah/)).toBeInTheDocument();
  });

  it("filter hasil diteruskan ke server dan halaman kembali ke 1", async () => {
    const { calls } = mockApi({
      "GET /api/investigations/1/evidence-access/?page=1&page_size=20": () => ({
        body: page([row()], 45),
      }),
      "GET /api/investigations/1/evidence-access/?page=2&page_size=20": () => ({
        body: { ...page([row()], 45), page: 2 },
      }),
      "GET /api/investigations/1/evidence-access/?page=1&page_size=20&result=MISMATCH": () => ({
        body: page([]),
      }),
    });
    renderPanel();
    await screen.findByText(/45 akses, halaman 1 dari 3/);
    await userEvent.click(screen.getByRole("button", { name: "Berikutnya" }));
    await screen.findByText(/halaman 2 dari 3/);
    await userEvent.selectOptions(screen.getByLabelText("Filter hasil"), "MISMATCH");
    expect(await screen.findByText(/Belum ada akses bukti/)).toBeInTheDocument();
    expect(calls).toContain(
      "GET /api/investigations/1/evidence-access/?page=1&page_size=20&result=MISMATCH",
    );
  });
});
