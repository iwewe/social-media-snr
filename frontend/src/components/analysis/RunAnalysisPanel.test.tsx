import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AnalysisRunInfo, AnalysisSetup } from "../../api/types";
import { mockApi } from "../../test/factories";
import { RunAnalysisPanel } from "./RunAnalysisPanel";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const CO = { sync_window_seconds: 120, permutations: 100, evidence_limit: 50 };
const SETUP: AnalysisSetup = {
  datasets: [
    {
      id: 2,
      number: 2,
      platform: "x",
      observation_count: 40,
      inspection_runs: 2,
      note: "",
      created_at: "2026-10-19T00:00:00Z",
    },
    {
      id: 1,
      number: 1,
      platform: "x",
      observation_count: 20,
      inspection_runs: 1,
      note: "",
      created_at: "2026-10-18T00:00:00Z",
    },
  ],
  inspection_runs: [
    {
      id: 11,
      target_id: 1,
      target_url: "https://x.com/u/status/1",
      platform: "x",
      sequence: 1,
      status: "COMPLETED",
      finished_at: null,
    },
    {
      id: 12,
      target_id: 2,
      target_url: "https://tiktok.com/@u/video/1",
      platform: "tiktok",
      sequence: 1,
      status: "COMPLETED",
      finished_at: null,
    },
  ],
  propositions: [
    { id: 7, label: "P1", statement: "Perlu diaudit.", issue: { id: 1, title: "Isu" } },
  ],
  m2_runs: [
    { id: 31, dataset_id: 2, created_at: "2026-10-19T01:00:00Z" },
    { id: 32, dataset_id: 1, created_at: "2026-10-18T01:00:00Z" },
  ],
  examples: {
    m3: { min_responses: 2, bucket_hours: 24, min_active_buckets: 2, narrative_min_texts: 2 },
    m4: {
      unknown_time: "include",
      relation_types: ["reply_to", "mentions"],
      weighting: "count",
      resolution: 1,
      seed: 1,
      compute_betweenness: true,
      metrics_max_nodes: 1000,
      stability_seeds: 10,
    },
    co: CO,
  },
  notes: {
    exploratory: "Nilai parameter adalah CONTOH.",
    context: "Catatan konteks: TEKSNYA belum dibaca klasifier.",
  },
};

const run = (over: Partial<AnalysisRunInfo> = {}): AnalysisRunInfo =>
  ({
    id: 50,
    method: "m2-rules",
    method_version: "1",
    status: "PENDING",
    created_at: "2026-10-19T02:00:00Z",
    created_by: "anggota",
    dataset: { id: 2, number: 2, platform: "x", observation_count: 40, digest: "d" },
    previous_run: null,
    tier: null,
    ...over,
  }) as AnalysisRunInfo;

const noop = () => undefined;

function setupApi(
  extra: Record<string, (body?: unknown) => { status?: number; body: unknown }> = {},
) {
  return mockApi({
    "GET /api/investigations/1/analysis-setup/": () => ({ body: SETUP }),
    ...extra,
  });
}

