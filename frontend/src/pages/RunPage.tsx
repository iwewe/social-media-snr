import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api/client";
import { errorText } from "../api/errorText";
import type { RunDetail } from "../api/types";
import { ArtifactList } from "../components/ArtifactList";
import { ErrorMessage } from "../components/ErrorMessage";
import { ObservationTable } from "../components/ObservationTable";
import { ReviewPanel } from "../components/ReviewPanel";
import { RunCard } from "../components/RunCard";
import { ContextHelp } from "../help/ContextHelp";

/** Detail satu run: ringkasan, tinjauan, artefak, dan respons mentah. */
export function RunPage() {
  const { id } = useParams();
  const [run, setRun] = useState<RunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .get<RunDetail>(`/api/inspections/${id}/`)
      .then((r) => {
        setRun(r);
        setError(null);
      })
      .catch((e: unknown) => setError(errorText(e)));
  }, [id]);

  useEffect(load, [load]);

  if (error) return <ErrorMessage error={error} />;
  if (!run) return <p className="muted">Memuat...</p>;

  return (
    <>
      <p>
        <Link to={`/investigations/${run.target.investigation_id}`}>&larr; Kembali ke target</Link>
      </p>
      <h1>
        Run #{run.sequence} <span className="muted url">{run.target.normalized_url}</span>
      </h1>
      <RunCard run={run} linkToDetail={false} />
      <ReviewPanel run={run} onAcknowledged={load} />
      <ArtifactList artifacts={run.artifacts} preservation={run.preservation} />
      <section aria-label="Respons mentah">
        <h2>
          Respons mentah <ContextHelp id="viewResponses" />
        </h2>
        <ObservationTable runId={run.id} dataState={run.data_state} />
      </section>
    </>
  );
}
