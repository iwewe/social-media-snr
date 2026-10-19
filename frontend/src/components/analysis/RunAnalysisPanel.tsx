import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "../../api/client";
import { errorText } from "../../api/errorText";
import type { AnalysisRunInfo, AnalysisSetup, DatasetInfo } from "../../api/types";
import { METHOD_LABELS, RELATION_LABELS, formatDateTime } from "../../analysis/labels";
import { ErrorMessage } from "../ErrorMessage";

type Method = "m2-rules" | "m3-profile" | "m4-network" | "co-indicators";
const METHODS = Object.keys(METHOD_LABELS) as Method[];
const RELATIONS = ["reply_to", "quote_of", "repost_of", "mentions"];
const POLL_MS = 3000;
const NONE = -1; // pilihan "tanpa konteks" untuk target
// Jendela lebar untuk tombol contoh: mencakup seluruh data; pengguna dapat mempersempitnya.
const WIDE_START = "2000-01-01T00:00";

const usesIssue = (method: Method, propositionId: number): boolean =>
  propositionId !== 0 &&
  (method === "m2-rules" || method === "m3-profile" || method === "m4-network");

const versionLabel = (v: { version: number; text: string }, latest: boolean): string => {
  const text = v.text.trim();
  const preview = text.length > 60 ? `${text.slice(0, 60)}...` : text || "(kosong)";
  return `Versi ${v.version}${latest ? " (terbaru)" : ""}: ${preview}`;
};

const lines = (text: string): string[] =>
  text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
const toIso = (local: string): string => (local ? new Date(`${local}Z`).toISOString() : "");
const nowLocal = (): string => new Date(Date.now() + 86_400_000).toISOString().slice(0, 16);