describe("RunAnalysisPanel", () => {
  it("menyatakan batas konteks dan sifat contoh sebelum apa pun dijalankan", async () => {
    setupApi();
    render(<RunAnalysisPanel investigationId={1} canWrite runs={[]} onChanged={noop} />);
    expect(await screen.findByText(/CONTOH/)).toBeInTheDocument();
    expect(document.querySelector("[data-context-note]")).toHaveTextContent(
      "TEKSNYA belum dibaca klasifier",
    );
  });

  it("M2: mengirim cue per baris, proposition, dataset terpilih, tanpa nilai tersembunyi", async () => {
    let sent: unknown;
    setupApi({
      "POST /api/investigations/1/analysis-runs/": (body) => {
        sent = body;
        return { status: 202, body: run() };
      },
    });
    const onChanged = vi.fn();
    render(<RunAnalysisPanel investigationId={1} canWrite runs={[]} onChanged={onChanged} />);
    await userEvent.selectOptions(await screen.findByLabelText("Proposition"), "7");
    await userEvent.type(
      screen.getByLabelText("Cue pro"),
      "harus diaudit{enter}  audit harus dilakukan  {enter}",
    );
    await userEvent.type(screen.getByLabelText("Cue kontra"), "tidak perlu diaudit");
    await userEvent.click(screen.getByRole("button", { name: "Jalankan analisis" }));
    await screen.findByText(/Analisis #50 dikirim ke worker/);
    expect(sent).toEqual({
      method: "m2-rules",
      dataset_id: 2,
      proposition_id: 7,
      source_run_id: null,
      parameters: {
        pro_cues: ["harus diaudit", "audit harus dilakukan"],
        contra_cues: ["tidak perlu diaudit"],
      },
    });
    expect(onChanged).toHaveBeenCalled();
  });

  it("M3: sumber M2 hanya yang memakai dataset terpilih; mengganti dataset mengganti pilihannya", async () => {
    setupApi();
    render(<RunAnalysisPanel investigationId={1} canWrite runs={[]} onChanged={noop} />);
    await userEvent.selectOptions(await screen.findByLabelText("Metode"), "m3-profile");
    const values = () =>
      [...(screen.getByLabelText("Run M2 sumber") as HTMLSelectElement).options].map(
        (o) => o.value,
      );
    expect(values()).toEqual(["0", "31"]); // dataset 2 (terbaru) terpilih
    await userEvent.selectOptions(screen.getByLabelText("Dataset"), "1");
    expect(values()).toEqual(["0", "32"]);
  });

  it("indikator: contoh eksplorasi mengisi semua parameter dan dikirim eksplisit", async () => {
    let sent: { parameters: Record<string, unknown> } | undefined;
    setupApi({
      "POST /api/investigations/1/analysis-runs/": (body) => {
        sent = body as typeof sent;
        return { status: 202, body: run({ method: "co-indicators" }) };
      },
    });
    render(<RunAnalysisPanel investigationId={1} canWrite runs={[]} onChanged={noop} />);
    await userEvent.selectOptions(await screen.findByLabelText("Metode"), "co-indicators");
    await userEvent.click(screen.getByRole("button", { name: "Isi contoh eksplorasi" }));
    await userEvent.click(screen.getByRole("button", { name: "Jalankan analisis" }));
    await screen.findByText(/dikirim ke worker/);
    expect(sent?.parameters).toMatchObject(CO);
    expect(String(sent?.parameters.window_start)).toMatch(/^2000-01-01T00:00:00/);
    expect(String(sent?.parameters.window_end)).toMatch(/Z$/);
  });

  it("M4: contoh mengisi relasi dan angka; stance view membutuhkan proposition dan run M2", async () => {
    setupApi();
    render(<RunAnalysisPanel investigationId={1} canWrite runs={[]} onChanged={noop} />);
    await userEvent.selectOptions(await screen.findByLabelText("Metode"), "m4-network");
    expect(screen.queryByLabelText("Run M2 sumber")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Isi contoh eksplorasi" }));
    expect(screen.getByLabelText("seed")).toHaveValue("1");
    expect(screen.getByRole("checkbox", { name: /Balasan/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /Kutipan/ })).not.toBeChecked();
    await userEvent.selectOptions(screen.getByLabelText(/Proposition/), "7");
    expect(screen.getByLabelText("Run M2 sumber")).toBeInTheDocument();
  });

  it("kesalahan server ditampilkan apa adanya dan tidak ada pesan sukses", async () => {
    setupApi({
      "POST /api/investigations/1/analysis-runs/": () => ({
        status: 400,
        body: {
          detail: "parameter wajib tepat: ['contra_cues', 'pro_cues']",
          code: "InvalidParameters",
        },
      }),
    });
    render(<RunAnalysisPanel investigationId={1} canWrite runs={[]} onChanged={noop} />);
    await userEvent.selectOptions(await screen.findByLabelText("Proposition"), "7");
    await userEvent.click(screen.getByRole("button", { name: "Jalankan analisis" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("parameter wajib tepat");
    expect(screen.queryByText(/dikirim ke worker/)).toBeNull();
  });

  it("dataset baru: hanya satu platform yang dapat dipilih dan kiriman memuat id pemeriksaan", async () => {
    let sent: unknown;
    setupApi({
      "POST /api/investigations/1/datasets/": (body) => {
        sent = body;
        return {
          status: 201,
          body: {
            ...SETUP.datasets[0],
            id: 3,
            number: 3,
            inspection_runs: 1,
            observation_count: 5,
          },
        };
      },
    });
    render(<RunAnalysisPanel investigationId={1} canWrite runs={[]} onChanged={noop} />);
    await userEvent.click(await screen.findByText("Buat dataset baru dari pemeriksaan"));
    const x = screen.getByRole("checkbox", { name: /x · pemeriksaan #1/ });
    const tiktok = screen.getByRole("checkbox", { name: /tiktok · pemeriksaan #1/ });
    expect(screen.getByRole("button", { name: "Buat dataset" })).toBeDisabled();
    await userEvent.click(x);
    expect(tiktok).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Buat dataset" }));
    await screen.findByText(/Dataset 3 dibuat dari 1 pemeriksaan \(5 observasi\)/);
    expect(sent).toEqual({ inspection_run_ids: [11], note: "" });
  });

  it("memperbarui status otomatis selama ada analisis berjalan dan berhenti setelah selesai", async () => {
    setupApi();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const onChanged = vi.fn();
    const { rerender } = render(
      <RunAnalysisPanel
        investigationId={1}
        canWrite
        runs={[run({ status: "RUNNING" })]}
        onChanged={onChanged}
      />,
    );
    await screen.findByText("Jalankan analisis", { selector: "h2" });
    await vi.advanceTimersByTimeAsync(3100);
    expect(onChanged).toHaveBeenCalledTimes(1);
    rerender(
      <RunAnalysisPanel
        investigationId={1}
        canWrite
        runs={[run({ status: "COMPLETED" })]}
        onChanged={onChanged}
      />,
    );
    await vi.advanceTimersByTimeAsync(10_000);
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it("daftar menampilkan status dan galat run gagal; analisis ulang hanya untuk yang selesai", async () => {
    let sent: unknown;
    setupApi({
      "POST /api/analysis-runs/52/reanalyze/": (body) => {
        sent = body;
        return {
          status: 202,
          body: run({
            id: 60,
            previous_run: 52,
            dataset: { id: 3, number: 3, platform: "x", observation_count: 9, digest: "e" },
          }),
        };
      },
    });
    const runs = [
      run({ id: 50, status: "FAILED", error: "InvalidParameters: boom" }),
      run({ id: 51, status: "RUNNING" }),
      run({ id: 52, status: "COMPLETED", method: "m3-profile" }),
    ];
    render(<RunAnalysisPanel investigationId={1} canWrite runs={runs} onChanged={noop} />);
    const table = await screen.findByRole("table", { name: "Daftar analisis" });
    expect(table).toHaveTextContent("InvalidParameters: boom");
    expect(screen.getAllByRole("button", { name: "Analisis ulang" })).toHaveLength(1);
    await userEvent.click(screen.getByRole("checkbox", { name: /konteks terbaru/ }));
    await userEvent.click(screen.getByRole("button", { name: "Analisis ulang" }));
    await screen.findByText(/Analisis ulang #60 dikirim \(dataset 3\); run lama tetap utuh/);
    expect(sent).toEqual({ use_latest_context: true });
  });

  it("Pembaca melihat daftar tetapi tidak formulir maupun tombol analisis ulang", async () => {
    setupApi();
    render(
      <RunAnalysisPanel
        investigationId={1}
        canWrite={false}
        runs={[run({ status: "COMPLETED" })]}
        onChanged={noop}
      />,
    );
    expect(
      await screen.findByText(/Hanya Anggota yang dapat menjalankan analisis/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "Parameter analisis" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Analisis ulang" })).toBeNull();
    expect(screen.getByRole("table", { name: "Daftar analisis" })).toBeInTheDocument();
  });

  it("tanpa dataset, tombol jalankan nonaktif dan menyarankan membuat dataset", async () => {
    mockApi({
      "GET /api/investigations/1/analysis-setup/": () => ({ body: { ...SETUP, datasets: [] } }),
    });
    render(<RunAnalysisPanel investigationId={1} canWrite runs={[]} onChanged={noop} />);
    expect(await screen.findByText(/Belum ada dataset/)).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Jalankan analisis" })).toBeDisabled(),
    );
  });
});
