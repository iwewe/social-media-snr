import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import { errorText } from "../api/errorText";
import type { AnalysisRunInfo, CoordinationRow, InvestigationDetail } from "../api/types";
import { ErrorMessage } from "../components/ErrorMessage";
import { AuditPanel, type AuditScope } from "../components/analysis/AuditPanel";
import { EvidenceAccessPanel } from "../components/analysis/EvidenceAccessPanel";
import { FindingsPanel } from "../components/analysis/FindingsPanel";
import { NetworkPanel } from "../components/analysis/NetworkPanel";
import { ObservationDrawer } from "../components/analysis/ObservationDrawer";
import { ProfilesPanel } from "../components/analysis/ProfilesPanel";
import { RunAnalysisPanel } from "../components/analysis/RunAnalysisPanel";
import { ResponsesPanel } from "../components/analysis/ResponsesPanel";
import { RoleBadge } from "../components/RoleBadge";
import { canWrite } from "../team/roles";

type Tab = "responses" | "network" | "profiles" | "findings" | "audit" | "evidence" | "run";
const TABS: { id: Tab; label: string }[] = [
  { id: "responses", label: "Respons" },
  { id: "network", label: "Jaringan" },
  { id: "profiles", label: "Profil akun" },
  { id: "findings", label: "Temuan" },
  { id: "audit", label: "Jejak audit" },
  { id: "evidence", label: "Akses bukti" },
  { id: "run", label: "Jalankan analisis" },
];

function RunPicker({
  runs,
  value,
  onChange,
  label,
}: {
  runs: AnalysisRunInfo[];
  value: number;
  onChange: (id: number) => void;
  label: string;
}) {
  if (runs.length <= 1) return null;
  return (
    <label>
      {label}
      <select aria-label={label} value={value} onChange={(e) => onChange(Number(e.target.value))}>
        {runs.map((r) => (
          <option key={r.id} value={r.id}>
            Run #{r.id} · dataset {r.dataset.number} · {r.created_by}
          </option>
        ))}
      </select>
    </label>
  );
}

function NoAnalysis({ what }: { what: string }) {
  return (
    <p className="message" data-level="info" role="note" data-empty>
      Belum ada analisis {what} yang selesai pada investigasi ini. Anggota dapat menjalankannya dari
      tab <strong>Jalankan analisis</strong>; operator juga dapat memakai{" "}
      <code>manage.py run_analyses</code>. Hasilnya tampil di sini.
    </p>
  );
}

