import { useEffect, useState } from "react";

import { api } from "../../api/client";
import { errorText } from "../../api/errorText";
import type { AnalysisRunInfo, ProfileDetail, ProfilesPage } from "../../api/types";
import { DIMENSION_LABELS, actorLabel, formatDateTime } from "../../analysis/labels";
import { ContextHelp } from "../../help/ContextHelp";
import { ErrorMessage } from "../ErrorMessage";
import { CategoryBadge } from "./CategoryBadge";

function Dimension({ name, dim }: { name: string; dim: ProfileDetail["dimensions"][string] }) {
  const ok = dim.status === "OK";
  const {
    status: _status,
    reason: _reason,
    observed: _observed,
    required_minimum: _min,
    ...values
  } = dim;
  return (
    <article
      className="card"
      aria-label={DIMENSION_LABELS[name] ?? name}
      data-dimension={name}
      data-status={dim.status}
    >
      <h4>
        {DIMENSION_LABELS[name] ?? name}{" "}
        <span className="badge" data-dim-status={dim.status}>
          {ok ? "Tersedia" : "Data tidak cukup"}
        </span>
      </h4>
      {ok ? (
        <pre className="basis">{JSON.stringify(values, null, 1)}</pre>
      ) : (
        <p className="muted">
          {dim.reason} (teramati {dim.observed}, dibutuhkan minimal {dim.required_minimum}). Ini
          bukan nol: datanya belum cukup untuk dinilai.
        </p>
      )}
    </article>
  );
}

/** Profil aktivitas akun Level A (FR-093): pernyataan cakupan selalu di bagian atas. */
export function ProfilesPanel({ run }: { run: AnalysisRunInfo }) {
  const [list, setList] = useState<ProfilesPage | null>(null);
  const [detail, setDetail] = useState<ProfileDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<ProfilesPage>(`/api/analysis-runs/${run.id}/profiles/?page_size=100`)
      .then((l) => {
        setList(l);
        setError(null);
      })
      .catch((e: unknown) => setError(errorText(e)));
  }, [run.id]);

  const open = (id: number) =>
    api
      .get<ProfileDetail>(`/api/profiles/${id}/`)
      .then((d) => {
        setDetail(d);
        setError(null);
      })
      .catch((e: unknown) => setError(errorText(e)));

  return (
    <section aria-label="Profil aktor">
      <h2>
        Profil aktivitas akun <ContextHelp id="viewActorProfile" />
      </h2>
      <ErrorMessage error={error} />
      {!list && !error && <p className="muted">Memuat profil...</p>}
      {list && (
        <>
          <p className="message" data-level="info" role="note">
            {list.notice}
          </p>
          {list.results.length === 0 ? (
            <p className="muted" data-empty>
              Tidak ada profil pada analisis ini.
            </p>
          ) : (
            <div className="table-scroll">
              <table aria-label="Daftar profil">
                <thead>
                  <tr>
                    <th>Akun</th>
                    <th>Cakupan profil</th>
                    <th>Partisipasi</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {list.results.map((p) => (
                    <tr key={p.id} data-profile={p.id}>
                      <td>
                        <strong>{actorLabel(p.actor)}</strong>
                        <div className="muted">
                          {p.actor.external_actor_id
                            ? `ID ${p.actor.external_actor_id}`
                            : "ID tidak diketahui"}
                        </div>
                      </td>
                      <td>
                        {p.partial_coverage && (
                          <span className="badge warning">Cakupan sebagian</span>
                        )}{" "}
                        <span className="note">{p.coverage_statement}</span>
                      </td>
                      <td>
                        {p.participation.responses ?? 0} respons pada{" "}
                        {p.participation.distinct_targets ?? 0} target
                      </td>
                      <td>
                        <button type="button" onClick={() => void open(p.id)}>
                          Buka profil
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
      {detail && (
        <article className="card" aria-label="Detail profil" data-profile-detail>
          <p className="message" data-level="warning" role="note" data-coverage>
            <strong>Cakupan:</strong> {detail.coverage.statement}
          </p>
          <h3>
            {actorLabel(detail.actor)}{" "}
            <CategoryBadge category={detail.category} tier={detail.tier} />
          </h3>
          <p className="muted">
            Platform {detail.platform} · Level {detail.level} · periode{" "}
            {formatDateTime(detail.period.start)} sampai {formatDateTime(detail.period.end)} ·{" "}
            {detail.coverage.targets_covered.length} dari{" "}
            {detail.coverage.targets_in_investigation.length} target diperiksa
            {detail.coverage.incomplete_runs.length > 0
              ? ` · ${detail.coverage.incomplete_runs.length} pemeriksaan tidak lengkap`
              : ""}
          </p>
          {Object.entries(detail.dimensions).map(([name, dim]) => (
            <Dimension key={name} name={name} dim={dim} />
          ))}
          <button type="button" onClick={() => setDetail(null)}>
            Tutup profil
          </button>
        </article>
      )}
    </section>
  );
}
