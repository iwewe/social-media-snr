import type { RunArtifact, RunSummary } from "../api/types";
import { formatTime } from "../inspection/labels";

function size(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KiB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MiB`;
}

/** Metadata artefak bukti + hash. Isi berkas dan verifikasi ulang hash menyusul (WP-1.10). */
export function ArtifactList({
  artifacts,
  preservation,
}: {
  artifacts: RunArtifact[];
  preservation: RunSummary["preservation"];
}) {
  const rejected = preservation?.rejected_count ?? 0;
  return (
    <section aria-label="Artefak bukti">
      <h3>Artefak bukti</h3>
      {artifacts.length === 0 ? (
        <p className="muted">Tidak ada artefak tersimpan untuk run ini.</p>
      ) : (
        <div className="table-scroll">
          <table aria-label="Artefak">
            <thead>
              <tr>
                <th>Jenis</th>
                <th>Ukuran</th>
                <th>SHA-256</th>
                <th>Disimpan</th>
              </tr>
            </thead>
            <tbody>
              {artifacts.map((a) => (
                <tr key={a.id} data-kind={a.kind}>
                  <td>{a.kind}</td>
                  <td>{size(a.size_bytes)}</td>
                  <td>
                    <code title={a.sha256}>{a.sha256.slice(0, 16)}...</code>
                  </td>
                  <td>{formatTime(a.stored_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {rejected > 0 && (
        <p className="muted">
          {rejected} artefak tidak disimpan karena tampak memuat kredensial atau rahasia.
        </p>
      )}
      <p className="muted">
        Hash SHA-256 menunjukkan berkas tidak berubah sejak disimpan; hash tidak membuktikan
        keaslian konten platform.
      </p>
    </section>
  );
}
