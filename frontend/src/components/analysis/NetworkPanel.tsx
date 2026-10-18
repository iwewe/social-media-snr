import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "../../api/client";
import { errorText } from "../../api/errorText";
import type {
  AnalysisRunInfo,
  CoordinationPage,
  CoordinationRow,
  GraphPayload,
} from "../../api/types";
import {
  buildElements,
  buildLegend,
  edgeSummary,
  similarityTitle,
} from "../../analysis/graphElements";
import {
  INDICATOR_LABELS,
  RELATION_LABELS,
  STANCE_LABELS,
  actorLabel,
} from "../../analysis/labels";
import { queryString } from "../../analysis/query";
import { ContextHelp } from "../../help/ContextHelp";
import { ErrorMessage } from "../ErrorMessage";
import { CategoryBadge } from "./CategoryBadge";
import { GraphCanvas, type GraphSelection } from "./GraphCanvas";

const RELATIONS = ["reply_to", "quote_of", "repost_of", "mentions"] as const;
const INDICATORS = Object.keys(INDICATOR_LABELS);

function toIso(local: string): string {
  return local ? new Date(`${local}Z`).toISOString() : "";
}

export function NetworkPanel({
  graphRuns,
  coordinationRuns,
  selected,
  onToggleIndicator,
  onOpenObservation,
}: {
  graphRuns: AnalysisRunInfo[];
  coordinationRuns: AnalysisRunInfo[];
  selected: Map<number, CoordinationRow>;
  onToggleIndicator: (row: CoordinationRow) => void;
  onOpenObservation: (id: number) => void;
}) {
  const [graphRunId, setGraphRunId] = useState(graphRuns[0]?.id ?? 0);
  const [coRunId, setCoRunId] = useState(0);
  const [types, setTypes] = useState<string[]>([...RELATIONS]);
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const [stance, setStance] = useState("");
  const [maxNodes, setMaxNodes] = useState(300);
  const [indicator, setIndicator] = useState("");
  const [beyond, setBeyond] = useState(false);
  const [minSupport, setMinSupport] = useState("");
  const [graph, setGraph] = useState<GraphPayload | null>(null);
  const [coordination, setCoordination] = useState<CoordinationPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selection, setSelection] = useState<GraphSelection | null>(null);

  useEffect(() => {
    if (!graphRunId) return;
    const qs = queryString({
      relation_types: types.length === RELATIONS.length ? "" : types.join(","),
      since: toIso(since),
      until: toIso(until),
      stance,
      max_nodes: maxNodes,
    });
    api
      .get<GraphPayload>(`/api/analysis-runs/${graphRunId}/graph/${qs}`)
      .then((g) => {
        setGraph(g);
        setError(null);
        setSelection(null);
      })
      .catch((e: unknown) => setError(errorText(e)));
  }, [graphRunId, types, since, until, stance, maxNodes]);

  useEffect(() => {
    if (!coRunId) return;
    const qs = queryString({
      indicator,
      beyond_baseline: beyond ? "true" : "",
      min_support: minSupport,
      page_size: 200,
    });
    api
      .get<CoordinationPage>(`/api/analysis-runs/${coRunId}/coordination/${qs}`)
      .then((c) => setCoordination(c))
      .catch((e: unknown) => setError(errorText(e)));
  }, [coRunId, indicator, beyond, minSupport]);

  const showSimilarity = coRunId !== 0 && coordination !== null;
  const view = useMemo(
    () =>
      graph
        ? buildElements(graph, showSimilarity ? (coordination?.results ?? []) : [], {
            showSimilarity,
          })
        : null,
    [graph, coordination, showSimilarity],
  );
  const legend = useMemo(() => buildLegend({ showSimilarity }), [showSimilarity]);
  const onSelect = useCallback((s: GraphSelection | null) => setSelection(s), []);
  const toggleType = (t: string) =>
    setTypes((cur) => (cur.includes(t) ? cur.filter((x) => x !== t) : [...cur, t]));

  if (graphRuns.length === 0) {
    return (
      <p className="muted" data-empty>
        Belum ada analisis jaringan (M4) pada investigasi ini.
      </p>
    );
  }

  const stability = graph?.metrics.community_detection?.stability;
  const detailNode =
    selection?.kind === "node" ? graph?.nodes.find((n) => n.id === selection.id) : undefined;
  const detailEdge =
    selection?.kind === "interaction" ? graph?.edges.find((e) => e.id === selection.id) : undefined;
  const detailRow =
    selection?.kind === "behavioral_similarity"
      ? coordination?.results.find((r) => r.id === selection.id)
      : undefined;

  return (
    <section aria-label="Jaringan">
      <h2>
        Jaringan <ContextHelp id="viewNetwork" />
      </h2>
      <fieldset className="filters">
        <legend>Sumber dan filter</legend>
        {graphRuns.length > 1 && (
          <label>
            Analisis jaringan
            <select
              aria-label="Analisis jaringan"
              value={graphRunId}
              onChange={(e) => setGraphRunId(Number(e.target.value))}
            >
              {graphRuns.map((r) => (
                <option key={r.id} value={r.id}>
                  Run #{r.id} (dataset {r.dataset.number})
                </option>
              ))}
            </select>
          </label>
        )}
        <fieldset>
          <legend>Jenis relasi interaksi</legend>
          {RELATIONS.map((t) => (
            <label key={t} className="inline">
              <input type="checkbox" checked={types.includes(t)} onChange={() => toggleType(t)} />{" "}
              {RELATION_LABELS[t]}
            </label>
          ))}
        </fieldset>
        <label>
          Sejak (UTC)
          <input
            type="datetime-local"
            aria-label="Sejak"
            value={since}
            onChange={(e) => setSince(e.target.value)}
          />
        </label>
        <label>
          Sampai (UTC)
          <input
            type="datetime-local"
            aria-label="Sampai"
            value={until}
            onChange={(e) => setUntil(e.target.value)}
          />
        </label>
        <label>
          Atribut stance node
          <select
            aria-label="Filter stance node"
            value={stance}
            onChange={(e) => setStance(e.target.value)}
          >
            <option value="">Semua</option>
            {(["PRO", "CONTRA", "MIXED", "UNDETERMINED"] as const).map((s) => (
              <option key={s} value={s}>
                {STANCE_LABELS[s]}
              </option>
            ))}
          </select>
        </label>
        <label>
          Maks. node ditampilkan
          <input
            type="number"
            aria-label="Maksimum node"
            min={1}
            max={2000}
            value={maxNodes}
            onChange={(e) =>
              setMaxNodes(Math.max(1, Math.min(2000, Number(e.target.value) || 300)))
            }
          />
        </label>
        {coordinationRuns.length > 0 && (
          <>
            <label>
              Edge kesamaan perilaku (indikator)
              <select
                aria-label="Analisis indikator"
                value={coRunId}
                onChange={(e) => setCoRunId(Number(e.target.value))}
              >
                <option value={0}>Tidak ditampilkan</option>
                {coordinationRuns.map((r) => (
                  <option key={r.id} value={r.id}>
                    Run #{r.id} (dataset {r.dataset.number})
                  </option>
                ))}
              </select>
            </label>
            {coRunId !== 0 && (
              <>
                <label>
                  Indikator
                  <select
                    aria-label="Filter indikator"
                    value={indicator}
                    onChange={(e) => setIndicator(e.target.value)}
                  >
                    <option value="">Semua</option>
                    {INDICATORS.map((i) => (
                      <option key={i} value={i}>
                        {i} {INDICATOR_LABELS[i]}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Dukungan minimum
                  <input
                    type="number"
                    aria-label="Dukungan minimum"
                    min={1}
                    value={minSupport}
                    onChange={(e) => setMinSupport(e.target.value)}
                  />
                </label>
                <label className="inline">
                  <input
                    type="checkbox"
                    checked={beyond}
                    onChange={(e) => setBeyond(e.target.checked)}
                  />{" "}
                  Hanya yang melampaui baseline
                </label>
              </>
            )}
          </>
        )}
      </fieldset>
      <ErrorMessage error={error} />
      {!graph && !error && <p className="muted">Memuat graf...</p>}
      {graph && view && (
        <>
          <p>
            <CategoryBadge category={graph.category} tier={graph.tier} />{" "}
            <span className="muted">
              Platform {graph.platform}. {graph.nodes.length} dari {graph.total_nodes} node,{" "}
              {graph.edges.length} edge interaksi
              {showSimilarity && coordination
                ? `, ${coordination.results.length} edge kesamaan perilaku`
                : ""}
              .
            </span>
          </p>
          {graph.truncated && (
            <p className="message" data-level="warning" role="note" data-truncated>
              Graf dibatasi {graph.nodes.length} node dari {graph.total_nodes} (yang tertaut paling
              banyak dipertahankan). Persempit filter untuk melihat bagian lain.
            </p>
          )}
          {graph.notice && (
            <p className="message" data-level="info" role="note">
              {graph.notice}
            </p>
          )}
          {stability && (
            <p className="message" data-level="warning" role="note" data-stability>
              Stabilitas komunitas antar-seed: {stability.distinct_partitions} partisi berbeda dari{" "}
              {stability.seeds} seed (indeks Rand rata-rata{" "}
              {stability.mean_rand_index_vs_first.toFixed(2)}, terendah{" "}
              {stability.min_rand_index_vs_first.toFixed(2)}). {stability.note}.
            </p>
          )}
          <div className="graph-layout">
            <GraphCanvas elements={view.elements} onSelect={onSelect} />
            <aside className="graph-side">
              <h3>Legenda</h3>
              <ul className="legend" aria-label="Legenda graf">
                {legend.map((l) => (
                  <li key={l.key} data-legend={l.key}>
                    <span
                      className={`swatch ${l.shape}`}
                      style={{
                        borderColor: l.color,
                        background: l.shape === "node" ? l.color : undefined,
                      }}
                    />{" "}
                    {l.label}
                    {l.note && <div className="muted">{l.note}</div>}
                  </li>
                ))}
              </ul>
              <h3>Detail terpilih</h3>
              {!selection && <p className="muted">Klik node atau edge pada graf.</p>}
              {detailNode && (
                <div data-detail="node">
                  <strong>{detailNode.label}</strong>
                  <div className="muted">
                    ID {detailNode.actor.external_actor_id ?? "tidak diketahui"}
                  </div>
                  <div>
                    Atribut stance (hasil mesin):{" "}
                    {detailNode.attributes.stance_summary
                      ? STANCE_LABELS[detailNode.attributes.stance_summary]
                      : "tidak dinilai"}
                  </div>
                  {detailNode.attributes.stance_counts && (
                    <div className="muted">
                      {Object.entries(detailNode.attributes.stance_counts)
                        .map(([k, v]) => `${k}: ${v}`)
                        .join(", ")}
                    </div>
                  )}
                  <div className="muted">
                    Struktur: derajat masuk {detailNode.metrics.in_degree ?? 0}, keluar{" "}
                    {detailNode.metrics.out_degree ?? 0}
                    {detailNode.metrics.community !== undefined
                      ? `, komunitas ${detailNode.metrics.community}`
                      : ""}{" "}
                    (menggambarkan struktur, bukan penentu pengendali)
                  </div>
                </div>
              )}
              {detailEdge && (
                <div data-detail="interaction">
                  <strong>Edge interaksi</strong>
                  <div>{edgeSummary(detailEdge, graph.nodes)}</div>
                  <div className="muted">
                    Stance respons pembentuk: {JSON.stringify(detailEdge.stance_counts)}
                  </div>
                  <div>
                    Bukti:{" "}
                    {detailEdge.observation_ids.slice(0, 5).map((id) => (
                      <button
                        key={id}
                        type="button"
                        className="link"
                        onClick={() => onOpenObservation(id)}
                      >
                        observasi #{id}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {detailRow && (
                <div data-detail="behavioral_similarity">
                  <strong>Indikator kesamaan perilaku: {similarityTitle(detailRow)}</strong>
                  <div>{detailRow.explanation}</div>
                  <div className="muted">
                    Nilai {detailRow.value}, dukungan {detailRow.support}.{" "}
                    {detailRow.baseline.permutations
                      ? `Baseline: p(maks ≥ nilai) = ${detailRow.baseline.p_max_ge}; ${detailRow.baseline.exceeds_baseline_p95 ? "melampaui" : "tidak melampaui"} persentil 95 baseline.`
                      : "Baseline tidak dihitung."}
                  </div>
                  {detailRow.overlaps_with.length > 0 && (
                    <div className="muted">
                      Berbagi bukti dengan: {detailRow.overlaps_with.join(", ")} (bukan bukti
                      independen)
                    </div>
                  )}
                  <details>
                    <summary>Hipotesis alternatif yang harus dipertimbangkan</summary>
                    <ul>
                      {detailRow.alternative_hypotheses.map((h) => (
                        <li key={h}>{h}</li>
                      ))}
                    </ul>
                  </details>
                  <div>
                    Bukti:{" "}
                    {detailRow.observation_ids.slice(0, 5).map((id) => (
                      <button
                        key={id}
                        type="button"
                        className="link"
                        onClick={() => onOpenObservation(id)}
                      >
                        observasi #{id}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </aside>
          </div>
          <details>
            <summary>Daftar edge interaksi sebagai teks ({graph.edges.length})</summary>
            <ul aria-label="Daftar edge interaksi" className="plain">
              {graph.edges.map((e) => (
                <li key={e.id} data-edge-kind="interaction">
                  {edgeSummary(e, graph.nodes)}
                </li>
              ))}
            </ul>
          </details>
        </>
      )}
      {showSimilarity && coordination && (
        <div>
          <h3>Indikator kesamaan perilaku</h3>
          <p className="message" data-level="info" role="note">
            {coordination.notice}
          </p>
          {coordination.total > coordination.results.length && (
            <p className="muted">
              Menampilkan {coordination.results.length} dari {coordination.total}; persempit filter
              untuk melihat yang lain.
            </p>
          )}
          <div className="table-scroll">
            <table aria-label="Indikator kesamaan perilaku">
              <thead>
                <tr>
                  <th>Pasangan akun</th>
                  <th>Indikator</th>
                  <th>Dukungan</th>
                  <th>Baseline</th>
                  <th>Penjelasan</th>
                  <th>Pilih untuk temuan</th>
                </tr>
              </thead>
              <tbody>
                {coordination.results.map((r) => (
                  <tr key={r.id} data-indicator-row={r.id}>
                    <td>
                      {actorLabel(r.actor_a)} ↔ {actorLabel(r.actor_b)}
                    </td>
                    <td>
                      {similarityTitle(r)}
                      {r.overlaps_with.length > 0 && (
                        <div className="muted">dependen: {r.overlaps_with.join(", ")}</div>
                      )}
                    </td>
                    <td>{r.support}</td>
                    <td>
                      {r.baseline.permutations
                        ? r.baseline.exceeds_baseline_p95
                          ? "melampaui p95"
                          : "tidak melampaui p95"
                        : "tidak dihitung"}
                    </td>
                    <td>{r.explanation}</td>
                    <td>
                      <input
                        type="checkbox"
                        aria-label={`Pilih indikator ${r.id}`}
                        checked={selected.has(r.id)}
                        onChange={() => onToggleIndicator(r)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
