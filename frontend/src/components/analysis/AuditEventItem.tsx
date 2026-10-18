import type { AuditEvent } from "../../api/types";
import { auditRefs, changeRows } from "../../analysis/audit";
import { formatDateTime } from "../../analysis/labels";

/** Satu peristiwa audit: siapa, kapan, apa yang berubah (sebelum/sesudah), alasan, dan tautan ke objeknya. */
export function AuditEventItem({
  event,
  onOpenObservation,
  onOpenFinding,
}: {
  event: AuditEvent;
  onOpenObservation: (id: number) => void;
  onOpenFinding: (id: number) => void;
}) {
  const rows = changeRows(event);
  const refs = auditRefs(event);
  return (
    <li className="card" data-audit-event={event.id} data-action={event.action}>
      <strong>{event.action_label}</strong>{" "}
      <span className="muted">
        {event.subject_type_label} #{event.subject_id} · oleh {event.actor} ·{" "}
        {formatDateTime(event.at)}
      </span>
      {event.reason && (
        <div className="note">
          <strong>Alasan:</strong> {event.reason}
        </div>
      )}
      {rows.length > 0 && (
        <table aria-label="Perubahan">
          <thead>
            <tr>
              <th>Bagian</th>
              <th>Sebelum</th>
              <th>Sesudah</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key} data-field={r.key}>
                <td>{r.label}</td>
                <td>{r.before}</td>
                <td>{r.after}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div>
        {refs.observationId !== null && (
          <button
            type="button"
            className="link"
            onClick={() => onOpenObservation(refs.observationId as number)}
          >
            Buka observasi #{refs.observationId}
          </button>
        )}{" "}
        {refs.findingId !== null && (
          <button
            type="button"
            className="link"
            onClick={() => onOpenFinding(refs.findingId as number)}
          >
            Buka temuan #{refs.findingId}
          </button>
        )}
      </div>
    </li>
  );
}
