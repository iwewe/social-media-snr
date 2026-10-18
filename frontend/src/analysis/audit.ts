import type { AuditEvent } from "../api/types";
import { STANCE_LABELS } from "./labels";

/** Kunci yang merujuk objek lain; ditampilkan sebagai tautan, bukan sebagai perubahan nilai. */
export const REFERENCE_KEYS = [
  "assessment_id",
  "finding_id",
  "observation_id",
  "analysis_run_id",
  "analysis_run_ids",
  "proposition_id",
] as const;

export const FIELD_LABELS: Record<string, string> = {
  version: "Versi",
  definition: "Definisi",
  note: "Catatan",
  stances: "Posisi awal",
  issue_stance: "Stance isu",
  target_alignment: "Terhadap yang dibalas",
  expression_sentiment: "Sentimen",
  response_character: "Karakter respons",
  narrative_function: "Fungsi narasi",
  title: "Judul",
  confidence: "Confidence",
  status: "Status",
  observation_count: "Jumlah observasi",
  synthetic_data: "Data sintetis",
};

export interface ChangeRow {
  key: string;
  label: string;
  before: string;
  after: string;
}

export function formatValue(key: string, value: unknown): string {
  if (value === null || value === undefined || value === "") return "(kosong)";
  if (key === "issue_stance" && typeof value === "string") {
    return STANCE_LABELS[value as keyof typeof STANCE_LABELS] ?? value;
  }
  if (typeof value === "boolean") return value ? "ya" : "tidak";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "(kosong)";
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    return entries.length ? entries.map(([k, v]) => `${k}: ${String(v)}`).join(", ") : "(kosong)";
  }
  return String(value);
}

/** Baris perubahan antara `before` dan `after`; kunci rujukan dan nilai yang sama dibuang. */
export function changeRows(event: Pick<AuditEvent, "before" | "after">): ChangeRow[] {
  const before = event.before ?? {};
  const keys = new Set([...Object.keys(before), ...Object.keys(event.after)]);
  const rows: ChangeRow[] = [];
  for (const key of keys) {
    if ((REFERENCE_KEYS as readonly string[]).includes(key)) continue;
    const b = before[key];
    const a = event.after[key];
    if (JSON.stringify(b) === JSON.stringify(a)) continue;
    rows.push({
      key,
      label: FIELD_LABELS[key] ?? key,
      before: event.before === null ? "(baru dibuat)" : formatValue(key, b),
      after: formatValue(key, a),
    });
  }
  return rows;
}

export interface AuditRefs {
  observationId: number | null;
  findingId: number | null;
  assessmentId: number | null;
}

export function auditRefs(event: AuditEvent): AuditRefs {
  const num = (v: unknown) => (typeof v === "number" ? v : null);
  return {
    observationId: num(event.after.observation_id),
    findingId: event.subject_type === "finding" ? event.subject_id : num(event.after.finding_id),
    assessmentId: event.subject_type === "response_assessment" ? event.subject_id : null,
  };
}
