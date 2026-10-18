import { describe, expect, it } from "vitest";

import type { AuditEvent } from "../api/types";
import { auditRefs, changeRows, formatValue } from "./audit";

const base: AuditEvent = {
  id: 1,
  at: "2026-10-18T01:00:00Z",
  actor: "anggota",
  action: "CLASSIFICATION_REVIEW",
  action_label: "Tinjauan klasifikasi",
  subject_type: "response_assessment",
  subject_type_label: "Klasifikasi respons",
  subject_id: 9,
  before: { assessment_id: 8, issue_stance: "PRO" },
  after: { assessment_id: 9, observation_id: 4, analysis_run_id: 2, issue_stance: "CONTRA" },
  reason: "alasan",
};

describe("changeRows", () => {
  it("hanya memuat nilai yang berubah, bukan kunci rujukan", () => {
    const rows = changeRows(base);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ key: "issue_stance", before: "Pro", after: "Kontra" });
  });

  it("peristiwa baru (before null) menandai sisi sebelum sebagai baru dibuat", () => {
    const rows = changeRows({ before: null, after: { version: 1, definition: "isi" } });
    expect(rows.map((r) => r.key).sort()).toEqual(["definition", "version"]);
    expect(rows.every((r) => r.before === "(baru dibuat)")).toBe(true);
  });

  it("nilai yang sama tidak ditampilkan sebagai perubahan", () => {
    const rows = changeRows({
      before: { version: 1, note: "a", stances: { P1: "PRO" } },
      after: { version: 2, note: "a", stances: { P1: "PRO" } },
    });
    expect(rows.map((r) => r.key)).toEqual(["version"]);
  });

  it("kunci yang hilang di sisi sesudah tampil sebagai kosong", () => {
    const rows = changeRows({ before: { note: "lama" }, after: {} });
    expect(rows).toEqual([{ key: "note", label: "Catatan", before: "lama", after: "(kosong)" }]);
  });
});

describe("formatValue", () => {
  it("memetakan stance ke label, objek ke daftar, boolean ke ya/tidak", () => {
    expect(formatValue("issue_stance", "UNDETERMINED")).toBe("Belum dapat ditentukan");
    expect(formatValue("stances", { P1: "PRO", P2: "CONTRA" })).toBe("P1: PRO, P2: CONTRA");
    expect(formatValue("synthetic_data", true)).toBe("ya");
    expect(formatValue("x", null)).toBe("(kosong)");
    expect(formatValue("response_character", ["RC-01", "RC-02"])).toBe("RC-01, RC-02");
  });
});

describe("auditRefs", () => {
  it("klasifikasi merujuk observasi dan klasifikasi, bukan temuan", () => {
    expect(auditRefs(base)).toEqual({ observationId: 4, findingId: null, assessmentId: 9 });
  });
  it("temuan merujuk dirinya sendiri", () => {
    const e = {
      ...base,
      subject_type: "finding" as const,
      subject_id: 3,
      after: { title: "Pola" },
    };
    expect(auditRefs(e)).toEqual({ observationId: null, findingId: 3, assessmentId: null });
  });
});
