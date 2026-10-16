import { useState } from "react";
import type { FormEvent } from "react";

import { api } from "../api/client";
import { ContextHelp } from "../help/ContextHelp";
import { errorText } from "../api/errorText";
import { ErrorMessage } from "./ErrorMessage";

export function IssueForm({
  investigationId,
  onCreated,
}: {
  investigationId: number;
  onCreated: () => void;
}) {
  const [title, setTitle] = useState("");
  const [definition, setDefinition] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/investigations/${investigationId}/issues/`, { title, definition });
      setTitle("");
      setDefinition("");
      onCreated();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="card">
      <h3>
        Tambah issue <ContextHelp id="createIssue" />
      </h3>
      <label>
        Judul issue (topik)
        <input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} />
      </label>
      <label>
        Definisi / arahan konteks (opsional)
        <textarea value={definition} onChange={(e) => setDefinition(e.target.value)} rows={3} />
      </label>
      <ErrorMessage error={error} />
      <button type="submit" disabled={busy}>
        Simpan issue
      </button>
    </form>
  );
}