function Num({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label>
      {label}
      <input
        aria-label={label}
        inputMode="decimal"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

/** Jalankan analisis dari antarmuka (WP-2.9): parameter eksplisit, dijalankan worker, dengan status. */
export function RunAnalysisPanel({
  investigationId,
  canWrite,
  runs,
  onChanged,
}: {
  investigationId: number;
  canWrite: boolean;
  runs: AnalysisRunInfo[];
  onChanged: () => void;
}) {
  const [setup, setSetup] = useState<AnalysisSetup | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [datasetId, setDatasetId] = useState(0);
  const [picked, setPicked] = useState<number[]>([]);
  const [datasetNote, setDatasetNote] = useState("");
  const [method, setMethod] = useState<Method>("m2-rules");
  const [propositionId, setPropositionId] = useState(0);
  const [sourceRunId, setSourceRunId] = useState(0);
  const [pro, setPro] = useState("");
  const [contra, setContra] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [numbers, setNumbers] = useState<Record<string, string>>({});
  const [unknownTime, setUnknownTime] = useState("include");
  const [weighting, setWeighting] = useState("count");
  const [relations, setRelations] = useState<string[]>([]);
  const [betweenness, setBetweenness] = useState(false);
  const [busy, setBusy] = useState(false);
  const [latestContext, setLatestContext] = useState(false);
  // 0 = belum dipilih (memakai versi terbaru); NONE = tanpa konteks (hanya target).
  const [issueVersion, setIssueVersion] = useState(0);
  const [targetVersions, setTargetVersions] = useState<Record<number, number>>({});

  const load = useCallback(
    () =>
      api
        .get<AnalysisSetup>(`/api/investigations/${investigationId}/analysis-setup/`)
        .then((s) => {
          setSetup(s);
          setError(null);
          setDatasetId((cur) => cur || (s.datasets[0]?.id ?? 0));
        })
        .catch((e: unknown) => setError(errorText(e))),
    [investigationId],
  );

  useEffect(() => {
    void load();
  }, [load]);

  const active = runs.some((r) => r.status === "PENDING" || r.status === "RUNNING");
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(onChanged, POLL_MS);
    return () => clearInterval(timer);
  }, [active, onChanged]);

  const dataset: DatasetInfo | undefined = setup?.datasets.find((d) => d.id === datasetId);
  const sources = useMemo(
    () => (setup?.m2_runs ?? []).filter((r) => r.dataset_id === datasetId),
    [setup, datasetId],
  );
  const platformOfPick = setup?.inspection_runs.find((r) => r.id === picked[0])?.platform;
  const needsProposition = method === "m2-rules" || method === "m3-profile";
  const needsSource = method === "m3-profile";
  const stanceView = method === "m4-network";
  // Konteks yang dibekukan: isu dari proposition terpilih; target dari dataset terpilih.
  const issueId = setup?.propositions.find((p) => p.id === propositionId)?.issue.id;
  const issueInfo = usesIssue(method, propositionId)
    ? setup?.issues.find((i) => i.id === issueId)
    : undefined;
  const datasetTargets = (setup?.targets ?? []).filter((t) => dataset?.target_ids.includes(t.id));
  const effectiveIssue = issueInfo ? issueVersion || (issueInfo.versions[0]?.version ?? 0) : 0;
  const effectiveTarget = (t: { id: number; versions: { version: number }[] }) =>
    targetVersions[t.id] ?? t.versions[0]?.version ?? NONE;

  const num = (key: string) => numbers[key] ?? "";
  const setNum = (key: string) => (v: string) => setNumbers((cur) => ({ ...cur, [key]: v }));

  const fillExample = () => {
    if (!setup) return;
    const ex =
      method === "m3-profile"
        ? setup.examples.m3
        : method === "co-indicators"
          ? setup.examples.co
          : {};
    if (method === "m4-network") {
      const m4 = setup.examples.m4;
      setUnknownTime(String(m4.unknown_time));
      setWeighting(String(m4.weighting));
      setRelations(m4.relation_types as string[]);
      setBetweenness(Boolean(m4.compute_betweenness));
      setNumbers(
        Object.fromEntries(
          ["resolution", "seed", "metrics_max_nodes", "stability_seeds"].map((k) => [
            k,
            String(m4[k]),
          ]),
        ),
      );
    } else {
      setNumbers(Object.fromEntries(Object.entries(ex).map(([k, v]) => [k, String(v)])));
    }
    if (method !== "m2-rules") {
      setStart(WIDE_START);
      setEnd(nowLocal());
    }
  };

  const parameters = (): Record<string, unknown> => {
    const n = (k: string) => (num(k).trim() === "" ? null : Number(num(k)));
    if (method === "m2-rules") return { pro_cues: lines(pro), contra_cues: lines(contra) };
    if (method === "m3-profile") {
      return {
        period_start: toIso(start),
        period_end: toIso(end),
        ...Object.fromEntries(
          ["min_responses", "bucket_hours", "min_active_buckets", "narrative_min_texts"].map(
            (k) => [k, n(k)],
          ),
        ),
      };
    }
    if (method === "m4-network") {
      return {
        window_start: toIso(start),
        window_end: toIso(end),
        unknown_time: unknownTime,
        relation_types: relations,
        weighting,
        compute_betweenness: betweenness,
        ...Object.fromEntries(
          ["resolution", "seed", "metrics_max_nodes", "stability_seeds"].map((k) => [k, n(k)]),
        ),
      };
    }
    return {
      window_start: toIso(start),
      window_end: toIso(end),
      ...Object.fromEntries(Object.keys(setup?.examples.co ?? {}).map((k) => [k, n(k)])),
    };
  };

  const submit = (e: React.SyntheticEvent) => {
    e.preventDefault();
    setBusy(true);
    setMessage(null);
    api
      .post<AnalysisRunInfo>(`/api/investigations/${investigationId}/analysis-runs/`, {
        method,
        dataset_id: datasetId,
        proposition_id: propositionId || null,
        source_run_id: sourceRunId || null,
        parameters: parameters(),
        issue_context_version: issueInfo && effectiveIssue ? effectiveIssue : null,
        target_context_versions: Object.fromEntries(
          datasetTargets.map((t) => {
            const v = effectiveTarget(t);
            return [String(t.id), v === NONE ? null : v];
          }),
        ),
      })
      .then((run) => {
        setError(null);
        setMessage(`Analisis #${run.id} dikirim ke worker (status ${run.status}).`);
        onChanged();
      })
      .catch((err: unknown) => setError(errorText(err)))
      .finally(() => setBusy(false));
  };

  const createDataset = () => {
    setBusy(true);
    api
      .post<DatasetInfo>(`/api/investigations/${investigationId}/datasets/`, {
        inspection_run_ids: picked,
        note: datasetNote,
      })
      .then((d) => {
        setPicked([]);
        setDatasetNote("");
        setDatasetId(d.id);
        setMessage(
          `Dataset ${d.number} dibuat dari ${d.inspection_runs} pemeriksaan (${d.observation_count} observasi).`,
        );
        setError(null);
        void load();
      })
      .catch((err: unknown) => setError(errorText(err)))
      .finally(() => setBusy(false));
  };

  const reanalyze = (run: AnalysisRunInfo) => {
    api
      .post<AnalysisRunInfo>(`/api/analysis-runs/${run.id}/reanalyze/`, {
        use_latest_context: latestContext,
      })
      .then((r) => {
        setError(null);
        setMessage(
          `Analisis ulang #${r.id} dikirim (dataset ${r.dataset.number}); run lama tetap utuh.`,
        );
        onChanged();
        void load();
      })
      .catch((err: unknown) => setError(errorText(err)));
  };

  if (!setup)
    return <p className="muted">{error ? <ErrorMessage error={error} /> : "Memuat..."}</p>;

  return (
    <section aria-label="Jalankan analisis">
      <h2>Jalankan analisis</h2>
      <p className="message" data-level="info" role="note">
        {setup.notes.exploratory} Analisis dijalankan oleh worker di latar belakang dan statusnya
        diperbarui otomatis.
      </p>
      <p className="message" data-level="warning" role="note" data-context-note>
        {setup.notes.context}
      </p>
      <ErrorMessage error={error} />
      {message && (
        <p className="message" data-level="info" role="status">
          {message}
        </p>
      )}

      {canWrite ? (
        <>
          <fieldset>
            <legend>1. Dataset (observasi yang dibekukan)</legend>
            {setup.datasets.length === 0 ? (
              <p className="muted">Belum ada dataset. Buat dari pemeriksaan di bawah.</p>
            ) : (
              <label>
                Dataset
                <select
                  aria-label="Dataset"
                  value={datasetId}
                  onChange={(e) => setDatasetId(Number(e.target.value))}
                >
                  {setup.datasets.map((d) => (
                    <option key={d.id} value={d.id}>
                      Dataset {d.number} · {d.platform} · {d.observation_count} observasi ·{" "}
                      {d.inspection_runs} pemeriksaan
                    </option>
                  ))}
                </select>
              </label>
            )}
            <details>
              <summary>Buat dataset baru dari pemeriksaan</summary>
              <p className="muted">Satu dataset hanya memuat satu platform.</p>
              {setup.inspection_runs.length === 0 && (
                <p className="muted">Belum ada pemeriksaan yang selesai di-ingest.</p>
              )}
              <ul className="plain">
                {setup.inspection_runs.map((r) => (
                  <li key={r.id}>
                    <label className="inline">
                      <input
                        type="checkbox"
                        checked={picked.includes(r.id)}
                        disabled={platformOfPick !== undefined && platformOfPick !== r.platform}
                        onChange={() =>
                          setPicked((cur) =>
                            cur.includes(r.id) ? cur.filter((x) => x !== r.id) : [...cur, r.id],
                          )
                        }
                      />{" "}
                      {r.platform} · pemeriksaan #{r.sequence} · {r.target_url}
                    </label>
                  </li>
                ))}
              </ul>
              <label>
                Catatan dataset (opsional)
                <input
                  value={datasetNote}
                  maxLength={500}
                  onChange={(e) => setDatasetNote(e.target.value)}
                />
              </label>{" "}
              <button type="button" disabled={busy || picked.length === 0} onClick={createDataset}>
                Buat dataset
              </button>
            </details>
          </fieldset>

          <form onSubmit={submit} aria-label="Parameter analisis" className="card">
            <fieldset>
              <legend>
                2. Metode dan parameter (semua eksplisit; tidak ada nilai bawaan tersembunyi)
              </legend>
              <label>
                Metode
                <select
                  aria-label="Metode"
                  value={method}
                  onChange={(e) => setMethod(e.target.value as Method)}
                >
                  {METHODS.map((m) => (
                    <option key={m} value={m}>
                      {METHOD_LABELS[m]}
                    </option>
                  ))}
                </select>
              </label>
              {(needsProposition || stanceView) && (
                <label>
                  Proposition{stanceView ? " (opsional: tampilan stance)" : ""}
                  <select
                    aria-label="Proposition"
                    value={propositionId}
                    onChange={(e) => setPropositionId(Number(e.target.value))}
                  >
                    <option value={0}>{stanceView ? "Tanpa tampilan stance" : "(pilih)"}</option>
                    {setup.propositions.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.label}: {p.statement}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {(needsSource || (stanceView && propositionId !== 0)) && (
                <label>
                  Run klasifikasi (M2) sumber
                  <select
                    aria-label="Run M2 sumber"
                    value={sourceRunId}
                    onChange={(e) => setSourceRunId(Number(e.target.value))}
                  >
                    <option value={0}>(pilih)</option>
                    {sources.map((r) => (
                      <option key={r.id} value={r.id}>
                        Run #{r.id} · {formatDateTime(r.created_at)}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {method === "m2-rules" && (
                <>
                  <label>
                    Cue PRO (satu per baris; ditulis analis)
                    <textarea
                      aria-label="Cue pro"
                      rows={3}
                      value={pro}
                      onChange={(e) => setPro(e.target.value)}
                    />
                  </label>
                  <label>
                    Cue KONTRA (satu per baris)
                    <textarea
                      aria-label="Cue kontra"
                      rows={3}
                      value={contra}
                      onChange={(e) => setContra(e.target.value)}
                    />
                  </label>
                  <p className="muted">
                    Aturan setuju/tidak setuju dan karakter respons memakai daftar dasar modul; cue
                    di atas khusus proposition ini.
                  </p>
                </>
              )}
              {method !== "m2-rules" && (
                <>
                  <label>
                    {method === "m3-profile" ? "Periode mulai (UTC)" : "Jendela mulai (UTC)"}
                    <input
                      type="datetime-local"
                      aria-label="Waktu mulai"
                      value={start}
                      onChange={(e) => setStart(e.target.value)}
                    />
                  </label>
                  <label>
                    {method === "m3-profile" ? "Periode akhir (UTC)" : "Jendela akhir (UTC)"}
                    <input
                      type="datetime-local"
                      aria-label="Waktu akhir"
                      value={end}
                      onChange={(e) => setEnd(e.target.value)}
                    />
                  </label>
                </>
              )}
              {method === "m3-profile" &&
                ["min_responses", "bucket_hours", "min_active_buckets", "narrative_min_texts"].map(
                  (k) => <Num key={k} label={k} value={num(k)} onChange={setNum(k)} />,
                )}
              {method === "m4-network" && (
                <>
                  <fieldset>
                    <legend>Jenis relasi</legend>
                    {RELATIONS.map((t) => (
                      <label key={t} className="inline">
                        <input
                          type="checkbox"
                          checked={relations.includes(t)}
                          onChange={() =>
                            setRelations((cur) =>
                              cur.includes(t) ? cur.filter((x) => x !== t) : [...cur, t],
                            )
                          }
                        />{" "}
                        {RELATION_LABELS[t]}
                      </label>
                    ))}
                  </fieldset>
                  <label>
                    Waktu tak diketahui
                    <select
                      aria-label="Waktu tak diketahui"
                      value={unknownTime}
                      onChange={(e) => setUnknownTime(e.target.value)}
                    >
                      <option value="include">Sertakan</option>
                      <option value="exclude">Kecualikan</option>
                    </select>
                  </label>
                  <label>
                    Pembobotan
                    <select
                      aria-label="Pembobotan"
                      value={weighting}
                      onChange={(e) => setWeighting(e.target.value)}
                    >
                      <option value="count">Jumlah Post</option>
                      <option value="binary">Biner</option>
                    </select>
                  </label>
                  <label className="inline">
                    <input
                      type="checkbox"
                      checked={betweenness}
                      onChange={(e) => setBetweenness(e.target.checked)}
                    />{" "}
                    Hitung betweenness
                  </label>
                  {["resolution", "seed", "metrics_max_nodes", "stability_seeds"].map((k) => (
                    <Num key={k} label={k} value={num(k)} onChange={setNum(k)} />
                  ))}
                </>
              )}
              {method === "co-indicators" &&
                Object.keys(setup.examples.co).map((k) => (
                  <Num key={k} label={k} value={num(k)} onChange={setNum(k)} />
                ))}
              {method !== "m2-rules" && (
                <p>
                  <button type="button" onClick={fillExample}>
                    Isi contoh eksplorasi
                  </button>{" "}
                  <span className="muted">
                    Nilai contoh, bukan ambang; jendela waktu lebar mencakup seluruh data. Tetap
                    dikirim eksplisit.
                  </span>
                </p>
              )}
            </fieldset>
            <fieldset data-context-versions>
              <legend>3. Versi konteks yang dibekukan pada analisis ini</legend>
              <p className="muted">
                Default: versi terbaru. Pilih versi lama bila analisis harus mengikuti konteks yang
                berlaku saat itu; pilihan dicatat pada analisis dan jejak audit.
              </p>
              {issueInfo && (
                <label>
                  Konteks isu: {issueInfo.title}
                  <select
                    aria-label="Versi konteks isu"
                    value={effectiveIssue}
                    onChange={(e) => setIssueVersion(Number(e.target.value))}
                  >
                    {issueInfo.versions.map((v, i) => (
                      <option key={v.version} value={v.version}>
                        {versionLabel(v, i === 0)}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {datasetTargets.map((t) => (
                <label key={t.id}>
                  Konteks target: {t.url}
                  <select
                    aria-label={`Versi konteks target ${t.id}`}
                    value={effectiveTarget(t)}
                    onChange={(e) =>
                      setTargetVersions((cur) => ({ ...cur, [t.id]: Number(e.target.value) }))
                    }
                  >
                    {t.versions.map((v, i) => (
                      <option key={v.version} value={v.version}>
                        {versionLabel(v, i === 0)}
                      </option>
                    ))}
                    <option value={NONE}>Tanpa konteks target</option>
                  </select>
                </label>
              ))}
              {!issueInfo && datasetTargets.length === 0 && (
                <p className="muted">Tidak ada konteks yang berlaku untuk pilihan ini.</p>
              )}
            </fieldset>
            <button type="submit" disabled={busy || datasetId === 0 || !dataset}>
              Jalankan analisis
            </button>
          </form>
        </>
      ) : (
        <p className="muted" data-readonly>
          Hanya Anggota yang dapat menjalankan analisis. Daftar di bawah tetap dapat dilihat.
        </p>
      )}

      <h3>Analisis pada investigasi ini</h3>
      {canWrite && (
        <label className="inline">
          <input
            type="checkbox"
            checked={latestContext}
            onChange={(e) => setLatestContext(e.target.checked)}
          />{" "}
          Analisis ulang memakai konteks terbaru
        </label>
      )}
      {runs.length === 0 ? (
        <p className="muted" data-empty>
          Belum ada analisis.
        </p>
      ) : (
        <div className="table-scroll">
          <table aria-label="Daftar analisis">
            <thead>
              <tr>
                <th>Run</th>
                <th>Metode</th>
                <th>Dataset</th>
                <th>Status</th>
                <th>Dibuat</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id} data-run={r.id} data-status={r.status}>
                  <td>#{r.id}</td>
                  <td>{METHOD_LABELS[r.method] ?? r.method}</td>
                  <td>{r.dataset.number}</td>
                  <td>
                    <span className="badge" data-status-badge={r.status}>
                      {r.status}
                    </span>
                    {r.error && <div className="muted">{r.error}</div>}
                  </td>
                  <td>
                    {r.created_by} · {formatDateTime(r.created_at)}
                  </td>
                  <td>
                    {canWrite && r.status === "COMPLETED" && (
                      <button type="button" onClick={() => reanalyze(r)}>
                        Analisis ulang
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
