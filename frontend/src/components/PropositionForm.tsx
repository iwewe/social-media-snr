import { useState } from "react";
import type { FormEvent } from "react";

import { api } from "../api/client";
import { ContextHelp } from "../help/ContextHelp";
import { errorText } from "../api/errorText";
import { ErrorMessage } from "./ErrorMessage";

export function PropositionForm({
  issueId,
  onCreated,
}: {
  issueId: number;
  onCreated: () => void;
}) {
  const [statement, setStatement] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/issues/${issueId}/propositions/`, { statement });
      setStatement("");
      onCreated();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="inline-form">
      <label>
        Tambah proposition <ContextHelp id="addProposition" />
        <input
          value={statement}
          onChange={(e) => setStatement(e.target.value)}
          placeholder="Klaim spesifik yang dapat disetujui atau ditentang"
          required
        />
      </label>
      <ErrorMessage error={error} />
      <button type="submit" disabled={busy}>
        Simpan proposition
      </button>
    </form>
  );
}
