import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../../api/client";
import { errorText } from "../../api/errorText";
import type { ObservationRef, ObservationTrail } from "../../api/types";
import { ALIGNMENT_LABELS, STANCE_LABELS, actorLabel, formatDateTime } from "../../analysis/labels";
import { ErrorMessage } from "../ErrorMessage";
import { CategoryBadge } from "./CategoryBadge";

function Item({ o }: { o: ObservationRef }) {
  return (
    <li>
      <strong>{actorLabel(o.author)}</strong>{" "}
      <span className="muted">{formatDateTime(o.published_at)}</span>
      <div className="note">{o.text ?? <span className="muted">teks tidak tersedia</span>}</div>
    </li>
  );
}

/** Jejak bukti satu klik (FR-005): observasi, rantai induk, artefak, klasifikasi, dan temuan terkait. */
export function ObservationDrawer({
  observationId,
  onClose,
  onOpenFinding,
}: {
  observationId: number;
  onClose: () => void;
  onOpenFinding: (id: number) => void;
}) {
  const [trail, setTrail] = useState<ObservationTrail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<ObservationTrail>(`/api/observations/${observationId}/`)
      .then((t) => {
        setTrail(t);
        setError(null);
      })
      .catch((e: unknown) => setError(errorText(e)));
  }, [observationId]);

  return (
    <aside role="dialog" aria-label="Jejak bukti" className="drawer">
      <div className="drawer-head">
        <h3>Jejak bukti</h3>
        <button type="button" onClick={onClose}>
          Tutup
        </button>
      </div>
      <ErrorMessage error={error} />
      {!trail && !error && <p className="muted">Memuat jejak bukti...</p>}
      {trail && (
        <>
          <p>
            <CategoryBadge category={trail.category} tier={trail.tier} />{" "}
            <span className="muted">
              Pemeriksaan <Link to={`/inspections/${trail.run.id}`}>#{trail.run.sequence}</Link> ·{" "}
              {trail.run.status} · sumber {trail.run.source_method || "tidak tercatat"}
            </span>
          </p>
          <h4>Observasi</h4>
          <ul className="plain">
            <Item o={trail.observation} />
          </ul>
          <h4>Rantai induk (terdekat lebih dulu)</h4>
          {trail.parent_chain.length === 0 ? (
            <p className="muted">Tidak ada induk teramati pada pemeriksaan ini.</p>
          ) : (
            <ol className="plain">
              {trail.parent_chain.map((p) => (
                <Item key={p.id} o={p} />
              ))}
            </ol>
          )}
          <h4>Artefak bukti</h4>
          {trail.artifacts.length === 0 ? (
            <p className="muted">Tidak ada artefak preservasi pada pemeriksaan ini.</p>
          ) : (
            <ul className="plain">
              {trail.artifacts.map((a) => (
                <li key={a.id}>
                  {a.kind} ({a.content_type}, {a.size_bytes} bita) ·{" "}
                  <code>{a.sha256.slice(0, 12)}…</code> ·{" "}
                  {a.last_verification
                    ? `verifikasi hash terakhir: ${a.last_verification.result}`
                    : "belum pernah diverifikasi"}
                </li>
              ))}
            </ul>
          )}
          <h4>Klasifikasi yang berlaku</h4>
          {trail.assessments.length === 0 ? (
            <p className="muted">Belum diklasifikasi.</p>
          ) : (
            <ul className="plain">
              {trail.assessments.map((a) => (
                <li key={a.assessment_id}>
                  <CategoryBadge category={a.category} /> stance{" "}
                  {STANCE_LABELS[a.labels.issue_stance]};{" "}
                  {ALIGNMENT_LABELS[a.labels.target_alignment].toLowerCase()}
                </li>
              ))}
            </ul>
          )}
          <h4>Temuan yang merujuk observasi ini</h4>
          {trail.finding_ids.length === 0 ? (
            <p className="muted">Belum ada.</p>
          ) : (
            <ul className="plain">
              {trail.finding_ids.map((id) => (
                <li key={id}>
                  <button type="button" className="link" onClick={() => onOpenFinding(id)}>
                    Temuan #{id}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </aside>
  );
}
