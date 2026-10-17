import type { Inspections } from "../hooks/useInspections";
import { ContextHelp } from "../help/ContextHelp";
import { ErrorMessage } from "./ErrorMessage";
import { STATUS_LABELS } from "../inspection/labels";
import { RunCard } from "./RunCard";

/** Tombol Inspect / Inspect Again dan riwayat run. Run terbaru terbuka; yang lama dilipat. */
export function InspectionPanel({
  inspections,
  readOnly = false,
}: {
  inspections: Inspections;
  readOnly?: boolean;
}) {
  const { runs, error, starting, inProgress, start, reload } = inspections;
  const first = runs !== null && runs.length === 0;
  const busy = starting || inProgress;

  return (
    <section aria-label="Inspeksi">
      <div className="row">
        <button
          type="button"
          onClick={() => void start()}
          disabled={readOnly || runs === null || busy}
          title={
            readOnly
              ? "Peran Pembaca tidak dapat menjalankan inspeksi"
              : busy
                ? "Masih ada pemeriksaan yang berjalan"
                : undefined
          }
        >
          {first ? "Inspect" : "Inspect Again"}
        </button>
        <ContextHelp id={first ? "startInspection" : "reinspection"} />
        <ContextHelp id="dataStates" />
        {error && (
          <button type="button" onClick={reload}>
            Muat ulang
          </button>
        )}
      </div>
      {readOnly && <p className="muted">Peran Pembaca: hanya dapat melihat hasil inspeksi.</p>}
      <ErrorMessage error={error} />
      {runs === null && <p className="muted">Memuat riwayat pemeriksaan...</p>}
      {runs !== null && runs.length === 0 && (
        <p className="muted">Belum pernah diperiksa. Tekan Inspect untuk memulai.</p>
      )}
      {runs?.map((run, index) =>
        index === 0 ? (
          <RunCard key={run.id} run={run} />
        ) : (
          <details key={run.id} className="older-run">
            <summary>
              Run #{run.sequence} - {STATUS_LABELS[run.status]}
            </summary>
            <RunCard run={run} />
          </details>
        ),
      )}
    </section>
  );
}
