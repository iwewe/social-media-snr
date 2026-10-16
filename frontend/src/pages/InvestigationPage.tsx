import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api/client";
import type { InvestigationDetail, Meta } from "../api/types";
import { errorText } from "../api/errorText";
import { ErrorMessage } from "../components/ErrorMessage";
import { IssueForm } from "../components/IssueForm";
import { PropositionForm } from "../components/PropositionForm";
import { TargetCard } from "../components/TargetCard";
import { TargetForm } from "../components/TargetForm";

export function InvestigationPage() {
  const { id } = useParams();
  const [detail, setDetail] = useState<InvestigationDetail | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .get<InvestigationDetail>(`/api/investigations/${id}/`)
      .then(setDetail)
      .catch((e: unknown) => setError(errorText(e)));
  }, [id]);

  useEffect(load, [load]);
  useEffect(() => {
    api
      .get<Meta>("/api/meta/")
      .then(setMeta)
      .catch((e: unknown) => setError(errorText(e)));
  }, []);

  if (error) return <ErrorMessage error={error} />;
  if (!detail || !meta) return <p className="muted">Memuat...</p>;

  return (
    <>
      <p>
        <Link to="/">&larr; Semua investigasi</Link>
      </p>
      <h1>{detail.name}</h1>
      {detail.description && <p>{detail.description}</p>}

      <section>
        <h2>Issue dan proposition</h2>
        {detail.issues.length === 0 && <p className="muted">Belum ada issue.</p>}
        {detail.issues.map((issue) => (
          <article key={issue.id} className="card" aria-label={`Issue ${issue.title}`}>
            <h3>{issue.title}</h3>
            {issue.context?.definition && <p className="note">{issue.context.definition}</p>}
            {issue.propositions.length === 0 ? (
              <p className="muted">Belum ada proposition.</p>
            ) : (
              <ul>
                {issue.propositions.map((p) => (
                  <li key={p.id}>
                    <strong>{p.label}</strong>: {p.statement}
                    {p.retired && <span className="muted"> (dinonaktifkan)</span>}
                  </li>
                ))}
              </ul>
            )}
            <PropositionForm issueId={issue.id} onCreated={load} />
          </article>
        ))}
        <IssueForm investigationId={detail.id} onCreated={load} />
      </section>

      <section>
        <h2>Target</h2>
        {detail.targets.length === 0 && <p className="muted">Belum ada target terdaftar.</p>}
        {detail.targets.map((t) => (
          <TargetCard key={t.id} target={t} meta={meta} onChanged={load} />
        ))}
        <TargetForm
          investigationId={detail.id}
          issues={detail.issues}
          meta={meta}
          onCreated={load}
        />
      </section>
    </>
  );
}
