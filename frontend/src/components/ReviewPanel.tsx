import { useState } from "react";
import type { FormEvent } from "react";

import { ApiError, api } from "../api/client";
import { errorText } from "../api/errorText";
import type { RunSummary } from "../api/types";
import { formatTime } from "../inspection/labels";
import { ErrorMessage } from "./ErrorMessage";

/**
 * Tinjauan manusia untuk run REVIEW_REQUIRED (FR-026). Mengakui tinjauan memulihkan hasil adapter
 * yang tercatat dan mencatat siapa/kapan/catatan; data run tidak diubah.
 */
export function ReviewPanel({
  run,
  onAcknowledged,
}: {
  run: RunSummary;
  onAcknowledged: () => void;
}) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ack = run.review?.acknowledged ?? null;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/inspections/${run.id}/acknowledge-review/`, { note });
      onAcknowledged();
    } catch (e) {
      setError(errorText(e));
      // Sudah diakui dari tempat lain: tampilkan keadaan terbaru.
      if (e instanceof ApiError && e.code === "not_awaiting_review") onAcknowledged();
    } finally {
      setBusy(false);
    }
  }

  if (ack) {
    return (
      <section aria-label="Tinjauan" className="review">
        <h3>Tinjauan</h3>
        <p>
          Diakui oleh <strong>{ack.by}</strong> pada {formatTime(ack.at)}.
        </p>
        {ack.note ? <p className="note">{ack.note}</p> : <p className="muted">(tanpa catatan)</p>}
      </section>
    );
  }
  if (run.status !== "REVIEW_REQUIRED") return null;

  return (
    <section aria-label="Tinjauan" className="review">
      <h3>Tinjauan diperlukan</h3>
      <p>
        Periksa masalah yang tercantum di atas. Mengakui tinjauan mencatat bahwa Anda sudah
        memeriksanya dan memulihkan hasil pengambil data yang tercatat
        {run.review?.outcome ? ` (${run.review.outcome})` : ""}; data run tidak diubah.
      </p>
      <form onSubmit={submit}>
        <label>
          Catatan tinjauan (opsional)
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
            maxLength={2000}
          />
        </label>
        <ErrorMessage error={error} />
        <button type="submit" disabled={busy}>
          Akui tinjauan
        </button>
      </form>
    </section>
  );
}