/** Halaman analisis I2: respons terklasifikasi, jaringan, profil akun, dan temuan (WP-2.7; FR-091..094). */
export function AnalysisPage() {
  const { id } = useParams();
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") as Tab) ?? "responses";
  const [detail, setDetail] = useState<InvestigationDetail | null>(null);
  const [allRuns, setAllRuns] = useState<AnalysisRunInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [observation, setObservation] = useState<number | null>(null);
  const [focusFinding, setFocusFinding] = useState<number | null>(null);
  const [actorFilter, setActorFilter] = useState<number | null>(null);
  const [auditScope, setAuditScope] = useState<AuditScope | null>(null);
  const [selected, setSelected] = useState<Map<number, CoordinationRow>>(new Map());
  const [m2Id, setM2Id] = useState(0);
  const [m3Id, setM3Id] = useState(0);

  const reloadRuns = useCallback(() => {
    api
      .get<{ results: AnalysisRunInfo[] }>(`/api/investigations/${id}/analysis-runs/`)
      .then((r) => setAllRuns(r.results))
      .catch((e: unknown) => setError(errorText(e)));
  }, [id]);
  const runs = useMemo(() => (allRuns ?? []).filter((x) => x.status === "COMPLETED"), [allRuns]);

  useEffect(() => {
    api
      .get<InvestigationDetail>(`/api/investigations/${id}/`)
      .then(setDetail)
      .catch((e: unknown) => setError(errorText(e)));
    reloadRuns();
  }, [id, reloadRuns]);

  const byMethod = useMemo(
    () => (method: string) => (runs ?? []).filter((r) => r.method === method),
    [runs],
  );
  const m2 = byMethod("m2-rules");
  const m3 = byMethod("m3-profile");
  const m4 = byMethod("m4-network");
  const co = byMethod("co-indicators");

  const setTab = (next: Tab) => setParams({ tab: next });
  const toggleIndicator = useCallback((row: CoordinationRow) => {
    setSelected((cur) => {
      const next = new Map(cur);
      if (next.has(row.id)) next.delete(row.id);
      else next.set(row.id, row);
      return next;
    });
  }, []);
  const openFinding = (fid: number) => {
    setFocusFinding(fid);
    setObservation(null);
    setTab("findings");
  };
  const openActor = (actorId: number) => {
    setActorFilter(actorId);
    setTab("responses");
  };
  const openAudit = (scope: AuditScope) => {
    setAuditScope(scope);
    setObservation(null);
    setTab("audit");
  };

  if (error) return <ErrorMessage error={error} />;
  if (!detail || !allRuns) return <p className="muted">Memuat...</p>;

  const writable = canWrite(detail.my_role);
  const activeM2 = m2.find((r) => r.id === m2Id) ?? m2[0];
  const activeM3 = m3.find((r) => r.id === m3Id) ?? m3[0];

  return (
    <>
      <p>
        <Link to={`/investigations/${detail.id}`}>&larr; Kembali ke investigasi</Link>
      </p>
      <h1>
        Analisis: {detail.name} <RoleBadge role={detail.my_role} />
      </h1>
      <p className="muted">
        Tiga kategori ditandai konsisten:{" "}
        <span className="badge category" data-category="observed_fact">
          Fakta observasi
        </span>{" "}
        <span className="badge category" data-category="machine_result">
          Hasil mesin
        </span>{" "}
        <span className="badge category" data-category="reviewed_finding">
          Temuan yang telah ditinjau
        </span>
        .
      </p>
      <nav className="tabs" aria-label="Bagian analisis">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            data-active={tab === t.id}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {tab === "responses" &&
        (activeM2 ? (
          <>
            <RunPicker runs={m2} value={activeM2.id} onChange={setM2Id} label="Analisis respons" />
            <ResponsesPanel
              key={activeM2.id}
              run={activeM2}
              canReview={writable}
              actorId={actorFilter}
              onClearActor={() => setActorFilter(null)}
              onOpenObservation={setObservation}
            />
          </>
        ) : (
          <NoAnalysis what="klasifikasi respons (M2)" />
        ))}
      {tab === "network" && (
        <NetworkPanel
          graphRuns={m4}
          coordinationRuns={co}
          selected={selected}
          onToggleIndicator={toggleIndicator}
          onOpenObservation={setObservation}
          onOpenActor={openActor}
        />
      )}
      {tab === "network" && m4.length === 0 && <NoAnalysis what="jaringan (M4)" />}
      {tab === "profiles" &&
        (activeM3 ? (
          <>
            <RunPicker runs={m3} value={activeM3.id} onChange={setM3Id} label="Analisis profil" />
            <ProfilesPanel key={activeM3.id} run={activeM3} />
          </>
        ) : (
          <NoAnalysis what="profil akun (M3)" />
        ))}
      {tab === "findings" && (
        <FindingsPanel
          investigationId={detail.id}
          runs={runs}
          canWrite={writable}
          selected={[...selected.values()]}
          focusId={focusFinding}
          onOpenObservation={setObservation}
          onOpenAudit={(id) => openAudit({ subject_type: "finding", subject_id: id })}
        />
      )}
      {tab === "audit" && (
        <AuditPanel
          key={JSON.stringify(auditScope)}
          investigationId={detail.id}
          scope={auditScope}
          onClearScope={() => setAuditScope(null)}
          onOpenObservation={setObservation}
          onOpenFinding={openFinding}
        />
      )}
      {tab === "evidence" && <EvidenceAccessPanel investigationId={detail.id} />}
      {tab === "run" && (
        <RunAnalysisPanel
          investigationId={detail.id}
          canWrite={writable}
          runs={allRuns}
          onChanged={reloadRuns}
        />
      )}
      {observation !== null && (
        <ObservationDrawer
          key={observation}
          observationId={observation}
          onClose={() => setObservation(null)}
          onOpenFinding={openFinding}
          onOpenAudit={(id) => openAudit({ observation: id })}
        />
      )}
    </>
  );
}
