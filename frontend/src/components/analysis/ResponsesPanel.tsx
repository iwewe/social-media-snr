import { useCallback, useEffect, useState } from "react";

import { api } from "../../api/client";
import { errorText } from "../../api/errorText";
import type { AnalysisRunInfo, ResponseRow, ResponsesPage } from "../../api/types";
import {
  ALIGNMENT_LABELS,
  RESPONSE_CHARACTER_CODES,
  SENTIMENT_LABELS,
  STANCE_LABELS,
  actorLabel,
  formatDateTime,
} from "../../analysis/labels";
import { queryString } from "../../analysis/query";
import { ContextHelp } from "../../help/ContextHelp";
import { ErrorMessage } from "../ErrorMessage";
import { CategoryBadge } from "./CategoryBadge";

const PAGE_SIZE = 25;
const STANCES = Object.keys(STANCE_LABELS);
const ALIGNMENTS = Object.keys(ALIGNMENT_LABELS);

interface Filters {
  stance: string;
  alignment: string;
  character: string;
  origin: string;
  needs_review: string;
}
const NO_FILTERS: Filters = {
  stance: "",
  alignment: "",
  character: "",
  origin: "",
  needs_review: "",
};

function Chain({ row }: { row: ResponseRow }) {
  if (row.parent_chain.length === 0) {
    return (
      <span className="muted">
        {row.parent_unknown ? "induk tidak dapat dilacak" : "tanpa induk teramati"}
      </span>
    );
  }
  const [nearest, ...rest] = row.parent_chain;
  return (
    <>
      <div className="note">
        <strong>Dibalas:</strong> {actorLabel(nearest.author)}:{" "}
        {nearest.text ?? <span className="muted">teks tidak tersedia</span>}
        {nearest.stance && <span className="muted"> (stance {STANCE_LABELS[nearest.stance]})</span>}
      </div>
      {rest.length > 0 && (
        <details>
          <summary>Rantai induk lengkap ({row.parent_chain.length})</summary>
          <ol className="plain">
            {row.parent_chain.map((p) => (
              <li key={p.observation_id}>
                {actorLabel(p.author)}: {p.text ?? "teks tidak tersedia"}
              </li>
            ))}
          </ol>
        </details>
      )}
    </>
  );
}

