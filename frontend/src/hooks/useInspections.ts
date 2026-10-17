import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, api } from "../api/client";
import { errorText } from "../api/errorText";
import type { RunSummary, Target } from "../api/types";

/** Jeda polling saat ada run yang menunggu/berjalan (pilihan antarmuka, bukan batas riset). */
export const POLL_MS = 2000;

export interface Inspections {
  /** null = sedang dimuat. */
  runs: RunSummary[] | null;
  error: string | null;
  starting: boolean;
  inProgress: boolean;
  start: () => Promise<void>;
  reload: () => void;
}

/**
 * Riwayat run satu target + permintaan inspeksi + polling selama ada run yang berjalan.
 * `latest_inspection === null` berarti belum pernah ada run, jadi riwayat kosong tanpa permintaan.
 * Polling berhenti saat run final, saat galat (pengguna dapat memuat ulang), dan saat unmount.
 */
export function useInspections(
  target: Pick<Target, "id" | "latest_inspection">,
  onSettled?: () => void,
): Inspections {
  const [runs, setRuns] = useState<RunSummary[] | null>(
    target.latest_inspection === null ? [] : null,
  );
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const wasInProgress = useRef(false);
  const onSettledRef = useRef(onSettled);
  onSettledRef.current = onSettled;

  const load = useCallback(async () => {
    try {
      const data = await api.get<RunSummary[]>(`/api/targets/${target.id}/inspections/`);
      setRuns(data);
      setError(null);
    } catch (e) {
      setError(errorText(e));
    }
  }, [target.id]);

  useEffect(() => {
    if (target.latest_inspection !== null) void load();
    // Hanya saat target berganti; perubahan ringkasan dari induk tidak perlu memuat ulang.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target.id]);

  const inProgress = runs?.[0]?.data_state === "in_progress";

  useEffect(() => {
    if (inProgress) {
      wasInProgress.current = true;
      const timer = setTimeout(() => void load(), POLL_MS);
      return () => clearTimeout(timer);
    }
    if (wasInProgress.current && runs !== null) {
      wasInProgress.current = false;
      onSettledRef.current?.();
    }
    return undefined;
  }, [inProgress, runs, load]);

  const start = useCallback(async () => {
    setStarting(true);
    setError(null);
    try {
      const run = await api.post<RunSummary>(`/api/targets/${target.id}/inspections/`, {});
      setRuns((current) => [run, ...(current ?? [])]);
    } catch (e) {
      // Sudah ada run yang berjalan (mis. dari tab lain): tampilkan keadaan sebenarnya, lalu
      // pasang kembali pesannya (pemuatan yang berhasil menghapus galat).
      if (e instanceof ApiError && e.code === "inspection_in_progress") await load();
      setError(errorText(e));
    } finally {
      setStarting(false);
    }
  }, [target.id, load]);

  return { runs, error, starting, inProgress, start, reload: () => void load() };
}
