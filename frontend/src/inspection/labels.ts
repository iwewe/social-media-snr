import type { DataState, RunStatus } from "../api/types";

export const STATUS_LABELS: Record<RunStatus, string> = {
  PENDING: "Menunggu giliran",
  RUNNING: "Sedang berjalan",
  COMPLETED: "Selesai",
  PARTIAL: "Parsial",
  FAILED: "Gagal",
  ACCESS_RESTRICTED: "Akses ditolak",
  UNSUPPORTED: "Belum didukung",
  REVIEW_REQUIRED: "Perlu ditinjau",
};

/** Tiga keadaan wajib (NFR-08): belum diperiksa, tidak ada data, gagal mengakses data. */
export const DATA_STATE_INFO: Record<DataState, { label: string; description: string }> = {
  not_inspected: {
    label: "Belum diperiksa",
    description:
      "Target ini belum pernah diperiksa, jadi belum ada data. Itu berbeda dari 'tidak ada balasan'.",
  },
  in_progress: {
    label: "Sedang diperiksa",
    description: "Pemeriksaan sedang berjalan; hasilnya belum diketahui.",
  },
  has_data: {
    label: "Ada data",
    description: "Pemeriksaan selesai dan balasan berhasil terbaca.",
  },
  no_data: {
    label: "Tidak ada data",
    description:
      "Pemeriksaan berhasil membaca target dan tidak menemukan balasan pada cakupan yang diminta.",
  },
  partial: {
    label: "Data sebagian",
    description:
      "Hanya sebagian yang terbaca. Jumlah yang tampak dapat lebih sedikit dari kenyataan.",
  },
  access_failed: {
    label: "Gagal mengakses data",
    description:
      "Data tidak dapat diambil (ditolak, gagal, atau belum didukung). Ini BUKAN berarti tidak ada balasan.",
  },
  needs_review: {
    label: "Perlu ditinjau",
    description: "Ada data, tetapi masalah penyimpanan perlu diperiksa manusia sebelum dipakai.",
  },
};

export const RECONCILIATION_LABELS: Record<string, string> = {
  NEW: "Baru",
  UNCHANGED: "Tidak berubah",
  MODIFIED: "Berubah",
  NOT_OBSERVED: "Tidak teramati kali ini",
  CONFIRMED_UNAVAILABLE: "Dinyatakan tidak tersedia",
};

export const IN_PROGRESS_STATES: readonly DataState[] = ["in_progress"];

export function formatTime(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString("id-ID") : "belum";
}

/** null = tidak diketahui, ditulis apa adanya (bukan 0). */
export function formatCount(value: number | null | undefined): string {
  return value === null || value === undefined ? "tidak diketahui" : String(value);
}
