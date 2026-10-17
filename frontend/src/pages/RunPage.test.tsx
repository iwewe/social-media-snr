import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { artifact, mockApi, obsPage, row, run, runDetail } from "../test/factories";
import { RunPage } from "./RunPage";

afterEach(() => vi.unstubAllGlobals());

const DETAIL = "GET /api/inspections/5/";
const OBS = "GET /api/inspections/5/observations/?page=1&page_size=25";

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/inspections/5"]}>
      <Routes>
        <Route path="/inspections/:id" element={<RunPage />} />
        <Route path="/investigations/:id" element={<p>halaman investigasi</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RunPage", () => {
  it("menampilkan ringkasan run, artefak, dan respons mentah", async () => {
    mockApi({
      [DETAIL]: () => ({ body: runDetail({ id: 5, sequence: 3, artifacts: [artifact()] }) }),
      [OBS]: () => ({ body: obsPage([row()]) }),
    });
    renderPage();
    expect(await screen.findByRole("heading", { name: /Run #3/ })).toHaveTextContent(
      "https://x.com/u/status/1",
    );
    expect(screen.getByRole("table", { name: "Artefak" })).toBeInTheDocument();
    expect(await screen.findByRole("table", { name: "Respons mentah" })).toBeInTheDocument();
    expect(screen.getByLabelText("Petunjuk: Melihat respons mentah")).toBeInTheDocument();
  });

  it("tautan kembali menuju investigasi pemilik target", async () => {
    mockApi({
      [DETAIL]: () => ({ body: runDetail({ id: 5 }) }),
      [OBS]: () => ({ body: obsPage([]) }),
    });
    renderPage();
    const back = await screen.findByRole("link", { name: /Kembali ke target/ });
    expect(back).toHaveAttribute("href", "/investigations/9");
  });

  it("run gagal akses: keadaan benar dan daftar kosong tidak menyebut 'tidak ada balasan'", async () => {
    const failed = runDetail({
      id: 5,
      status: "ACCESS_RESTRICTED",
      data_state: "access_failed",
      coverage: null,
      reconciliation: null,
      messages: [
        {
          code: "access_restricted",
          level: "error",
          title: "Akses ditolak",
          detail: "d",
          action: null,
        },
      ],
    });
    mockApi({ [DETAIL]: () => ({ body: failed }), [OBS]: () => ({ body: obsPage([]) }) });
    renderPage();
    expect(await screen.findByText(/Ini bukan berarti tidak ada balasan\./)).toBeInTheDocument();
    expect(screen.getAllByText("Gagal mengakses data").length).toBeGreaterThan(0);
    expect(screen.queryByText("Tidak ada respons pada run ini.")).toBeNull();
  });

  it("run yang perlu ditinjau menampilkan panel; mengakui memuat ulang detail", async () => {
    let acknowledged = false;
    const review = runDetail({
      id: 5,
      status: "REVIEW_REQUIRED",
      data_state: "needs_review",
      review: { reasons: ["mixed_source_methods"], outcome: "COMPLETED", acknowledged: null },
    });
    const done = runDetail({
      id: 5,
      review: {
        reasons: [],
        outcome: "COMPLETED",
        acknowledged: { by: "analis", at: "2026-10-17T02:00:00Z", note: "" },
      },
    });
    const { calls } = mockApi({
      [DETAIL]: () => ({ body: acknowledged ? done : review }),
      [OBS]: () => ({ body: obsPage([]) }),
      "POST /api/inspections/5/acknowledge-review/": () => {
        acknowledged = true;
        return { body: run() };
      },
    });
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Akui tinjauan" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Akui tinjauan" })).toBeNull());
    expect(await screen.findByText("analis", { selector: "strong" })).toBeInTheDocument();
    expect(calls.filter((c) => c === DETAIL)).toHaveLength(2);
  });

  it("run tidak ditemukan menampilkan galat berbahasa Indonesia", async () => {
    mockApi({
      [DETAIL]: () => ({
        status: 404,
        body: { detail: "Data tidak ditemukan.", code: "not_found" },
      }),
    });
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("Data tidak ditemukan.");
  });

  it("kartu run di halaman detail tidak menautkan dirinya sendiri", async () => {
    mockApi({
      [DETAIL]: () => ({ body: runDetail({ id: 5 }) }),
      [OBS]: () => ({ body: obsPage([]) }),
    });
    renderPage();
    await screen.findByRole("heading", { name: /Run #/ });
    expect(screen.queryByRole("link", { name: /Lihat respons mentah/ })).toBeNull();
  });
});
