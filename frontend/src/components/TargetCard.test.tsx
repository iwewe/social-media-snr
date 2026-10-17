import { act, render as rtlRender, screen, waitFor, within } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Meta, Target, TargetContext } from "../api/types";
import { POLL_MS } from "../hooks/useInspections";
import { latest, mockApi, run, target as baseTarget } from "../test/factories";
import { TargetCard } from "./TargetCard";

const meta: Meta = {
  platforms: [{ value: "x", label: "X" }],
  target_types: [{ value: "post", label: "Posting" }],
  initial_stances: [
    { value: "PRO", label: "PRO" },
    { value: "UNDETERMINED", label: "UNDETERMINED" },
  ],
};

const ctx = (version: number, note: string): TargetContext => ({
  version,
  note,
  created_at: "2026-10-16T05:00:00Z",
  created_by: "analis",
  stances: [{ proposition_id: 1, label: "P1", statement: "Perlu audit", stance: "CONTRA" }],
});

const target = (overrides: Partial<Target> = {}): Target =>
  baseTarget({
    url: "https://twitter.com/u/status/1?s=20",
    context: ctx(1, "  Catatan\nbaris dua  "),
    context_history: [ctx(1, "  Catatan\nbaris dua  ")],
    ...overrides,
  });

const render = (ui: ReactElement) => rtlRender(<MemoryRouter>{ui}</MemoryRouter>);

const LIST = "GET /api/targets/1/inspections/";
const START = "POST /api/targets/1/inspections/";

