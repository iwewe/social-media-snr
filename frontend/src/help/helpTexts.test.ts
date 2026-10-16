import { describe, expect, it } from "vitest";

import { HELP, REQUIRED_HELP_IDS } from "./helpTexts";

describe("teks petunjuk (PRD bagian 12)", () => {
  it("tersedia untuk setiap titik yang wajib", () => {
    for (const id of REQUIRED_HELP_IDS) {
      expect(HELP[id].title.trim()).not.toBe("");
      expect(HELP[id].body.trim().length).toBeGreaterThan(40);
    }
  });

  it("issue dibedakan dari proposition", () => {
    const body = HELP.createIssue.body.toLowerCase();
    expect(body).toContain("topik");
    expect(body).toContain("proposition");
    expect(body).toContain("tidak diberi label pro/kontra");
  });

  it("catatan target adalah panduan dan melarang perintah label buzzer", () => {
    const body = HELP.targetNote.body.toLowerCase();
    expect(body).toContain("bukan perintah");
    expect(body).toContain("buzzer");
    expect(body).toContain("tidak memberi vonis");
  });

  it("inspeksi menjelaskan cakupan, batas akses, dan hasil parsial", () => {
    const body = HELP.startInspection.body.toLowerCase();
    expect(body).toContain("cakupan");
    expect(body).toContain("batas akses");
    expect(body).toContain("parsial");
  });

  it("inspeksi ulang menjelaskan objek lama tidak digandakan", () => {
    const body = HELP.reinspection.body.toLowerCase();
    expect(body).toContain("tidak digandakan");
    expect(body).toContain("data baru");
  });

  it("label ketidakpastian menjelaskan UNDETERMINED bukan netral", () => {
    const body = HELP.uncertaintyLabels.body;
    expect(body).toContain("UNDETERMINED");
    expect(body.toLowerCase()).toContain("bukan netral");
  });

  it("tidak menjanjikan skor atau vonis otomatis", () => {
    const all = Object.values(HELP)
      .map((h) => h.body.toLowerCase())
      .join(" ");
    expect(all).not.toMatch(/skor (buzzer|bot)/);
    expect(all).not.toContain("buzzer score");
  });
});
