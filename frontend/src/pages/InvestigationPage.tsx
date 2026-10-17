import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "../api/client";
import type { InvestigationDetail, Meta } from "../api/types";
import { useAuth } from "../auth/context";
import { errorText } from "../api/errorText";
import { ErrorMessage } from "../components/ErrorMessage";
import { IssueForm } from "../components/IssueForm";
import { PropositionForm } from "../components/PropositionForm";
import { RoleBadge } from "../components/RoleBadge";
import { TargetCard } from "../components/TargetCard";
import { TargetForm } from "../components/TargetForm";
import { TeamPanel } from "../components/TeamPanel";
import { ROLE_DESCRIPTIONS, canWrite } from "../team/roles";

export function InvestigationPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
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

  const role = detail.my_role;
  const writable = canWrite(role);

  return (
    <>
      <p>
        <Link to="/">&larr; Semua investigasi</Link>
      </p>
      <h1>
        {detail.name} <RoleBadge role={role} />
      </h1>
      {!writable && role && (
        <p className="message" data-level="info" role="note" data-readonly>
          Anda berperan <span className="emph">Pembaca</span> pada investigasi ini:{" "}
          {ROLE_DESCRIPTIONS[role]}
        </p>
      )}
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
            {writable && <PropositionForm issueId={issue.id} onCreated={load} />}
          </article>
        ))}
        {writable && <IssueForm investigationId={detail.id} onCreated={load} />}
      </section>

      <section>
        <h2>Target</h2>
        {detail.targets.length === 0 && <p className="muted">Belum ada target terdaftar.</p>}
        {detail.targets.map((t) => (
          <TargetCard key={t.id} target={t} meta={meta} onChanged={load} readOnly={!writable} />
        ))}
        {writable && (
          <TargetForm
            investigationId={detail.id}
            issues={detail.issues}
            meta={meta}
            onCreated={load}
          />
        )}
      </section>

      {role && user && (
        <TeamPanel
          investigationId={detail.id}
          role={role}
          username={user.username}
          onLeft={() => navigate("/")}
        />
      )}
    </>
  );
}
