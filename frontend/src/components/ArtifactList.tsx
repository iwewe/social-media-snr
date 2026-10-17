import { useState } from "react";

import { api } from "../api/client";
import { errorText } from "../api/errorText";
import type {
  RunArtifact,
  RunSummary,
  RunVerification,
  Verification,
  VerificationResult,
} from "../api/types";
import { formatTime } from "../inspection/labels";
import { ErrorMessage } from "./ErrorMessage";

const RESULT_LABELS: Record<VerificationResult, string> = {
  MATCH: "Cocok",
  MISMATCH: "Berbeda dari saat disimpan",
  MISSING: "Berkas hilang",
  UNREADABLE: "Tidak dapat diverifikasi",
};

function size(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KiB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MiB`;
}

/** Unduh lewat tautan sementara. Server hanya menyajikan berkas yang hash-nya cocok. */
function download(url: string): void {
  const a = document.createElement("a");
  a.href = url;
  a.download = "";
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function Outcome({ v }: { v: Verification }) {
  const ok = v.result === "MATCH";
  return (
    <div
      className="message"
      data-level={v.message.level}
      data-verification={v.result}
      role={ok ? "status" : "alert"}
    >
      <strong>{RESULT_LABELS[v.result]}</strong>
      <p>{v.message.detail}</p>
      {v.message.action && <p className="action">{v.message.action}</p>}
      {v.result === "MISMATCH" && (
        <p>
          Dicatat: <code title={v.expected_sha256}>{v.expected_sha256.slice(0, 16)}...</code>;
          dihitung ulang:{" "}
          <code title={v.actual_sha256 ?? ""}>{v.actual_sha256?.slice(0, 16)}...</code>
        </p>
      )}
      <p className="muted">
        Diperiksa oleh {v.verified_by}, {formatTime(v.verified_at)}.
      </p>
    </div>
  );
}

/**
 * Artefak bukti: metadata, hash, verifikasi ulang SHA-256 dari berkas pada disk, dan unduhan.
 * Unduhan memverifikasi dulu dan hanya berlanjut bila hash cocok; server menegakkan hal yang sama.
 */
export function ArtifactList({
  runId,
  artifacts,
  preservation,
}: {
  runId: number;
  artifacts: RunArtifact[];
  preservation: RunSummary["preservation"];
}) {
  const [results, setResults] = useState<Record<number, Verification>>({});
  const [runResult, setRunResult] = useState<RunVerification | null>(null);
  const [busy, setBusy] = useState<number | "all" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const rejected = preservation?.rejected_count ?? 0;

  async function verifyOne(a: RunArtifact): Promise<Verification | null> {
    setBusy(a.id);
    setError(null);
    try {
      const v = await api.post<Verification>(`/api/artifacts/${a.id}/verify/`);
      setResults((r) => ({ ...r, [a.id]: v }));
      return v;
    } catch (e) {
      setError(errorText(e));
      return null;
    } finally {
      setBusy(null);
    }
  }

  async function verifyAll() {
    setBusy("all");
    setError(null);
    try {
      const out = await api.post<RunVerification>(`/api/inspections/${runId}/verify-artifacts/`);
      setRunResult(out);
      setResults(Object.fromEntries(out.verifications.map((v) => [v.artifact_id, v])));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  }

  async function downloadOne(a: RunArtifact) {
    const v = await verifyOne(a);
    if (v?.result === "MATCH") download(`/api/artifacts/${a.id}/content/`);
  }

  return (
    <section aria-label="Artefak bukti">
      <h3>Artefak bukti</h3>
      {artifacts.length === 0 ? (
        <p className="muted">Tidak ada artefak tersimpan untuk run ini.</p>
      ) : (
        <>
          <div className="row">
            <button type="button" onClick={() => void verifyAll()} disabled={busy !== null}>
              Verifikasi semua artefak
            </button>
          </div>
          <div className="table-scroll">
            <table aria-label="Artefak">
              <thead>
                <tr>
                  <th>Jenis</th>
                  <th>Ukuran</th>
                  <th>SHA-256</th>
                  <th>Disimpan</th>
                  <th>Verifikasi</th>
                </tr>
              </thead>
              <tbody>
                {artifacts.map((a) => {
                  const fresh = results[a.id];
                  const last = a.last_verification;
                  return (
                    <tr key={a.id} data-kind={a.kind}>
                      <td>{a.kind}</td>
                      <td>{size(a.size_bytes)}</td>
                      <td>
                        <code title={a.sha256}>{a.sha256.slice(0, 16)}...</code>
                      </td>
                      <td>{formatTime(a.stored_at)}</td>
                      <td>
                        <div className="row">
                          <button
                            type="button"
                            aria-label={`Verifikasi artefak ${a.kind} #${a.id}`}
                            onClick={() => void verifyOne(a)}
                            disabled={busy !== null}
                          >
                            Verifikasi
                          </button>
                          <button
                            type="button"
                            aria-label={`Unduh artefak ${a.kind} #${a.id}`}
                            onClick={() => void downloadOne(a)}
                            disabled={busy !== null}
                          >
                            Unduh
                          </button>
                        </div>
                        {fresh ? (
                          <Outcome v={fresh} />
                        ) : last ? (
                          <p className="muted" data-last-verification={last.result}>
                            Terakhir: {RESULT_LABELS[last.result]} oleh {last.verified_by},{" "}
                            {formatTime(last.verified_at)}
                          </p>
                        ) : (
                          <p className="muted">Belum pernah diverifikasi.</p>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
      <ErrorMessage error={error} />
      {runResult && (
        <div
          className="message"
          data-level={runResult.all_match ? "info" : "error"}
          data-run-verification={runResult.all_match ? "ok" : "problem"}
          role={runResult.all_match ? "status" : "alert"}
        >
          <strong>
            {runResult.all_match
              ? "Semua artefak cocok dan manifest konsisten"
              : "Ada artefak atau manifest yang bermasalah"}
          </strong>
          <p>
            {runResult.verifications.length} artefak diperiksa:{" "}
            {Object.entries(runResult.summary)
              .map(([k, n]) => `${n} ${RESULT_LABELS[k as VerificationResult].toLowerCase()}`)
              .join(", ")}
            .
          </p>
          <p data-manifest={runResult.manifest.state}>
            <strong>{runResult.manifest.message.title}.</strong> {runResult.manifest.message.detail}
          </p>
          {runResult.manifest.problems.length > 0 && (
            <ul>
              {runResult.manifest.problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      {rejected > 0 && (
        <p className="muted">
          {rejected} artefak tidak disimpan karena tampak memuat kredensial atau rahasia.
        </p>
      )}
      <p className="muted">
        Hash SHA-256 menunjukkan berkas tidak berubah sejak disimpan; hash tidak membuktikan
        keaslian konten platform. Berkas hanya dapat diunduh bila hash-nya cocok.
      </p>
    </section>
  );
}
