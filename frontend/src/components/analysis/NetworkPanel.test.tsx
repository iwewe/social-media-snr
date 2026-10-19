import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  AnalysisRunInfo,
  CoordinationPage,
  CoordinationRow,
  GraphPayload,
} from "../../api/types";
import { mockApi } from "../../test/factories";
import { NetworkPanel } from "./NetworkPanel";

vi.mock("cytoscape", () => ({
  default: () => ({ on: vi.fn(), destroy: vi.fn(), nodes: () => ({ forEach: vi.fn() }) }),
}));
afterEach(() => vi.unstubAllGlobals());

const run = (id: number, datasetId: number, platform: string): AnalysisRunInfo =>
  ({ id, dataset: { id: datasetId, number: datasetId, platform } }) as unknown as AnalysisRunInfo;

const graphFor = (runInfo: AnalysisRunInfo): GraphPayload =>
  ({
    run: runInfo,
    platform: runInfo.dataset.platform,
    nodes: [{ id: 1, label: "a01", actor: { id: 1 }, attributes: {}, metrics: {} }],
    edges: [],
    metrics: {},
    total_nodes: 1,
    truncated: false,
    category: "machine_result",
    tier: 3,
    notice: "",
  }) as unknown as GraphPayload;

const row = {
  id: 7,
  kind: "behavioral_similarity",
  indicator: "CO-02",
  variant: "",
  actor_a: { id: 1, handle: "a01" },
  actor_b: { id: 2, handle: "a02" },
  value: 1,
  support: 2,
  explanation: "x",
  detail: {},
  baseline: {},
  overlaps_with: [],
  observation_ids: [],
  evidence_truncated: false,
  alternative_hypotheses: [],
} as unknown as CoordinationRow;

const coordinationFor = (runInfo: AnalysisRunInfo, platform?: string): CoordinationPage =>
  ({
    run: runInfo,
    platform: platform ?? runInfo.dataset.platform,
    results: [row],
    notice: "",
    alternative_hypotheses: [],
    baseline: {},
    exclusions: {},
    category: "machine_result",
    tier: 3,
  }) as unknown as CoordinationPage;

const X1 = run(1, 10, "x");
const X2 = run(2, 11, "x");
const TT = run(3, 20, "tiktok");
const COX1 = run(11, 10, "x");
const COX2 = run(12, 11, "x");
const COTT = run(13, 20, "tiktok");

function routes(coordination: Record<number, CoordinationPage>) {
  const table: Record<string, () => { body: unknown }> = {};
  for (const r of [X1, X2, TT]) {
    table[`GET /api/analysis-runs/${r.id}/graph/?max_nodes=300`] = () => ({ body: graphFor(r) });
  }
  for (const [id, page] of Object.entries(coordination)) {
    table[`GET /api/analysis-runs/${id}/coordination/?page_size=200`] = () => ({ body: page });
  }
  mockApi(table);
}

const noop = () => undefined;
const renderPanel = (graphRuns: AnalysisRunInfo[], coRuns: AnalysisRunInfo[]) =>
  render(
    <NetworkPanel
      graphRuns={graphRuns}
      coordinationRuns={coRuns}
      selected={new Map()}
      onToggleIndicator={noop}
      onOpenObservation={noop}
      onOpenActor={noop}
    />,
  );

const optionValues = (label: string) =>
  [...(screen.getByLabelText(label) as HTMLSelectElement).options].map((o) => o.value);

