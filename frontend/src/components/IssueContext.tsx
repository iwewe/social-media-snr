import { useState } from "react";
import type { FormEvent } from "react";

import { api } from "../api/client";
import { errorText } from "../api/errorText";
import type { Issue } from "../api/types";
import { ErrorMessage } from "./ErrorMessage";

/** Konteks isu: tampil, revisi menjadi versi baru, dan riwayat versi (FR-014). Versi lama tidak pernah hilang. */
export function IssueContext({
  issue,
  writable,
  onRevised,
}: {
  issue: Issue;
  writable: boolean;
  onRevised: () => void;
}) {
  const current = issue.context?.definition ?? "";
  const [revising, setRevising] = useState(false);
  const [draft, setDraft] = useState(current);
  const [showHistory, setShowHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const open = () => {
    setDraft(current);
    setError(null);
    setRevising(true);
  };

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/issues/${issue.id}/context-versions/`, { definition: draft });
      setRevising(false);
      onRevised();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div data-issue-context>
      {current ? (
        <p className="note">{current}</p>
      ) : (
        <p className="muted">Belum ada definisi konteks.</p>
      )}
      {issue.context && <p className="muted">Konteks versi {issue.context.version}.</p>}
      {writable &&
        (revising ? (
          <form onSubmit={submit} aria-label={`Revisi konteks ${issue.title}`}>
            <label>
              Definisi / arahan konteks
              <textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={3} />
            </label>
            <p className="muted">
              Revisi menjadi versi baru; versi lama tetap tersimpan dan tercatat di jejak audit.
              Penjelasan ini belum dibaca klasifier mesin (hanya stance awal target, cue analis, dan
              rantai balasan).
            </p>
            <ErrorMessage error={error} />
            <button type="submit" disabled={busy}>
              Simpan revisi
            </button>{" "}
            <button type="button" onClick={() => setRevising(false)}>
              Batal
            </button>
          </form>
        ) : (
          <button type="button" onClick={open}>
            Revisi konteks isu
          </button>
        ))}
      {issue.context_history.length > 1 && (
        <section>
          <button type="button" onClick={() => setShowHistory((v) => !v)}>
            {showHistory ? "Sembunyikan" : "Lihat"} riwayat konteks ({issue.context_history.length})
          </button>
          {showHistory && (
            <ol reversed aria-label="Riwayat konteks isu">
              {issue.context_history.map((v) => (
                <li key={v.version}>
                  <strong>Versi {v.version}</strong> - {v.created_by},{" "}
                  {new Date(v.created_at).toLocaleString("id-ID")}
                  <p className="note">{v.definition || "(definisi kosong)"}</p>
                </li>
              ))}
            </ol>
          )}
        </section>
      )}
    </div>
  );
}