afterEach(() => {
  delete (globalThis as { jest?: unknown }).jest;
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("TargetCard: konteks", () => {
  beforeEach(() => {
    mockApi({});
  });

  it("menampilkan catatan apa adanya dan posisi awal per proposition", () => {
    render(<TargetCard target={target()} meta={meta} onChanged={() => {}} />);
    const note = document.querySelector("p.note")!;
    expect(note.textContent).toBe("  Catatan\nbaris dua  ");
    expect(screen.getByText("CONTRA")).toBeInTheDocument();
    expect(screen.getByText(/P1:/)).toBeInTheDocument();
  });

  it("menautkan ke URL ternormalisasi dengan rel aman", () => {
    render(<TargetCard target={target()} meta={meta} onChanged={() => {}} />);
    const link = screen.getByRole("link", { name: "https://x.com/u/status/1" });
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("riwayat versi baru muncul bila ada lebih dari satu versi", async () => {
    const t = target({
      context: ctx(2, "Revisi"),
      context_history: [ctx(2, "Revisi"), ctx(1, "Awal")],
    });
    render(<TargetCard target={t} meta={meta} onChanged={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: /riwayat versi \(2\)/ }));
    const history = document.querySelector("ol") as HTMLElement;
    expect(within(history).getByText("Awal")).toBeInTheDocument();
    expect(within(history).getByText("Revisi")).toBeInTheDocument();
  });

  it("menampilkan pemberitahuan konteks belum cukup dari server", () => {
    const t = target({
      notices: [
        {
          code: "context_insufficient",
          level: "info",
          title: "Konteks target belum diisi",
          detail: "Catatan kosong.",
          action: null,
        },
      ],
    });
    render(<TargetCard target={t} meta={meta} onChanged={() => {}} />);
    expect(screen.getByText("Konteks target belum diisi")).toBeInTheDocument();
  });
});

describe("TargetCard: belum pernah diperiksa", () => {
  it("tanpa run: tidak meminta riwayat, menandai 'Belum diperiksa', tombol Inspect aktif", () => {
    const { calls } = mockApi({});
    render(<TargetCard target={target()} meta={meta} onChanged={() => {}} />);
    expect(calls).toEqual([]);
    expect(screen.getByText("Belum diperiksa")).toHaveAttribute("data-state", "not_inspected");
    expect(screen.getByRole("button", { name: "Inspect" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Inspect Again" })).toBeNull();
    expect(screen.getByText(/Belum pernah diperiksa/)).toBeInTheDocument();
    expect(screen.getByLabelText("Petunjuk: Memulai inspeksi")).toBeInTheDocument();
    expect(
      screen.getByLabelText("Petunjuk: Belum diperiksa, tidak ada data, gagal mengakses"),
    ).toBeInTheDocument();
  });
});

describe("TargetCard: menjalankan inspeksi dan polling", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: false });
    // Testing Library hanya menguras timer palsu bila menemukan global `jest`; tanpa ini
    // asyncWrapper-nya menunggu setTimeout nyata dan tes menggantung. Pola resmi untuk vitest.
    (globalThis as { jest?: unknown }).jest = { advanceTimersByTime: vi.advanceTimersByTime };
  });

  const user = () => userEvent.setup({ delay: null });

  it("Inspect membuat run, mengunci tombol, lalu polling sampai selesai", async () => {
    let polls = 0;
    const pending = run({
      status: "PENDING",
      data_state: "in_progress",
      coverage: null,
      reconciliation: null,
      finished_at: null,
      messages: [
        {
          code: "run_pending",
          level: "info",
          title: "Menunggu giliran",
          detail: "d",
          action: null,
        },
      ],
    });
    const done = run();
    const { calls } = mockApi({
      [START]: () => ({ status: 202, body: pending }),
      [LIST]: () => ({ body: [++polls < 2 ? pending : done] }),
    });
    const onChanged = vi.fn();
    render(<TargetCard target={target()} meta={meta} onChanged={onChanged} />);

    await user().click(screen.getByRole("button", { name: "Inspect" }));
    await act(() => vi.advanceTimersByTimeAsync(0)); // biarkan POST selesai
    expect(calls).toEqual([START]);
    expect(screen.getByText("Menunggu giliran", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Inspect Again" })).toBeDisabled();
    expect(screen.getAllByText("Sedang diperiksa")[0]).toHaveAttribute("data-state", "in_progress");

    await act(() => vi.advanceTimersByTimeAsync(POLL_MS)); // masih menunggu
    expect(calls.filter((c) => c === LIST)).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Inspect Again" })).toBeDisabled();
    expect(onChanged).not.toHaveBeenCalled();

    await act(() => vi.advanceTimersByTimeAsync(POLL_MS)); // selesai
    // Lencana kartu target dan lencana run keduanya mengikuti run terbaru.
    expect(screen.getAllByText("Ada data")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Inspect Again" })).toBeEnabled();
    expect(onChanged).toHaveBeenCalledTimes(1);

    await act(() => vi.advanceTimersByTimeAsync(POLL_MS * 5)); // polling berhenti
    expect(calls.filter((c) => c === LIST)).toHaveLength(2);
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it("run yang sedang berjalan saat halaman dibuka langsung dipantau", async () => {
    const running = run({
      status: "RUNNING",
      data_state: "in_progress",
      coverage: null,
      reconciliation: null,
    });
    let n = 0;
    const { calls } = mockApi({
      [LIST]: () => ({ body: [++n < 2 ? running : run({ id: 1 })] }),
    });
    render(
      <TargetCard
        target={target({
          latest_inspection: latest({ status: "RUNNING", data_state: "in_progress" }),
        })}
        meta={meta}
        onChanged={() => {}}
      />,
    );
    await act(() => vi.advanceTimersByTimeAsync(0));
    expect(calls).toEqual([LIST]);
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
    expect(calls).toEqual([LIST, LIST]);
    expect(screen.getByRole("button", { name: "Inspect Again" })).toBeEnabled();
  });

  it("polling berhenti saat komponen dilepas", async () => {
    const running = run({ status: "RUNNING", data_state: "in_progress", coverage: null });
    const { calls } = mockApi({ [LIST]: () => ({ body: [running] }) });
    const view = render(
      <TargetCard
        target={target({
          latest_inspection: latest({ data_state: "in_progress", status: "RUNNING" }),
        })}
        meta={meta}
        onChanged={() => {}}
      />,
    );
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
    const before = calls.length;
    view.unmount();
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS * 5));
    expect(calls).toHaveLength(before);
  });

  it("galat saat polling menghentikan polling dan menawarkan 'Muat ulang'", async () => {
    const running = run({ status: "RUNNING", data_state: "in_progress", coverage: null });
    let fail = false;
    const { calls } = mockApi({
      [LIST]: () =>
        fail ? { status: 500, body: { detail: "Galat server." } } : { body: [running] },
    });
    render(
      <TargetCard
        target={target({
          latest_inspection: latest({ data_state: "in_progress", status: "RUNNING" }),
        })}
        meta={meta}
        onChanged={() => {}}
      />,
    );
    await act(() => vi.advanceTimersByTimeAsync(0));
    fail = true;
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
    expect(screen.getByRole("alert")).toHaveTextContent("Galat server.");
    const n = calls.length;
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS * 4));
    expect(calls).toHaveLength(n); // tidak mengulang tanpa henti
    fail = false;
    await user().click(screen.getByRole("button", { name: "Muat ulang" }));
    expect(calls.length).toBe(n + 1);
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  });

  it("409 'masih berjalan' menampilkan pesan dan memuat keadaan sebenarnya", async () => {
    const running = run({ status: "RUNNING", data_state: "in_progress", coverage: null });
    const { calls } = mockApi({
      [START]: () => ({
        status: 409,
        body: {
          detail: "Target ini masih memiliki pemeriksaan yang berjalan.",
          code: "inspection_in_progress",
        },
      }),
      [LIST]: () => ({ body: [running] }),
    });
    render(<TargetCard target={target()} meta={meta} onChanged={() => {}} />);
    await user().click(screen.getByRole("button", { name: "Inspect" }));
    await act(() => vi.advanceTimersByTimeAsync(0));
    expect(screen.getByRole("alert")).toHaveTextContent("masih memiliki pemeriksaan");
    expect(calls).toEqual([START, LIST]);
    expect(screen.getByRole("button", { name: "Inspect Again" })).toBeDisabled();
  });
});

describe("TargetCard: riwayat dan keadaan data", () => {
  it("run terbaru terbuka dan yang lama dilipat; badge mengikuti run terbaru", async () => {
    const newest = run({
      id: 2,
      sequence: 2,
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
    const older = run({ id: 1, sequence: 1 });
    mockApi({ [LIST]: () => ({ body: [newest, older] }) });
    render(
      <TargetCard
        target={target({
          latest_inspection: latest({
            sequence: 2,
            data_state: "access_failed",
            status: "ACCESS_RESTRICTED",
          }),
        })}
        meta={meta}
        onChanged={() => {}}
      />,
    );
    expect(await screen.findByText("Akses ditolak", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getAllByText("Gagal mengakses data")[0]).toHaveAttribute(
      "data-state",
      "access_failed",
    );
    expect(screen.queryByText("Tidak ada data")).toBeNull();
    const old = document.querySelector("details.older-run") as HTMLDetailsElement;
    expect(old).not.toBeNull();
    expect(old.open).toBe(false);
    expect(old.textContent).toContain("Run #1");
    expect(old.querySelector("summary")!.textContent).toBe("Run #1 - Selesai"); // bukan enum mentah
  });

  it("sebelum riwayat dimuat memakai ringkasan dari server", () => {
    mockApi({ [LIST]: () => ({ body: [run()] }) });
    render(
      <TargetCard
        target={target({ latest_inspection: latest({ data_state: "no_data" }) })}
        meta={meta}
        onChanged={() => {}}
      />,
    );
    expect(screen.getAllByText("Tidak ada data")[0]).toHaveAttribute("data-state", "no_data");
    expect(screen.getByText(/Memuat riwayat/)).toBeInTheDocument();
  });

  it("tombol dinonaktifkan selama riwayat dimuat (sudah ada riwayat: 'Inspect Again')", () => {
    mockApi({ [LIST]: () => ({ body: [run()] }) });
    render(
      <TargetCard
        target={target({ latest_inspection: latest() })}
        meta={meta}
        onChanged={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: "Inspect Again" })).toBeDisabled();
  });
});