describe("NetworkPanel: graf dan indikator tidak mencampur dataset atau platform (FR-081)", () => {
  it("hanya menawarkan run indikator pada dataset yang sama dengan graf aktif", async () => {
    routes({ 11: coordinationFor(COX1) });
    renderPanel([X1, TT], [COX1, COX2, COTT]);
    await screen.findByLabelText("Analisis indikator");
    expect(optionValues("Analisis indikator")).toEqual(["0", "11"]);
    expect(document.querySelector("[data-hidden-coordination]")).toHaveTextContent(
      "2 analisis indikator pada dataset lain tidak ditawarkan",
    );
  });

  it("mengganti graf ke platform lain mengosongkan indikator dan mengganti pilihan yang ditawarkan", async () => {
    routes({ 11: coordinationFor(COX1), 13: coordinationFor(COTT) });
    renderPanel([X1, TT], [COX1, COTT]);
    await userEvent.selectOptions(await screen.findByLabelText("Analisis indikator"), "11");
    await waitFor(() =>
      expect(document.querySelector('[data-legend="similarity"]')).not.toBeNull(),
    );
    await userEvent.selectOptions(screen.getByLabelText("Analisis jaringan"), "3");
    await waitFor(() => expect(optionValues("Analisis indikator")).toEqual(["0", "13"]));
    expect((screen.getByLabelText("Analisis indikator") as HTMLSelectElement).value).toBe("0");
    expect(document.querySelector('[data-legend="similarity"]')).toBeNull();
    expect(screen.queryByText(/Edge kesamaan perilaku \(indikator\)$/)).not.toBeNull();
  });

  it("menolak data indikator yang platformnya tidak cocok dengan graf walau run-nya ditawarkan", async () => {
    routes({ 11: coordinationFor(COX1, "tiktok") }); // muatan tidak konsisten dengan daftar run
    renderPanel([X1], [COX1]);
    await userEvent.selectOptions(await screen.findByLabelText("Analisis indikator"), "11");
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("platform tiktok");
    expect(alert).toHaveTextContent("platform x");
    expect(document.querySelector('[data-legend="similarity"]')).toBeNull();
  });

  it("menolak data indikator dari dataset lain pada platform yang sama", async () => {
    routes({ 11: coordinationFor(COX2) }); // muatan menyebut dataset 11, graf dataset 10
    renderPanel([X1], [COX1]);
    await userEvent.selectOptions(await screen.findByLabelText("Analisis indikator"), "11");
    expect(await screen.findByRole("alert")).toHaveTextContent("dataset yang berbeda");
    expect(document.querySelector('[data-legend="similarity"]')).toBeNull();
  });

  it("tanpa run indikator yang cocok, pilihan indikator tidak muncul sama sekali", async () => {
    routes({});
    renderPanel([TT], [COX1, COX2]);
    await screen.findByLabelText("Filter stance node");
    expect(screen.queryByLabelText("Analisis indikator")).toBeNull();
  });

  it("kembali ke graf semula tidak memunculkan lagi indikator yang dipilih sebelumnya", async () => {
    routes({ 11: coordinationFor(COX1), 13: coordinationFor(COTT) });
    renderPanel([X1, TT], [COX1, COTT]);
    await userEvent.selectOptions(await screen.findByLabelText("Analisis indikator"), "11");
    await waitFor(() =>
      expect(document.querySelector('[data-legend="similarity"]')).not.toBeNull(),
    );
    await userEvent.selectOptions(screen.getByLabelText("Analisis jaringan"), "3");
    await userEvent.selectOptions(screen.getByLabelText("Analisis jaringan"), "1");
    await waitFor(() => expect(optionValues("Analisis indikator")).toEqual(["0", "11"]));
    expect((screen.getByLabelText("Analisis indikator") as HTMLSelectElement).value).toBe("0");
    expect(document.querySelector('[data-legend="similarity"]')).toBeNull();
  });

  it("jawaban terlambat dari run indikator lama tidak menimpa pilihan yang lebih baru", async () => {
    const COX1B = run(14, 10, "x");
    const two = {
      ...coordinationFor(COX1B),
      results: [row, { ...row, id: 8 }],
    } as CoordinationPage;
    let release: (page: CoordinationPage) => void = () => undefined;
    const late = new Promise<CoordinationPage>((resolve) => {
      release = resolve;
    });
    const reply = (body: unknown) =>
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (path: string) => {
        if (path.includes("/analysis-runs/1/graph/")) return reply(graphFor(X1));
        if (path.includes("/analysis-runs/11/coordination/")) return reply(await late);
        if (path.includes("/analysis-runs/14/coordination/")) return reply(two);
        throw new Error(`rute tidak dimock: ${path}`);
      }),
    );
    renderPanel([X1], [COX1, COX1B]);
    const select = await screen.findByLabelText("Analisis indikator");
    await userEvent.selectOptions(select, "11"); // jawabannya ditahan
    await userEvent.selectOptions(select, "14");
    await screen.findByText(/2 edge kesamaan perilaku/);
    release(coordinationFor(COX1)); // jawaban lama tiba terlambat (1 edge)
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(screen.queryByText(/, 1 edge kesamaan perilaku/)).toBeNull();
    expect(screen.getByText(/2 edge kesamaan perilaku/)).toBeInTheDocument();
  });
});
