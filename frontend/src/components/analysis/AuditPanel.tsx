import { useCallback, useEffect, useState } from "react";

import { api } from "../../api/client";
import { errorText } from "../../api/errorText";
import type { AuditPage } from "../../api/types";
import { queryString } from "../../analysis/query";
import { ErrorMessage } from "../ErrorMessage";
import { AuditEventItem } from "./AuditEventItem";

const PAGE_SIZE = 20;
const ACTIONS: [string, string][] = [
  ["ISSUE_CONTEXT", "Konteks issue"],
  ["TARGET_CONTEXT", "Konteks target"],
  ["CLASSIFICATION_REVIEW", "Tinjauan klasifikasi"],
  ["FINDING_DRAFT", "Temuan dibuat"],
  ["FINDING_REVISE", "Temuan direvisi"],
  ["FINDING_ENDORSE", "Temuan disahkan"],
  ["FINDING_WITHDRAW", "Temuan ditarik"],
];

export interface AuditScope {
  subject_type?: string;
  subject_id?: number;
  observation?: number;
}

/** Jejak audit: sejarah versi konteks, klasifikasi, dan status temuan (WP-2.8; AT-16). */
export function AuditPanel({
  investigationId,
  scope,
  onClearScope,
  onOpenObservation,
  onOpenFinding,
}: {
  investigationId: number;
  scope: AuditScope | null;
  onClearScope: () => void;
  onOpenObservation: (id: number) => void;
  onOpenFinding: (id: number) => void;
}) {
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<AuditPage | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    const qs = queryString({ ...scope, action, page, page_size: PAGE_SIZE });
    api
      .get<AuditPage>(`/api/investigations/${investigationId}/audit/${qs}`)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e: unknown) => setError(errorText(e)));
  }, [investigationId, scope, action, page]);

  useEffect(load, [load]);

  const pages = data ? Math.max(1, Math.ceil(data.count / data.page_size)) : 1;

  return (
    <section aria-label="Jejak audit">
      <h2>Jejak audit</h2>
      <fieldset className="filters">
        <legend>Filter</legend>
        <label>
          Jenis perubahan
          <select
            aria-label="Filter jenis perubahan"
            value={action}
            onChange={(e) => {
              setAction(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Semua</option>
            {ACTIONS.map(([v, label]) => (
              <option key={v} value={v}>
                {label}
              </option>
            ))}
          </select>
        </label>
        {scope && (
          <span data-scope>
            Dibatasi pada satu objek{" "}
            <button type="button" className="link" onClick={onClearScope}>
              tampilkan semua
            </button>
          </span>
        )}
      </fieldset>
      <ErrorMessage error={error} />
      {!data && !error && <p className="muted">Memuat jejak...</p>}
      {data && (
        <>
          <p className="message" data-level="info" role="note">
            {data.notice}
          </p>
          <p className="muted" aria-live="polite">
            {data.count} peristiwa{data.count > 0 ? `, halaman ${data.page} dari ${pages}` : ""}
          </p>
          {data.results.length === 0 ? (
            <p className="muted" data-empty>
              Belum ada perubahan yang tercatat untuk filter ini.
            </p>
          ) : (
            <ul className="plain" aria-label="Peristiwa audit">
              {data.results.map((e) => (
                <AuditEventItem
                  key={e.id}
                  event={e}
                  onOpenObservation={onOpenObservation}
                  onOpenFinding={onOpenFinding}
                />
              ))}
            </ul>
          )}
          <div className="pager">
            <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              Sebelumnya
            </button>
            <button type="button" disabled={page >= pages} onClick={() => setPage(page + 1)}>
              Berikutnya
            </button>
          </div>
        </>
      )}
    </section>
  );
}
