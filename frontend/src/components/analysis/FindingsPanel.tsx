import { useCallback, useEffect, useState } from "react";

import { api } from "../../api/client";
import { errorText } from "../../api/errorText";
import type {
  AnalysisRunInfo,
  CoordinationRow,
  EvidenceAxis,
  FindingDetail,
  FindingSummary,
} from "../../api/types";
import {
  AXIS_LABELS,
  CONFIDENCE_LABELS,
  FINDING_STATUS_LABELS,
  OUTCOME_LABELS,
  QUALITY_LABELS,
  formatDateTime,
} from "../../analysis/labels";
import { ContextHelp } from "../../help/ContextHelp";
import { ErrorMessage } from "../ErrorMessage";
import { CategoryBadge } from "./CategoryBadge";
import { FindingForm } from "./FindingForm";

function FindingCategory({ f }: { f: FindingSummary }) {
  // Hanya temuan yang sudah disahkan yang berstatus "ditinjau"; draf tetap ditandai sebagai draf.
  if (f.status === "DRAFT") {
    return (
      <CategoryBadge category="machine_result" tier={4} label="Draf temuan (belum ditinjau)" />
    );
  }
  return <CategoryBadge category="reviewed_finding" tier={4} />;
}

export function FindingsPanel({
  investigationId,
  runs,
  canWrite,
  selected,
  focusId,
  onOpenObservation,
  onOpenAudit,
}: {
  investigationId: number;
  runs: AnalysisRunInfo[];
  canWrite: boolean;
  selected: CoordinationRow[];
  focusId: number | null;
  onOpenObservation: (id: number) => void;
  onOpenAudit: (subjectId: number) => void;
}) {
  const [list, setList] = useState<FindingSummary[] | null>(null);
  const [detail, setDetail] = useState<FindingDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<"none" | "new" | "revise">("none");
  const [note, setNote] = useState("");

  const loadList = useCallback(() => {
    api
      .get<{ results: FindingSummary[] }>(`/api/investigations/${investigationId}/findings/`)
      .then((r) => {
        setList(r.results);
        setError(null);
      })
      .catch((e: unknown) => setError(errorText(e)));
  }, [investigationId]);

  const open = useCallback((id: number) => {
    api
      .get<FindingDetail>(`/api/findings/${id}/`)
      .then((d) => {
        setDetail(d);
        setNote("");
        setError(null);
      })
      .catch((e: unknown) => setError(errorText(e)));
  }, []);

  useEffect(loadList, [loadList]);
  useEffect(() => {
    if (focusId !== null) open(focusId);
  }, [focusId, open]);

  const act = (kind: "endorse" | "withdraw") => {
    if (!detail) return;
    api
      .post<FindingDetail>(`/api/findings/${detail.id}/${kind}/`, { note })
      .then((d) => {
        setDetail(d);
        setNote("");
        loadList();
      })
      .catch((e: unknown) => setError(errorText(e)));
  };

  return (
    <section aria-label="Temuan">
      <h2>
        Temuan <ContextHelp id="viewFindings" />
      </h2>
      <ErrorMessage error={error} />
      {canWrite && form === "none" && (
        <p>
          <button type="button" onClick={() => setForm("new")}>
            Buat temuan baru
          </button>{" "}
          <span className="muted">Indikator terpilih dari tab Jaringan: {selected.length}</span>
        </p>
      )}
      {canWrite && form === "new" && (
        <FindingForm
          investigationId={investigationId}
          runs={runs}
          selected={selected}
          onCancel={() => setForm("none")}
          onSaved={(id) => {
            setForm("none");
            loadList();
            open(id);
          }}
        />
      )}
      {canWrite && form === "revise" && detail && (
        <FindingForm
          investigationId={investigationId}
          runs={runs}
          selected={selected}
          previous={detail}
          onCancel={() => setForm("none")}
          onSaved={(id) => {
            setForm("none");
            loadList();
            open(id);
          }}
        />
      )}
      {!list && !error && <p className="muted">Memuat temuan...</p>}
      {list && list.length === 0 && (
        <p className="muted" data-empty>
          Belum ada temuan. Indikator dan klasifikasi hanyalah bahan; temuan baru lahir setelah
          peninjauan manusia.
        </p>
      )}
      {list && list.length > 0 && (
        <ul className="plain" aria-label="Daftar temuan">
          {list.map((f) => (
            <li key={f.id} data-finding={f.id} data-status={f.status}>
              <button type="button" className="link" onClick={() => open(f.id)}>
                #{f.id} {f.title}
              </button>{" "}
              <span className="badge" data-status-badge={f.status}>
                {FINDING_STATUS_LABELS[f.status]}
              </span>{" "}
              <FindingCategory f={f} />{" "}
              <span className="muted">confidence {CONFIDENCE_LABELS[f.confidence]}</span>
              {f.synthetic_data && <span className="badge warning"> data sintetis</span>}
            </li>
          ))}
        </ul>
      )}
      {detail && (
        <article className="card" aria-label="Detail temuan" data-finding-detail={detail.id}>
          <h3>
            #{detail.id} {detail.title} <FindingCategory f={detail} />
          </h3>
          <p>
            <span className="badge" data-status-badge={detail.status}>
              {FINDING_STATUS_LABELS[detail.status]}
            </span>
            {detail.synthetic_data && (
              <span className="badge warning"> data sintetis: hanya uji alur</span>
            )}
            {detail.superseded_by !== null && (
              <>
                {" "}
                digantikan oleh{" "}
                <button
                  type="button"
                  className="link"
                  onClick={() => open(detail.superseded_by as number)}
                >
                  temuan #{detail.superseded_by}
                </button>
              </>
            )}
            {detail.supersedes !== null && (
              <>
                {" "}
                menggantikan{" "}
                <button
                  type="button"
                  className="link"
                  onClick={() => open(detail.supersedes as number)}
                >
                  temuan #{detail.supersedes}
                </button>
              </>
            )}
          </p>
          <p className="message" data-level="info" role="note">
            {detail.notice}
          </p>
          <h4>Pernyataan</h4>
          <p className="note">{detail.statement}</p>
          <h4>Interpretasi</h4>
          <p className="note">{detail.interpretation}</p>
          <h4>Confidence</h4>
          <p>
            <strong>{CONFIDENCE_LABELS[detail.confidence]}</strong> (bukan probabilitas). Alasan:{" "}
            {detail.confidence_reason}
          </p>
          <p className="muted">
            Kelompok bukti independen: {detail.independent_evidence_groups ?? "tidak diketahui"}
          </p>
          <h4>Kualitas bukti</h4>
          <ul className="plain" aria-label="Kualitas bukti">
            {Object.entries(AXIS_LABELS).map(([axis, label]) => {
              const a = detail.evidence_quality[axis] as EvidenceAxis | undefined;
              if (!a) return null;
              return (
                <li key={axis} data-axis={axis}>
                  <strong>{label}</strong>: {QUALITY_LABELS[a.level]} — {a.reason}
                  <div className="muted">
                    Saran sistem:{" "}
                    {QUALITY_LABELS[a.system_suggestion.level] ?? a.system_suggestion.level} (
                    {a.system_suggestion.reason})
                    {a.override_reason ? ` · override: ${a.override_reason}` : ""}
                  </div>
                </li>
              );
            })}
          </ul>
          <h4>Hipotesis alternatif yang dipertimbangkan</h4>
          <ul className="plain" aria-label="Hipotesis alternatif">
            {Object.entries(detail.alternative_titles).map(([key, title]) => {
              const alt = detail.alternatives[key];
              return (
                <li key={key} data-alternative={key}>
                  <strong>{title}</strong>:{" "}
                  {alt ? (
                    `${OUTCOME_LABELS[alt.outcome] ?? alt.outcome} — ${alt.reasoning}`
                  ) : (
                    <span className="muted">belum dinilai</span>
                  )}
                </li>
              );
            })}
          </ul>
          <h4>Tertaut ke</h4>
          <p>
            Analisis: {detail.runs.map((r) => `#${r.id} ${r.method}`).join(", ")} ·{" "}
            {detail.observation_count} observasi · {detail.indicator_ids.length} indikator.{" "}
            {detail.observations.slice(0, 5).map((o) => (
              <button
                key={o.id}
                type="button"
                className="link"
                onClick={() => onOpenObservation(o.id)}
              >
                observasi #{o.id}
              </button>
            ))}
          </p>
          {detail.reviews.length > 0 && (
            <>
              <h4>Tinjauan</h4>
              <ul className="plain">
                {detail.reviews.map((r) => (
                  <li key={r.action}>
                    {r.action === "ENDORSE" ? "Disahkan" : "Ditarik"} oleh {r.reviewer} (
                    {formatDateTime(r.at)}): {r.note}
                  </li>
                ))}
              </ul>
            </>
          )}
          <h4>Sejarah versi</h4>
          <ol className="plain">
            {detail.history.map((h) => (
              <li key={h.id}>
                #{h.id} {FINDING_STATUS_LABELS[h.status]} ({formatDateTime(h.created_at)})
              </li>
            ))}
          </ol>
          {canWrite && (detail.status === "DRAFT" || detail.status === "ENDORSED") && (
            <div className="actions">
              <label>
                Catatan peninjau
                <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} />
              </label>
              {detail.status === "DRAFT" && (
                <button type="button" disabled={note.trim() === ""} onClick={() => act("endorse")}>
                  Sahkan
                </button>
              )}{" "}
              <button type="button" disabled={note.trim() === ""} onClick={() => act("withdraw")}>
                Tarik
              </button>{" "}
              <button type="button" onClick={() => setForm("revise")}>
                Revisi (buat versi baru)
              </button>
            </div>
          )}
          <button type="button" className="link" onClick={() => onOpenAudit(detail.id)}>
            Jejak audit temuan ini
          </button>{" "}
          <button type="button" onClick={() => setDetail(null)}>
            Tutup detail
          </button>
        </article>
      )}
    </section>
  );
}
