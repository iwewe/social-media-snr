import { useState } from "react";
import type { FormEvent } from "react";

import { ApiError, api } from "../api/client";
import type { Issue, Meta } from "../api/types";
import { ContextHelp } from "../help/ContextHelp";
import { errorText } from "../api/errorText";
import { ErrorMessage } from "./ErrorMessage";
import { StanceFields } from "./StanceFields";
import { toStanceInput } from "./stances";
import type { StanceChoices } from "./stances";

export function TargetForm({
  investigationId,
  issues,
  meta,
  onCreated,
}: {
  investigationId: number;
  issues: Issue[];
  meta: Meta;
  onCreated: () => void;
}) {
  const [platform, setPlatform] = useState(meta.platforms[0]?.value ?? "x");
  const [targetType, setTargetType] = useState(meta.target_types[0]?.value ?? "post");
  const [url, setUrl] = useState("");
  const [note, setNote] = useState("");
  const [choices, setChoices] = useState<StanceChoices>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/investigations/${investigationId}/targets/`, {
        platform,
        target_type: targetType,
        url,
        note,
        stances: toStanceInput(choices),
      });
      setUrl("");
      setNote("");
      setChoices({});
      onCreated();
    } catch (e) {
      if (e instanceof ApiError && e.code === "duplicate_target") {
        setError(`${e.message} (target nomor ${e.existingId}).`);
      } else {
        setError(errorText(e));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="card">
      <h3>Daftarkan target</h3>
      <div className="row">
        <label>
          Platform
          <select value={platform} onChange={(e) => setPlatform(e.target.value)}>
            {meta.platforms.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Jenis target
          <select value={targetType} onChange={(e) => setTargetType(e.target.value)}>
            {meta.target_types.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label>
        URL target
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://..."
          required
        />
      </label>
      <label>
        Catatan konteks target <ContextHelp id="targetNote" />
        <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={4} />
      </label>
      <StanceFields
        issues={issues}
        stances={meta.initial_stances}
        choices={choices}
        onChange={setChoices}
      />
      <ErrorMessage error={error} />
      <button type="submit" disabled={busy}>
        Daftarkan target
      </button>
    </form>
  );
}
