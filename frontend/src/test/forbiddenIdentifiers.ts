/**
 * Pemeriksa identifier terlarang untuk kode frontend (WP-0.6). Padanan frontend dari
 * tests/architecture/arch_checker.py. PRD bagian 1 dan FR-079: tidak ada skor atau vonis otomatis
 * "buzzer", "bot", akun bayaran, atau koordinasi. Teks yang tampil ke pengguna (string) dan
 * komentar tidak diperiksa; yang diperiksa adalah identifier kode.
 */

export const FORBIDDEN_WORDS: readonly (readonly string[])[] = [
  ["buzzer"],
  ["botscore"],
  ["bot", "score"],
  ["bot", "probability"],
  ["is", "bot"],
  ["paid", "account"],
  ["coordination", "score"],
  ["coordination", "verdict"],
];

export function words(identifier: string): string[] {
  return (identifier.match(/[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+/g) ?? []).map((w) => w.toLowerCase());
}

export function forbiddenIn(identifier: string): readonly string[] | null {
  const ws = words(identifier);
  for (const seq of FORBIDDEN_WORDS) {
    if (seq.length === 1) {
      if (ws.some((w) => w.startsWith(seq[0]))) return seq;
    } else {
      for (let i = 0; i + seq.length <= ws.length; i++) {
        if (seq.every((s, j) => ws[i + j] === s)) return seq;
      }
    }
  }
  return null;
}

/** Karakter yang, bila mendahului "/", menandakan awal literal regex (bukan pembagian). */
const REGEX_PRECEDERS = new Set([
  "(",
  ",",
  "=",
  ":",
  "[",
  "!",
  "&",
  "|",
  "?",
  "{",
  "}",
  ";",
  "+",
  "-",
  "*",
  "%",
  "<",
  ">",
  "~",
  "^",
]);

function startsRegex(out: string): boolean {
  const prev = out.trimEnd();
  if (prev === "") return true;
  if (REGEX_PRECEDERS.has(prev[prev.length - 1])) return true;
  return /(?:^|[^A-Za-z0-9_$])(?:return|typeof|case|void|in|of)$/.test(prev);
}

/** Buang komentar serta isi string/template/regex literal; sisakan kode. */
export function stripNonCode(source: string): string {
  let out = "";
  let i = 0;
  while (i < source.length) {
    const c = source[i];
    const next = source[i + 1];
    if (c === "/" && next === "/") {
      while (i < source.length && source[i] !== "\n") i++;
    } else if (c === "/" && next === "*") {
      i += 2;
      while (i < source.length && !(source[i] === "*" && source[i + 1] === "/")) i++;
      i += 2;
    } else if (c === "/" && startsRegex(out)) {
      i++;
      let inClass = false;
      while (i < source.length && (inClass || source[i] !== "/") && source[i] !== "\n") {
        if (source[i] === "\\") i++;
        else if (source[i] === "[") inClass = true;
        else if (source[i] === "]") inClass = false;
        i++;
      }
      i++;
      while (i < source.length && /[a-z]/i.test(source[i])) i++;
      out += '""';
    } else if (c === '"' || c === "'" || c === "`") {
      const quote = c;
      i++;
      while (i < source.length && source[i] !== quote) {
        if (source[i] === "\\") i++;
        i++;
      }
      i++;
      out += '""';
    } else {
      out += c;
      i++;
    }
  }
  return out;
}

export interface Finding {
  identifier: string;
  words: readonly string[];
}

export function findForbidden(source: string): Finding[] {
  const identifiers = stripNonCode(source).match(/[A-Za-z_$][A-Za-z0-9_$]*/g) ?? [];
  const findings: Finding[] = [];
  for (const identifier of new Set(identifiers)) {
    const hit = forbiddenIn(identifier);
    if (hit) findings.push({ identifier, words: hit });
  }
  return findings;
}
