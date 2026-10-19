import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AnalysisRunInfo, ProfileSummary, ProfilesPage } from "../../api/types";
import { mockApi } from "../../test/factories";
import { ProfilesPanel } from "./ProfilesPanel";

afterEach(() => vi.unstubAllGlobals());

const run = { id: 5 } as AnalysisRunInfo;
const profile = (participation: ProfileSummary["participation"]): ProfileSummary => ({
  id: 1,
  actor: { id: 1, handle: "u1", display_name: null, external_actor_id: "u1" },
  level: "A",
  participation,
  coverage_statement: "Profil Level A: hanya respons akun ini yang teramati.",
  partial_coverage: false,
});
const page = (results: ProfileSummary[]): ProfilesPage =>
  ({ results, total: results.length, page: 1, page_size: 100, notice: "n" }) as ProfilesPage;

function renderWith(participation: ProfileSummary["participation"]) {
  mockApi({
    "GET /api/analysis-runs/5/profiles/?page_size=100": () => ({
      body: page([profile(participation)]),
    }),
  });
  return render(
    <MemoryRouter>
      <ProfilesPanel run={run} />
    </MemoryRouter>,
  );
}

describe("ProfilesPanel: satu Post = satu respons", () => {
  it("menyatakan respons unik dan melaporkan riwayat observasi terpisah", async () => {
    renderWith({
      status: "OK",
      responses: 3,
      observations: 12,
      responses_with_changed_text: 1,
      distinct_targets: 1,
    });
    expect(await screen.findByText(/3 respons unik pada/)).toBeInTheDocument();
    const history = document.querySelector("[data-history]") as HTMLElement;
    expect(history).toHaveTextContent("12 observasi historis; 1 teks berubah");
    expect(history).toHaveTextContent("Pemeriksaan ulang tidak menambah aktivitas");
  });

  it("tanpa riwayat tambahan tidak menampilkan catatan observasi", async () => {
    renderWith({
      status: "OK",
      responses: 3,
      observations: 3,
      responses_with_changed_text: 0,
      distinct_targets: 1,
    });
    expect(await screen.findByText(/3 respons unik pada/)).toBeInTheDocument();
    expect(document.querySelector("[data-history]")).toBeNull();
  });

  it("teks yang berubah saja tetap dilaporkan", async () => {
    renderWith({
      status: "OK",
      responses: 2,
      observations: 2,
      responses_with_changed_text: 2,
      distinct_targets: 1,
    });
    expect(await screen.findByText(/2 teks berubah/)).toBeInTheDocument();
  });
});
