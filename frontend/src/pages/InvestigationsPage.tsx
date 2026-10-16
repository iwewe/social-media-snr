import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api/client";
import type { InvestigationDetail, InvestigationSummary } from "../api/types";
import { errorText } from "../api/errorText";
import { ErrorMessage } from "../components/ErrorMessage";

export function InvestigationsPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<InvestigationSummary[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api
      .get<InvestigationSummary[]>("/api/investigations/")
      .then(setItems)
      .catch((e: unknown) => setLoadError(errorText(e)));
  }, []);

  useEffect(load, [load]);

  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await api.post<InvestigationDetail>("/api/investigations/", {
        name,
        description,
      });
      navigate(`/investigations/${created.id}`);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Investigasi</h1>
      <ErrorMessage error={loadError} />
      {items === null && !loadError && <p className="muted">Memuat...</p>}
      {items?.length === 0 && (
        <p className="muted">Belum ada investigasi. Buat yang pertama di bawah.</p>
      )}
      <ul className="list">
        {items?.map((i) => (
          <li key={i.id} className="card">
            <Link to={`/investigations/${i.id}`}>{i.name}</Link>
            <span className="muted">
              {" "}
              - {i.issue_count} issue, {i.target_count} target, oleh {i.created_by}
            </span>
            {i.description && <p>{i.description}</p>}
          </li>
        ))}
      </ul>

      <form onSubmit={create} className="card">
        <h2>Buat investigasi</h2>
        <label>
          Nama
          <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={200} />
        </label>
        <label>
          Deskripsi (opsional)
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
        </label>
        <ErrorMessage error={error} />
        <button type="submit" disabled={busy}>
          Buat investigasi
        </button>
      </form>
    </>
  );
}
