import { useState } from "react";

import { api } from "../../api/client";
import { errorText } from "../../api/errorText";
import type {
  AnalysisRunInfo,
  CoordinationRow,
  EvidenceSuggestion,
  FindingDetail,
} from "../../api/types";
import {
  ALTERNATIVE_KEYS,
  AXIS_LABELS,
  CONFIDENCE_LABELS,
  OUTCOME_LABELS,
  QUALITY_LABELS,
} from "../../analysis/labels";
import { ErrorMessage } from "../ErrorMessage";

const AXES = ["integrity", "provenance", "completeness", "relevance"] as const;
const CONFIDENCES = ["HIGH", "MODERATE", "LOW", "NOT_ASSESSABLE"] as const;

interface Rating {
  level: string;
  reason: string;
  override_reason: string;
}

/** Formulir temuan (baru atau revisi). Server menegakkan plafon confidence dan larangan vonis. */
export function FindingForm({
  investigationId,
  runs,
  selected,
  previous,
  onSaved,
  onCancel,
}: {
  investigationId: number;
  runs: AnalysisRunInfo[];
  selected: CoordinationRow[];
  previous?: FindingDetail;
  onSaved: (id: number) => void;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState(previous?.title ?? "");
  const [statement, setStatement] = useState(previous?.statement ?? "");
  const [interpretation, setInterpretation] = useState(previous?.interpretation ?? "");
  const [runIds, setRunIds] = useState<number[]>(previous ? previous.runs.map((r) => r.id) : []);
  const [extraObs, setExtraObs] = useState("");
  const [ratings, setRatings] = useState<Record<string, Rating>>(
    Object.fromEntries(AXES.map((a) => [a, { level: "", reason: "", override_reason: "" }])),
  );
  const [alts, setAlts] = useState<Record<string, { outcome: string; reasoning: string }>>(
    Object.fromEntries(
      ALTERNATIVE_KEYS.map((k) => [
        k,
        {
          outcome: previous?.alternatives[k]?.outcome ?? "",
          reasoning: previous?.alternatives[k]?.reasoning ?? "",
        },
      ]),
    ),
  );
  const [confidence, setConfidence] = useState<string>(previous?.confidence ?? "LOW");
  const [confidenceReason, setConfidenceReason] = useState(previous?.confidence_reason ?? "");
  const [suggestion, setSuggestion] = useState<EvidenceSuggestion | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const observationIds = (): number[] => {
    const typed = extraObs
      .split(/[,\s]+/)
      .filter(Boolean)
      .map(Number)
      .filter((n) => Number.isInteger(n) && n > 0);
    return [...new Set([...selected.flatMap((r) => r.observation_ids), ...typed])];
  };

  const fetchSuggestion = () => {
    const ids = observationIds();
    if (ids.length === 0) {
      setError("Pilih indikator atau isi ID observasi lebih dulu.");
      return;
    }
    api
      .post<EvidenceSuggestion>(`/api/investigations/${investigationId}/findings/evidence/`, {
        observation_ids: ids,
      })
      .then((s) => {
        setSuggestion(s);
        setError(null);
        setRatings((cur) =>
          Object.fromEntries(
            AXES.map((a) => {
              const sug = s.suggestions[a];
              const keep = cur[a];
              return [
                a,
                keep.level
                  ? keep
                  : {
                      level: sug.level,
                      reason: `Saran sistem: ${sug.reason}`,
                      override_reason: "",
                    },
              ];
            }),
          ),
        );
      })
      .catch((e: unknown) => setError(errorText(e)));
  };

  const toggleRun = (id: number) =>
    setRunIds((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));

  const submit = (e: React.SyntheticEvent) => {
    e.preventDefault();
    const alternatives = Object.fromEntries(
      Object.entries(alts)
        .filter(([, v]) => v.outcome || v.reasoning.trim())
        .map(([k, v]) => [k, { outcome: v.outcome, reasoning: v.reasoning }]),
    );
    const body = {
      analysis_run_ids: runIds,
      indicator_edge_ids: selected.map((r) => r.id),
      observation_ids: observationIds().filter(
        (id) => !selected.some((r) => r.observation_ids.includes(id)),
      ),
      title,
      statement,
      interpretation,
      evidence_ratings: ratings,
      alternatives,
      confidence,
      confidence_reason: confidenceReason,
    };
    setBusy(true);
    const path = previous
      ? `/api/findings/${previous.id}/revise/`
      : `/api/investigations/${investigationId}/findings/`;
    api
      .post<FindingDetail>(path, body)
      .then((f) => onSaved(f.id))
      .catch((err: unknown) => setError(errorText(err)))
      .finally(() => setBusy(false));
  };

  return (
    <form
      onSubmit={submit}
      className="card"
      aria-label={previous ? "Revisi temuan" : "Temuan baru"}
    >
      <h3>{previous ? `Revisi temuan #${previous.id}` : "Temuan baru"}</h3>
      <p className="muted">
        Temuan menggambarkan pola yang terobservasi, bukan vonis tentang operasi berbayar atau aktor
        pengendali. Anda bertanggung jawab atas interpretasi, penilaian bukti, dan pertimbangan
        SEMUA hipotesis alternatif.
      </p>
      <label>
        Judul
        <input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} />
      </label>
      <label>
        Pernyataan pola (deskriptif)
        <textarea
          value={statement}
          onChange={(e) => setStatement(e.target.value)}
          required
          rows={2}
        />
      </label>
      <label>
        Interpretasi
        <textarea
          value={interpretation}
          onChange={(e) => setInterpretation(e.target.value)}
          required
          rows={2}
        />
      </label>
      <fieldset>
        <legend>Analisis yang mendasari</legend>
        {runs.map((r) => (
          <label key={r.id} className="inline">
            <input
              type="checkbox"
              checked={runIds.includes(r.id)}
              onChange={() => toggleRun(r.id)}
            />{" "}
            Run #{r.id} {r.method}
          </label>
        ))}
      </fieldset>
      <p className="muted">
        Indikator terpilih:{" "}
        {selected.length === 0 ? "belum ada" : selected.map((r) => `#${r.id}`).join(", ")}.
      </p>
      <label>
        ID observasi tambahan (pisahkan dengan koma)
        <input value={extraObs} onChange={(e) => setExtraObs(e.target.value)} />
      </label>
      <fieldset>
        <legend>Kualitas bukti (empat sumbu terpisah)</legend>
        <button type="button" onClick={fetchSuggestion}>
          Ambil saran sistem
        </button>
        {suggestion?.facts.synthetic && (
          <p className="message" data-level="warning" role="note">
            Data sintetis: confidence tidak boleh melebihi Rendah.
          </p>
        )}
        {AXES.map((a) => (
          <div key={a} className="row" data-axis={a}>
            <strong>{AXIS_LABELS[a]}</strong>{" "}
            <select
              aria-label={`Level ${AXIS_LABELS[a]}`}
              value={ratings[a].level}
              onChange={(e) =>
                setRatings((c) => ({ ...c, [a]: { ...c[a], level: e.target.value } }))
              }
              required
            >
              <option value="">(pilih)</option>
              {Object.entries(QUALITY_LABELS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
            <input
              aria-label={`Alasan ${AXIS_LABELS[a]}`}
              placeholder="alasan (wajib)"
              value={ratings[a].reason}
              onChange={(e) =>
                setRatings((c) => ({ ...c, [a]: { ...c[a], reason: e.target.value } }))
              }
              required
            />
            <input
              aria-label={`Alasan override ${AXIS_LABELS[a]}`}
              placeholder="alasan override bila lebih baik dari saran"
              value={ratings[a].override_reason}
              onChange={(e) =>
                setRatings((c) => ({ ...c, [a]: { ...c[a], override_reason: e.target.value } }))
              }
            />
            {suggestion && (
              <div className="muted">
                Saran sistem: {QUALITY_LABELS[suggestion.suggestions[a].level]} (
                {suggestion.suggestions[a].reason})
              </div>
            )}
          </div>
        ))}
      </fieldset>
      <fieldset>
        <legend>Hipotesis alternatif (wajib semuanya sebelum disahkan)</legend>
        {ALTERNATIVE_KEYS.map((k) => (
          <div key={k} className="row" data-alternative={k}>
            <strong>{k.replaceAll("_", " ")}</strong>{" "}
            <select
              aria-label={`Hasil ${k}`}
              value={alts[k].outcome}
              onChange={(e) =>
                setAlts((c) => ({ ...c, [k]: { ...c[k], outcome: e.target.value } }))
              }
            >
              <option value="">(belum dinilai)</option>
              {Object.entries(OUTCOME_LABELS).map(([v, label]) => (
                <option key={v} value={v}>
                  {label}
                </option>
              ))}
            </select>
            <input
              aria-label={`Alasan ${k}`}
              placeholder="alasan penilaian"
              value={alts[k].reasoning}
              onChange={(e) =>
                setAlts((c) => ({ ...c, [k]: { ...c[k], reasoning: e.target.value } }))
              }
            />
          </div>
        ))}
      </fieldset>
      <label>
        Confidence (bukan probabilitas)
        <select
          aria-label="Confidence"
          value={confidence}
          onChange={(e) => setConfidence(e.target.value)}
        >
          {CONFIDENCES.map((c) => (
            <option key={c} value={c}>
              {CONFIDENCE_LABELS[c]}
            </option>
          ))}
        </select>
      </label>
      <label>
        Alasan confidence (wajib)
        <textarea
          value={confidenceReason}
          onChange={(e) => setConfidenceReason(e.target.value)}
          required
          rows={2}
        />
      </label>
      <ErrorMessage error={error} />
      <button type="submit" disabled={busy}>
        {previous ? "Simpan revisi" : "Simpan draf temuan"}
      </button>{" "}
      <button type="button" onClick={onCancel}>
        Batal
      </button>
    </form>
  );
}
