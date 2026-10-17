import { Link } from "react-router-dom";

import type { RunMessage, RunSummary } from "../api/types";
import {
  RECONCILIATION_LABELS,
  STATUS_LABELS,
  formatCount,
  formatTime,
} from "../inspection/labels";
import { DataStateBadge } from "./DataStateBadge";

function Message({ message }: { message: RunMessage }) {
  return (
    <div
      className="message"
      data-level={message.level}
      role={message.level === "error" ? "alert" : "note"}
    >
      <strong>{message.title}</strong>
      <p>{message.detail}</p>
      {message.action && <p className="action">{message.action}</p>}
    </div>
  );
}

function paginationText(value: boolean | null): string {
  if (value === null) return "tidak diketahui";
  return value ? "lengkap" : "tidak lengkap";
}

/** Satu run: status, keadaan data, pesan ramah, cakupan (dua angka terpisah), detail teknis. */
export function RunCard({ run, linkToDetail = true }: { run: RunSummary; linkToDetail?: boolean }) {
  const cov = run.coverage;
  // Pengambilan gagal: "0 teramati" mudah terbaca sebagai "tidak ada balasan"; tulis apa adanya.
  const observed = (n: number | null) =>
    run.data_state === "access_failed" ? "tidak diambil (pengambilan gagal)" : formatCount(n);
  const counts = run.reconciliation?.state === "DONE" ? run.reconciliation.counts : null;
  return (
    <div className="run" data-status={run.status} aria-label={`Run ${run.sequence}`}>
      <header className="row">
        <strong>Run #{run.sequence}</strong>
        <span className="badge" data-run-status={run.status}>
          {STATUS_LABELS[run.status]}
        </span>
        <DataStateBadge state={run.data_state} />
        <span className="muted">{formatTime(run.finished_at ?? run.created_at)}</span>
      </header>

      {run.messages.map((m) => (
        <Message key={m.code} message={m} />
      ))}

      {cov ? (
        <dl className="coverage">
          <dt>Ditampilkan platform</dt>
          <dd data-field="displayed">{formatCount(cov.platform_displayed_count)}</dd>
          <dt>Balasan unik teramati</dt>
          <dd data-field="observed-replies">{observed(cov.observed_reply_count)}</dd>
          <dt>Objek unik teramati</dt>
          <dd data-field="observed-objects">{observed(cov.observed_object_count)}</dd>
          <dt>Paginasi</dt>
          <dd data-field="pagination">{paginationText(cov.pagination_complete)}</dd>
        </dl>
      ) : (
        <p className="muted">Cakupan belum tercatat.</p>
      )}

      {counts && (
        <p className="reconciliation">
          Dibanding pemeriksaan sebelumnya:{" "}
          {Object.entries(counts)
            .filter(([, n]) => n > 0)
            .map(([key, n]) => `${RECONCILIATION_LABELS[key] ?? key}: ${n}`)
            .join(", ") || "tidak ada perubahan"}
        </p>
      )}

      {linkToDetail && run.data_state !== "in_progress" && (
        <p>
          <Link to={`/inspections/${run.id}`}>Lihat respons mentah dan bukti</Link>
        </p>
      )}

      <details className="technical">
        <summary>Detail teknis</summary>
        <ul>
          <li>Dimulai: {formatTime(run.started_at)}</li>
          <li>
            Diminta oleh {run.requested_by}; kemampuan: {run.requested.join(", ")}
          </li>
          <li>
            Pengambil data:{" "}
            {run.collector ? `${run.collector.name} ${run.collector.version}` : "belum tercatat"}
            {run.source_method ? ` (sumber: ${run.source_method})` : ""}
          </li>
          {run.limitations.map((l) => (
            <li key={`${l.code}-${l.message}`}>
              <code>{l.code}</code>: {l.message}
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}
