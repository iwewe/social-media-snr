import { render as rtlRender, screen, within } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { coverage, run } from "../test/factories";
import { RunCard } from "./RunCard";

const render = (ui: ReactElement) => rtlRender(<MemoryRouter>{ui}</MemoryRouter>);

describe("RunCard", () => {
  it("menampilkan status, keadaan data, dan pesan ramah", () => {
    render(<RunCard run={run()} />);
    expect(screen.getByText("Selesai")).toHaveAttribute("data-run-status", "COMPLETED");
    expect(screen.getByText("Ada data")).toHaveAttribute("data-state", "has_data");
    expect(screen.getByText("Pemeriksaan selesai")).toBeInTheDocument();
  });

  it("dua angka (ditampilkan platform vs teramati) tampil terpisah", () => {
    const r = run({ coverage: coverage({ platform_displayed_count: 7, observed_reply_count: 4 }) });
    const { container } = render(<RunCard run={r} />);
    expect(container.querySelector('[data-field="displayed"]')).toHaveTextContent("7");
    expect(container.querySelector('[data-field="observed-replies"]')).toHaveTextContent("4");
  });

  it("angka tidak diketahui ditulis 'tidak diketahui', angka nol tetap 0", () => {
    const r = run({
      coverage: coverage({
        platform_displayed_count: null,
        observed_reply_count: 0,
        pagination_complete: null,
      }),
    });
    const { container } = render(<RunCard run={r} />);
    expect(container.querySelector('[data-field="displayed"]')).toHaveTextContent(
      "tidak diketahui",
    );
    expect(container.querySelector('[data-field="observed-replies"]')).toHaveTextContent(/^0$/);
    expect(container.querySelector('[data-field="pagination"]')).toHaveTextContent(
      "tidak diketahui",
    );
  });

  it("paginasi tidak lengkap ditandai", () => {
    const { container } = render(
      <RunCard run={run({ coverage: coverage({ pagination_complete: false }) })} />,
    );
    expect(container.querySelector('[data-field="pagination"]')).toHaveTextContent("tidak lengkap");
  });

  it("run tanpa cakupan tidak menampilkan angka palsu", () => {
    const { container } = render(<RunCard run={run({ coverage: null })} />);
    expect(screen.getByText("Cakupan belum tercatat.")).toBeInTheDocument();
    expect(container.querySelector("dl.coverage")).toBeNull();
  });

  it("pesan galat memakai role alert beserta langkah yang disarankan", () => {
    const r = run({
      status: "ACCESS_RESTRICTED",
      data_state: "access_failed",
      coverage: null,
      reconciliation: null,
      messages: [
        {
          code: "access_restricted",
          level: "error",
          title: "Akses ditolak",
          detail: "Platform menolak akses.",
          action: "Pastikan jalur akses sah.",
        },
      ],
    });
    render(<RunCard run={r} />);
    const alert = screen.getByRole("alert");
    expect(within(alert).getByText("Akses ditolak")).toBeInTheDocument();
    expect(within(alert).getByText("Pastikan jalur akses sah.")).toBeInTheDocument();
    expect(screen.getByText("Gagal mengakses data")).toBeInTheDocument();
    expect(screen.queryByText("Tidak ada data")).toBeNull();
  });

  it("pesan info/peringatan bukan alert", () => {
    render(
      <RunCard
        run={run({
          messages: [{ code: "a", level: "warning", title: "Parsial", detail: "d", action: null }],
        })}
      />,
    );
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByRole("note")).toHaveAttribute("data-level", "warning");
  });

  it("ringkasan perubahan antar-run memakai istilah yang tidak menyebut terhapus", () => {
    const r = run({
      reconciliation: {
        state: "DONE",
        counts: { NEW: 2, NOT_OBSERVED: 1, UNCHANGED: 0 },
        baseline_run_count: 1,
      },
    });
    const { container } = render(<RunCard run={r} />);
    const text = container.querySelector(".reconciliation")!.textContent!;
    expect(text).toContain("Baru: 2");
    expect(text).toContain("Tidak teramati kali ini: 1");
    expect(text).not.toContain("Tidak berubah");
    expect(text.toLowerCase()).not.toContain("hapus");
  });

  it("rekonsiliasi yang belum selesai tidak menampilkan ringkasan", () => {
    const { container } = render(<RunCard run={run({ reconciliation: null })} />);
    expect(container.querySelector(".reconciliation")).toBeNull();
  });

  it.each(["BLOCKED", "ERROR", "SKIPPED"])(
    "rekonsiliasi berstatus %s tidak menampilkan ringkasan 'tidak ada perubahan'",
    (state) => {
      const r = run({ reconciliation: { state, counts: {}, baseline_run_count: 0 } });
      const { container } = render(<RunCard run={r} />);
      expect(container.querySelector(".reconciliation")).toBeNull();
    },
  );

  it("detail teknis memuat keterbatasan mentah, collector, dan sumber", () => {
    const r = run({
      limitations: [{ code: "TIMEOUT", message: "melampaui batas", capability: null }],
    });
    const { container } = render(<RunCard run={r} />);
    const details = container.querySelector("details.technical")!;
    expect(details.textContent).toContain("TIMEOUT");
    expect(details.textContent).toContain("melampaui batas");
    expect(details.textContent).toContain("fixture-dataset 1");
    expect(details.textContent).toContain("synthetic_fixture");
  });

  it("teks respons dari platform tidak pernah dirender di kartu run", () => {
    const { container } = render(<RunCard run={run()} />);
    expect(container.textContent).not.toMatch(/balasan sintetis/i);
  });

  it("menautkan ke halaman respons mentah untuk run yang sudah final", () => {
    render(<RunCard run={run({ id: 42 })} />);
    expect(screen.getByRole("link", { name: /Lihat respons mentah dan bukti/ })).toHaveAttribute(
      "href",
      "/inspections/42",
    );
  });

  it("tidak menautkan saat run masih berjalan atau bila diminta tanpa tautan", () => {
    render(<RunCard run={run({ status: "RUNNING", data_state: "in_progress" })} />);
    expect(screen.queryByRole("link")).toBeNull();
    render(<RunCard run={run()} linkToDetail={false} />);
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("run gagal diambil tidak menampilkan '0 teramati' yang bisa dibaca 'tidak ada balasan'", () => {
    const r = run({
      status: "UNSUPPORTED",
      data_state: "access_failed",
      coverage: coverage({
        observed_reply_count: 0,
        observed_object_count: 0,
        platform_displayed_count: null,
        pagination_complete: null,
      }),
    });
    const { container } = render(<RunCard run={r} />);
    expect(container.querySelector('[data-field="observed-replies"]')).toHaveTextContent(
      "tidak diambil",
    );
    expect(container.querySelector('[data-field="observed-objects"]')).toHaveTextContent(
      "tidak diambil",
    );
    expect(container.querySelector('[data-field="observed-replies"]')).not.toHaveTextContent(/^0$/);
  });

  it("run selesai dengan nol balasan tetap menulis 0 (itu pengamatan yang sah)", () => {
    const r = run({
      data_state: "no_data",
      coverage: coverage({ observed_reply_count: 0, platform_displayed_count: 0 }),
    });
    const { container } = render(<RunCard run={r} />);
    expect(container.querySelector('[data-field="observed-replies"]')).toHaveTextContent(/^0$/);
  });
});