function ReviewForm({
  row,
  onDone,
  onCancel,
}: {
  row: ResponseRow;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [reason, setReason] = useState("");
  const [stance, setStance] = useState("");
  const [alignment, setAlignment] = useState("");
  const [characters, setCharacters] = useState<string[]>(
    row.labels.response_character.map((c) => c.code),
  );
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = (e: React.SyntheticEvent) => {
    e.preventDefault();
    const body: Record<string, unknown> = { reason };
    if (stance) body.issue_stance = stance;
    if (alignment) body.target_alignment = alignment;
    const before = row.labels.response_character.map((c) => c.code).join(",");
    if (characters.slice().sort().join(",") !== before.split(",").sort().join(",")) {
      body.response_character = characters;
    }
    setBusy(true);
    api
      .post(`/api/assessments/${row.assessment_id}/review/`, body)
      .then(onDone)
      .catch((err: unknown) => setError(errorText(err)))
      .finally(() => setBusy(false));
  };

  const toggle = (code: string) =>
    setCharacters((cur) => (cur.includes(code) ? cur.filter((c) => c !== code) : [...cur, code]));

  return (
    <form
      onSubmit={submit}
      aria-label={`Tinjau klasifikasi ${row.assessment_id}`}
      className="card inline-form"
    >
      <p className="muted">
        Koreksi menjadi versi baru; hasil mesin tidak ditimpa dan jejak peninjauan tersimpan.
      </p>
      <label>
        Stance isu
        <select value={stance} onChange={(e) => setStance(e.target.value)}>
          <option value="">(tidak diubah)</option>
          {STANCES.map((s) => (
            <option key={s} value={s}>
              {STANCE_LABELS[s as keyof typeof STANCE_LABELS]}
            </option>
          ))}
        </select>
      </label>
      <label>
        Terhadap yang dibalas
        <select value={alignment} onChange={(e) => setAlignment(e.target.value)}>
          <option value="">(tidak diubah)</option>
          {ALIGNMENTS.map((a) => (
            <option key={a} value={a}>
              {ALIGNMENT_LABELS[a as keyof typeof ALIGNMENT_LABELS]}
            </option>
          ))}
        </select>
      </label>
      <fieldset>
        <legend>Karakter respons</legend>
        {RESPONSE_CHARACTER_CODES.map((code) => (
          <label key={code} className="inline">
            <input
              type="checkbox"
              checked={characters.includes(code)}
              onChange={() => toggle(code)}
            />{" "}
            {code}
          </label>
        ))}
      </fieldset>
      <label>
        Alasan peninjauan (wajib)
        <textarea value={reason} onChange={(e) => setReason(e.target.value)} required rows={2} />
      </label>
      <ErrorMessage error={error} />
      <button type="submit" disabled={busy || reason.trim() === ""}>
        Simpan tinjauan
      </button>{" "}
      <button type="button" onClick={onCancel}>
        Batal
      </button>
    </form>
  );
}

/** Respons terklasifikasi M2 (FR-091): label, rantai induk, status tinjauan, dan tautan bukti. */
export function ResponsesPanel({
  run,
  canReview,
  actorId,
  onClearActor,
  onOpenObservation,
}: {
  run: AnalysisRunInfo;
  canReview: boolean;
  actorId: number | null;
  onClearActor: () => void;
  onOpenObservation: (id: number) => void;
}) {
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ResponsesPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState<number | null>(null);

  const load = useCallback(() => {
    const qs = queryString({ ...filters, actor: actorId, page, page_size: PAGE_SIZE });
    api
      .get<ResponsesPage>(`/api/analysis-runs/${run.id}/responses/${qs}`)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e: unknown) => setError(errorText(e)));
  }, [run.id, filters, actorId, page]);

  useEffect(load, [load]);

  const set = (key: keyof Filters) => (e: React.ChangeEvent<HTMLSelectElement>) => {
    setFilters((f) => ({ ...f, [key]: e.target.value }));
    setPage(1);
  };

  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <section aria-label="Respons terklasifikasi">
      <h2>
        Respons terklasifikasi <ContextHelp id="viewClassifiedResponses" />
      </h2>
      <fieldset className="filters">
        <legend>Filter</legend>
        <label>
          Stance isu
          <select aria-label="Filter stance" value={filters.stance} onChange={set("stance")}>
            <option value="">Semua</option>
            {STANCES.map((s) => (
              <option key={s} value={s}>
                {STANCE_LABELS[s as keyof typeof STANCE_LABELS]}
              </option>
            ))}
          </select>
        </label>
        <label>
          Terhadap yang dibalas
          <select
            aria-label="Filter alignment"
            value={filters.alignment}
            onChange={set("alignment")}
          >
            <option value="">Semua</option>
            {ALIGNMENTS.map((a) => (
              <option key={a} value={a}>
                {ALIGNMENT_LABELS[a as keyof typeof ALIGNMENT_LABELS]}
              </option>
            ))}
          </select>
        </label>
        <label>
          Karakter
          <select
            aria-label="Filter karakter"
            value={filters.character}
            onChange={set("character")}
          >
            <option value="">Semua</option>
            {RESPONSE_CHARACTER_CODES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <label>
          Asal label
          <select aria-label="Filter asal" value={filters.origin} onChange={set("origin")}>
            <option value="">Semua</option>
            <option value="machine">Hasil mesin</option>
            <option value="human">Dikoreksi manusia</option>
          </select>
        </label>
        <label>
          Perlu tinjauan
          <select
            aria-label="Filter perlu tinjauan"
            value={filters.needs_review}
            onChange={set("needs_review")}
          >
            <option value="">Semua</option>
            <option value="true">Perlu ditinjau</option>
            <option value="false">Tidak ditandai</option>
          </select>
        </label>
      </fieldset>
      {actorId !== null && (
        <p data-actor-filter>
          Hanya respons satu akun (dari graf).{" "}
          <button type="button" className="link" onClick={onClearActor}>
            tampilkan semua
          </button>
        </p>
      )}
      <ErrorMessage error={error} />
      {!data && !error && <p className="muted">Memuat respons...</p>}
      {data && (
        <>
          <p className="message" data-level="info" role="note">
            {data.notice}
          </p>
          <p className="muted" aria-live="polite">
            {data.total} respons{data.total > 0 ? `, halaman ${data.page} dari ${pages}` : ""}
          </p>
          {data.results.length === 0 ? (
            <p className="muted" data-empty>
              Tidak ada respons yang cocok dengan filter ini.
            </p>
          ) : (
            <div className="table-scroll">
              <table aria-label="Respons terklasifikasi">
                <thead>
                  <tr>
                    <th>Respons</th>
                    <th>Konteks (yang dibalas)</th>
                    <th>Klasifikasi</th>
                    <th>Status</th>
                    <th>Bukti</th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((row) => (
                    <tr key={row.assessment_id} data-assessment={row.assessment_id}>
                      <td>
                        <strong>{actorLabel(row.observation.author)}</strong>
                        <div className="muted">{formatDateTime(row.observation.published_at)}</div>
                        <div className="note">
                          {row.observation.text ?? (
                            <span className="muted">teks tidak tersedia</span>
                          )}
                        </div>
                      </td>
                      <td>
                        <Chain row={row} />
                      </td>
                      <td>
                        <div>
                          <span className="muted">Stance isu:</span>{" "}
                          <span className="badge" data-stance={row.labels.issue_stance}>
                            {STANCE_LABELS[row.labels.issue_stance]}
                          </span>
                        </div>
                        <div>
                          <span className="muted">Terhadap yang dibalas:</span>{" "}
                          {ALIGNMENT_LABELS[row.labels.target_alignment]}
                        </div>
                        <div>
                          <span className="muted">Karakter:</span>{" "}
                          {row.labels.response_character
                            .map((c) => `${c.code} ${c.name}`)
                            .join("; ")}
                        </div>
                        {row.labels.expression_sentiment && (
                          <div>
                            <span className="muted">Sentimen:</span>{" "}
                            {SENTIMENT_LABELS[row.labels.expression_sentiment] ??
                              row.labels.expression_sentiment}
                          </div>
                        )}
                        {row.basis.matched && (
                          <details>
                            <summary>Dasar klasifikasi</summary>
                            <pre className="basis">
                              {JSON.stringify(row.basis.matched, null, 1)}
                            </pre>
                            <div className="muted">{row.basis.rules.join(", ")}</div>
                          </details>
                        )}
                      </td>
                      <td>
                        <CategoryBadge category={row.category} tier={row.tier} />
                        {row.needs_human_review && (
                          <div className="badge warning" data-needs-review>
                            Perlu tinjauan manusia
                          </div>
                        )}
                        {row.review && (
                          <div className="muted">
                            Ditinjau oleh {row.review.by}: {row.review.reason} ({row.versions}{" "}
                            versi)
                          </div>
                        )}
                        {canReview && reviewing !== row.assessment_id && (
                          <div>
                            <button type="button" onClick={() => setReviewing(row.assessment_id)}>
                              Tinjau
                            </button>
                          </div>
                        )}
                        {reviewing === row.assessment_id && (
                          <ReviewForm
                            row={row}
                            onCancel={() => setReviewing(null)}
                            onDone={() => {
                              setReviewing(null);
                              load();
                            }}
                          />
                        )}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="link"
                          onClick={() => onOpenObservation(row.observation.id)}
                        >
                          Jejak bukti
                        </button>
                        {row.artifact_ids.length > 0 && (
                          <div className="muted">{row.artifact_ids.length} artefak</div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <nav className="pager" aria-label="Halaman respons">
            <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              Sebelumnya
            </button>{" "}
            <button type="button" disabled={page >= pages} onClick={() => setPage(page + 1)}>
              Berikutnya
            </button>
          </nav>
        </>
      )}
    </section>
  );
}
