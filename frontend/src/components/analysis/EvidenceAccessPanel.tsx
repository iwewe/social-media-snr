import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../../api/client";
import { errorText } from "../../api/errorText";
import type { EvidenceAccessPage } from "../../api/types";
import { formatDateTime } from "../../analysis/labels";
import { queryString } from "../../analysis/query";
import { ErrorMessage } from "../ErrorMessage";

const PAGE_SIZE = 20;
const PURPOSES: [string, string][] = [
  ["download", "Unduh isi artefak"],
  ["verify", "Verifikasi satu artefak"],
  ["verify_run", "Verifikasi satu pemeriksaan"],
];
const RESULTS: [string, string][] = [
  ["MATCH", "Cocok"],
  ["MISMATCH", "Berbeda dari saat disimpan"],
  ["MISSING", "Berkas hilang"],
  ["UNREADABLE", "Tidak terbaca"],
];
const RESULT_LABELS = Object.fromEntries(RESULTS);

/** Riwayat akses bukti: siapa membuka atau memverifikasi artefak, kapan, untuk apa, dan hasilnya. */
export function EvidenceAccessPanel({ investigationId }: { investigationId: number }) {
  const [purpose, setPurpose] = useState("");
  const [result, setResult] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<EvidenceAccessPage | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    const qs = queryString({ purpose, result, page, page_size: PAGE_SIZE });
    api
      .get<EvidenceAccessPage>(`/api/investigations/${investigationId}/evidence-access/${qs}`)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e: unknown) => setError(errorText(e)));
  }, [investigationId, purpose, result, page]);

  useEffect(load, [load]);

  const pages = data ? Math.max(1, Math.ceil(data.count / data.page_size)) : 1;
  const choose = (set: (v: string) => void) => (e: React.ChangeEvent<HTMLSelectElement>) => {
    set(e.target.value);
    setPage(1);
  };

  return (
    <section aria-label="Akses bukti">
      <h2>Akses bukti</h2>
      <fieldset className="filters">
        <legend>Filter</legend>
        <label>
          Keperluan
          <select aria-label="Filter keperluan" value={purpose} onChange={choose(setPurpose)}>
            <option value="">Semua</option>
            {PURPOSES.map(([v, label]) => (
              <option key={v} value={v}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Hasil
          <select aria-label="Filter hasil" value={result} onChange={choose(setResult)}>
            <option value="">Semua</option>
            {RESULTS.map(([v, label]) => (
              <option key={v} value={v}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </fieldset>
      <ErrorMessage error={error} />
      {!data && !error && <p className="muted">Memuat riwayat akses...</p>}
      {data && (
        <>
          <p className="message" data-level="info" role="note">
            {data.notice}
          </p>
          <p className="muted" aria-live="polite">
            {data.count} akses{data.count > 0 ? `, halaman ${data.page} dari ${pages}` : ""}
          </p>
          {data.results.length === 0 ? (
            <p className="muted" data-empty>
              Belum ada akses bukti yang tercatat untuk filter ini.
            </p>
          ) : (
            <div className="table-scroll">
              <table aria-label="Riwayat akses bukti">
                <thead>
                  <tr>
                    <th>Waktu</th>
                    <th>Pengguna</th>
                    <th>Keperluan</th>
                    <th>Artefak</th>
                    <th>Hasil</th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((r) => (
                    <tr key={r.id} data-access={r.id} data-result={r.result}>
                      <td>{formatDateTime(r.at)}</td>
                      <td>{r.user}</td>
                      <td>{r.purpose_label}</td>
                      <td>
                        {r.artifact.kind} #{r.artifact.id} (
                        <Link to={`/inspections/${r.artifact.run_id}`}>
                          pemeriksaan #{r.artifact.run_sequence}
                        </Link>
                        )
                      </td>
                      <td>{RESULT_LABELS[r.result] ?? r.result}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
