import type {
  Alignment,
  Category,
  ConfidenceLevel,
  FindingStatus,
  IssueStance,
} from "../api/types";

export const CATEGORY_INFO: Record<Category, { label: string; description: string }> = {
  observed_fact: {
    label: "Fakta observasi",
    description: "Data yang teramati dan tersimpan apa adanya; belum ditafsirkan.",
  },
  machine_result: {
    label: "Hasil mesin",
    description:
      "Dihitung otomatis dari data; bukan temuan. Perlu ditinjau manusia dan dapat keliru.",
  },
  human_reviewed: {
    label: "Dikoreksi manusia",
    description:
      "Hasil mesin yang sudah ditinjau dan dikoreksi seorang peninjau (jejaknya tersimpan).",
  },
  reviewed_finding: {
    label: "Temuan yang telah ditinjau",
    description:
      "Interpretasi yang ditulis dan disahkan manusia dengan bukti, ketidakpastian, dan hipotesis alternatif.",
  },
};

export const STANCE_LABELS: Record<IssueStance, string> = {
  PRO: "Pro",
  CONTRA: "Kontra",
  MIXED: "Campuran",
  NEUTRAL: "Netral",
  UNDETERMINED: "Belum dapat ditentukan",
  NOT_RELEVANT: "Tidak relevan",
};

export const ALIGNMENT_LABELS: Record<Alignment, string> = {
  SUPPORT: "Mendukung yang dibalas",
  OPPOSE: "Menentang yang dibalas",
  UNCLEAR: "Tidak jelas",
};

export const SENTIMENT_LABELS: Record<string, string> = {
  POSITIVE: "Positif",
  NEGATIVE: "Negatif",
  NEUTRAL: "Netral",
};

export const FINDING_STATUS_LABELS: Record<FindingStatus, string> = {
  DRAFT: "Draf (belum disahkan)",
  ENDORSED: "Disahkan",
  WITHDRAWN: "Ditarik",
  SUPERSEDED: "Digantikan",
};

export const CONFIDENCE_LABELS: Record<ConfidenceLevel, string> = {
  HIGH: "Tinggi",
  MODERATE: "Sedang",
  LOW: "Rendah",
  NOT_ASSESSABLE: "Tidak dapat dinilai",
};

export const AXIS_LABELS: Record<string, string> = {
  integrity: "Integritas",
  provenance: "Asal-usul",
  completeness: "Kelengkapan",
  relevance: "Relevansi",
};

export const QUALITY_LABELS: Record<string, string> = {
  GOOD: "Baik",
  ACCEPTABLE: "Cukup",
  POOR: "Buruk",
  NOT_ASSESSABLE: "Tidak dapat dinilai",
};

export const OUTCOME_LABELS: Record<string, string> = {
  RULED_OUT: "Disingkirkan",
  NOT_RULED_OUT: "Belum dapat disingkirkan",
  CANNOT_ASSESS: "Tidak dapat dinilai",
};

export const RELATION_LABELS: Record<string, string> = {
  reply_to: "Balasan",
  quote_of: "Kutipan",
  repost_of: "Repost",
  mentions: "Sebutan",
};

export const DIMENSION_LABELS: Record<string, string> = {
  participation: "Partisipasi",
  stance_distribution: "Sebaran stance",
  response_character: "Karakter respons",
  temporal_activity: "Aktivitas waktu",
  target_concentration: "Konsentrasi target",
  narrative_consistency: "Pengulangan teks tersedia",
  activity_evolution: "Perubahan aktivitas",
};

export const METHOD_LABELS: Record<string, string> = {
  "m2-rules": "Klasifikasi respons (M2)",
  "m3-profile": "Profil akun (M3)",
  "m4-network": "Jaringan interaksi (M4)",
  "co-indicators": "Indikator pola perilaku",
};

export const INDICATOR_LABELS: Record<string, string> = {
  "CO-01": "Membalas posting yang sama",
  "CO-02": "Waktu serentak",
  "CO-03": "Teks mirip",
  "CO-04": "Mengamplifikasi objek yang sama",
  "CO-05": "Tautan/frasa sama",
  "CO-06": "Muncul bersama lintas target",
};

export const RESPONSE_CHARACTER_CODES = [
  "RC-01",
  "RC-02",
  "RC-03",
  "RC-04",
  "RC-05",
  "RC-06",
  "RC-07",
  "RC-08",
  "RC-09",
  "RC-10",
] as const;

export const ALTERNATIVE_KEYS = [
  "organic_mobilization",
  "external_event",
  "public_content_copying",
  "sampling_bias",
] as const;

export function actorLabel(
  actor: {
    handle: string | null;
    external_actor_id: string | null;
    id: number;
  } | null,
): string {
  if (!actor) return "tanpa penulis";
  return (
    actor.handle ?? (actor.external_actor_id ? `ID ${actor.external_actor_id}` : `akun ${actor.id}`)
  );
}

export function formatDateTime(value: string | null): string {
  if (!value) return "tidak diketahui";
  return new Date(value).toLocaleString("id-ID", { timeZone: "UTC", hour12: false }) + " UTC";
}
