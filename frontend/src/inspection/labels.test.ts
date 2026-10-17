import { describe, expect, it } from "vitest";

import type { DataState, RunStatus } from "../api/types";
import {
  DATA_STATE_INFO,
  RECONCILIATION_LABELS,
  STATUS_LABELS,
  formatCount,
  formatTime,
} from "./labels";

const STATES = Object.keys(DATA_STATE_INFO) as DataState[];

describe("label keadaan data (NFR-08)", () => {
  it("setiap keadaan punya label dan penjelasan, dan label tidak kembar", () => {
    expect(STATES.sort()).toEqual([
      "access_failed",
      "has_data",
      "in_progress",
      "needs_review",
      "no_data",
      "not_inspected",
      "partial",
    ]);
    const labels = STATES.map((s) => DATA_STATE_INFO[s].label);
    expect(new Set(labels).size).toBe(labels.length);
    for (const s of STATES) expect(DATA_STATE_INFO[s].description.length).toBeGreaterThan(20);
  });

  it("tiga keadaan wajib dibedakan dengan kata yang berbeda", () => {
    expect(DATA_STATE_INFO.not_inspected.label).toBe("Belum diperiksa");
    expect(DATA_STATE_INFO.no_data.label).toBe("Tidak ada data");
    expect(DATA_STATE_INFO.access_failed.label).toBe("Gagal mengakses data");
  });

  it("gagal mengakses tidak pernah dijelaskan sebagai 'tidak ada balasan'", () => {
    expect(DATA_STATE_INFO.access_failed.description).toContain("BUKAN berarti tidak ada balasan");
    expect(DATA_STATE_INFO.not_inspected.description).toContain("berbeda dari 'tidak ada balasan'");
  });

  it("setiap status run punya label", () => {
    const statuses: RunStatus[] = [
      "PENDING",
      "RUNNING",
      "COMPLETED",
      "PARTIAL",
      "FAILED",
      "ACCESS_RESTRICTED",
      "UNSUPPORTED",
      "REVIEW_REQUIRED",
    ];
    for (const s of statuses) expect(STATUS_LABELS[s]).toBeTruthy();
    expect(Object.keys(STATUS_LABELS).sort()).toEqual([...statuses].sort());
  });

  it("status rekonsiliasi NOT_OBSERVED tidak disebut dihapus", () => {
    expect(RECONCILIATION_LABELS.NOT_OBSERVED.toLowerCase()).not.toContain("hapus");
  });
});

describe("format nilai tidak diketahui", () => {
  it("null tampil 'tidak diketahui', 0 tampil 0", () => {
    expect(formatCount(null)).toBe("tidak diketahui");
    expect(formatCount(undefined)).toBe("tidak diketahui");
    expect(formatCount(0)).toBe("0");
    expect(formatCount(7)).toBe("7");
  });

  it("waktu kosong tampil 'belum'", () => {
    expect(formatTime(null)).toBe("belum");
    expect(formatTime("2026-10-17T01:00:00Z")).not.toBe("belum");
  });
});
