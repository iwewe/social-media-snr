import { describe, expect, it } from "vitest";

import { findForbidden, forbiddenIn, stripNonCode, words } from "./test/forbiddenIdentifiers";

// Seluruh kode sumber frontend sebagai teks mentah (dibaca saat build tes oleh Vite).
const sources = import.meta.glob("./**/*.{ts,tsx}", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

describe("larangan skor/vonis otomatis di kode frontend (PRD bagian 1, FR-079)", () => {
  it("pemindaian mencakup kode aplikasi yang sebenarnya (bukan kosong)", () => {
    const files = Object.keys(sources);
    expect(files.length).toBeGreaterThanOrEqual(20);
    for (const expected of [
      "./api/types.ts",
      "./api/client.ts",
      "./help/helpTexts.ts",
      "./pages/InvestigationPage.tsx",
      "./components/TargetCard.tsx",
    ]) {
      expect(files).toContain(expected);
    }
  });

  it("tidak ada identifier buzzer/bot/koordinasi-skor di kode", () => {
    const offenders: string[] = [];
    for (const [file, source] of Object.entries(sources)) {
      for (const f of findForbidden(source)) offenders.push(`${file}: ${f.identifier}`);
    }
    expect(offenders).toEqual([]);
  });

  it("teks petunjuk boleh menyebut kata buzzer (untuk melarangnya), tetapi bukan sebagai kode", () => {
    const help = sources["./help/helpTexts.ts"];
    expect(help.toLowerCase()).toContain("buzzer"); // ada di teks
    expect(findForbidden(help)).toEqual([]); // tidak ada di identifier
  });
});

describe("pemeriksa identifier frontend (uji diri)", () => {
  it.each([
    "const computeBuzzerScore = () => 1;",
    "interface BotScore { value: number }",
    "if (user.isBot) {}",
    "const x = { paid_account: 1 };",
    "function coordinationVerdict() {}",
    "type BUZZER_LEVEL = 1;",
    "const botProbability = 0.9;",
  ])("terdeteksi: %s", (code) => {
    expect(findForbidden(code).length).toBeGreaterThan(0);
  });

  it.each([
    "const bottom = 1; const robotArm = 2; const both = 3;",
    "const similarityScore = 0.4; const coordinationIndicator = 1;",
    'const label = "Jangan beri label buzzer pada kritik";',
    "// jangan buat buzzer score\nconst x = 1;",
    "/* buzzerScore */ const y = 2;",
    "const t = `skor buzzer ${1 + 1}`;",
    "const botsSeen = 3;",
    "expect(all).not.toMatch(/skor (buzzer|bot)/);",
    "const ok = /buzzer[/]x/i.test(s);",
  ])("tidak dianggap pelanggaran: %s", (code) => {
    expect(findForbidden(code)).toEqual([]);
  });

  it("pembagian tidak dikira regex: kode setelahnya tetap diperiksa", () => {
    expect(findForbidden("const a = b / c; const buzzerScore = 1; const d = e / f;")).toHaveLength(
      1,
    );
    expect(findForbidden("const r = x / 2 / y; if (isBot) {}").map((f) => f.identifier)).toEqual([
      "isBot",
    ]);
  });

  it("memecah kata dengan benar", () => {
    expect(words("computeBuzzerScore")).toEqual(["compute", "buzzer", "score"]);
    expect(words("is_bot_flag")).toEqual(["is", "bot", "flag"]);
    expect(forbiddenIn("bottom")).toBeNull();
    expect(forbiddenIn("isBot")).toEqual(["is", "bot"]);
  });

  it("stripNonCode menangani escape dan komentar dalam string", () => {
    const code = 'const a = "tanda \\" kutip // bukan komentar"; const buzzerScore = 1;';
    expect(findForbidden(code).map((f) => f.identifier)).toEqual(["buzzerScore"]);
    expect(stripNonCode('const s = "x//y"; // buzzer')).not.toContain("buzzer");
  });
});
