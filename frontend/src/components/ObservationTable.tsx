import { useCallback, useEffect, useState } from "react";

import { api } from "../api/client";
import { errorText } from "../api/errorText";
import type { DataState, ObservationPage, ObservationRow } from "../api/types";
import { RECONCILIATION_LABELS, formatTime } from "../inspection/labels";
import { ErrorMessage } from "./ErrorMessage";

export const PAGE_SIZE = 25;
const LONG_TEXT = 300;

const unknown = <span className="muted">tidak diketahui</span>;

function Author({ row }: { row: ObservationRow }) {
  const a = row.author;
  return (
    <>
      {a.handle ? <strong>{a.handle}</strong> : unknown}
      <div className="muted">
        {a.external_actor_id ? `ID ${a.external_actor_id}` : "ID tidak diketahui"}
        {a.needs_verification ? " (perlu verifikasi)" : ""}
      </div>
    </>
  );
}

function Text({ text }: { text: string | null }) {
  if (text === null) return <span className="muted">tidak tersedia</span>;
  if (text.length <= LONG_TEXT) return <span className="note">{text}</span>;
  return (
    <details>
      <summary>{text.slice(0, LONG_TEXT)}...</summary>
      <span className="note">{text}</span>
    </details>
  );
}

function Remark({ row }: { row: ObservationRow }) {
  const parts: string[] = [];
  if (!row.observed_in_this_run) {
    parts.push(
      `Terakhir terlihat pada run #${row.last_seen_run_sequence ?? "?"}; tidak muncul pada run ini.`,
    );
  }
  if (row.changed_fields.length > 0) parts.push(`Berubah: ${row.changed_fields.join(", ")}.`);
  if (row.evidence) parts.push(`Bukti dari sumber: ${row.evidence}`);
  if (row.artifact_ids.length > 0) parts.push(`Bukti terkait: ${row.artifact_ids.length} artefak.`);
  return <>{parts.join(" ")}</>;
}

function ParentCell({ row }: { row: ObservationRow }) {
  if (row.parent_external_post_id) return <code>{row.parent_external_post_id}</code>;
  if (row.parent_unknown) return <span className="muted">induk tidak diketahui</span>;
  return <span className="muted">-</span>;
}

function emptyText(state: DataState): string {
  if (state === "access_failed") {
    return "Tidak ada respons tersimpan karena pengambilan gagal. Ini bukan berarti tidak ada balasan.";
  }
  if (state === "partial" || state === "needs_review") {
    return "Tidak ada respons tersimpan pada run ini; hasilnya tidak lengkap, jadi jangan simpulkan tidak ada balasan.";
  }
  return "Tidak ada respons pada run ini.";
}

/** Respons mentah satu run, berhalaman. Belum ada klasifikasi, stance, atau skor. */
export function ObservationTable({ runId, dataState }: { runId: number; dataState: DataState }) {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ObservationPage | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    (target: number) => {
      api
        .get<ObservationPage>(
          `/api/inspections/${runId}/observations/?page=${target}&page_size=${PAGE_SIZE}`,
        )
        .then((d) => {
          setData(d);
          setError(null);
        })
        .catch((e: unknown) => setError(errorText(e)));
    },
    [runId],
  );

  useEffect(() => load(page), [load, page]);

  if (error)
    return (
      <>
        <ErrorMessage error={error} />
        <button type="button" onClick={() => load(page)}>
          Muat ulang
        </button>
      </>
    );
  if (data === null) return <p className="muted">Memuat respons...</p>;

  const pages = Math.max(1, Math.ceil(data.count / data.page_size));
  const first = data.count === 0 ? 0 : (data.page - 1) * data.page_size + 1;
  const last = Math.min(data.count, data.page * data.page_size);

  return (
    <div>
      {!data.reconciled && data.count > 0 && (
        <p className="message" data-level="info" role="note">
          Status perubahan antar-pemeriksaan belum tersedia untuk run ini.
        </p>
      )}
      {data.count === 0 ? (
        <p className="muted" data-empty>
          {emptyText(dataState)}
        </p>
      ) : (
        <>
          <p className="muted" aria-live="polite">
            Menampilkan {first}-{last} dari {data.count} objek
          </p>
          <div className="table-scroll">
            <table aria-label="Respons mentah">
              <thead>
                <tr>
                  <th>Jenis</th>
                  <th>ID</th>
                  <th>Penulis</th>
                  <th>Isi</th>
                  <th>Dipublikasikan</th>
                  <th>Induk</th>
                  <th>Perubahan</th>
                  <th>Keterangan</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((row) => (
                  <tr
                    key={row.post_id}
                    data-reconciliation={row.reconciliation ?? "none"}
                    data-observed={row.observed_in_this_run}
                  >
                    <td>{row.object_type}</td>
                    <td>
                      {row.external_post_id ? (
                        <code>{row.external_post_id}</code>
                      ) : (
                        <span className="muted">tanpa ID (perlu verifikasi)</span>
                      )}
                    </td>
                    <td>
                      <Author row={row} />
                    </td>
                    <td>
                      <Text text={row.text} />
                    </td>
                    <td>{row.published_at ? formatTime(row.published_at) : unknown}</td>
                    <td>
                      <ParentCell row={row} />
                    </td>
                    <td>
                      {row.reconciliation ? (
                        <span className="badge" data-reconciliation-badge={row.reconciliation}>
                          {RECONCILIATION_LABELS[row.reconciliation]}
                        </span>
                      ) : (
                        <span className="muted">belum direkonsiliasi</span>
                      )}
                    </td>
                    <td>
                      <Remark row={row} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <nav className="row" aria-label="Halaman respons">
            <button type="button" onClick={() => setPage(page - 1)} disabled={data.page <= 1}>
              Sebelumnya
            </button>
            <span>
              Halaman {data.page} dari {pages}
            </span>
            <button type="button" onClick={() => setPage(page + 1)} disabled={data.page >= pages}>
              Berikutnya
            </button>
          </nav>
        </>
      )}
    </div>
  );
}
