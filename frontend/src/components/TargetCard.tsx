import { useState } from "react";
import type { FormEvent } from "react";

import { api } from "../api/client";
import type { Meta, Target } from "../api/types";
import { ContextHelp } from "../help/ContextHelp";
import { useInspections } from "../hooks/useInspections";
import { errorText } from "../api/errorText";
import { DataStateBadge } from "./DataStateBadge";
import { ErrorMessage } from "./ErrorMessage";
import { InspectionPanel } from "./InspectionPanel";

function label(choices: { value: string; label: string }[], value: string): string {
  return choices.find((c) => c.value === value)?.label ?? value;
}

export function TargetCard({
  target,
  meta,
  onChanged,
}: {
  target: Target;
  meta: Meta;
  onChanged: () => void;
}) {
  const [revising, setRevising] = useState(false);
  const [note, setNote] = useState(target.context?.note ?? "");
  const [showHistory, setShowHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Setelah run final, minta induk memuat ulang agar ringkasan target ikut diperbarui.
  const inspections = useInspections(target, onChanged);

  async function revise(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      // Tanpa field `stances`: posisi awal versi sebelumnya dibawa ke versi baru.
      await api.post(`/api/targets/${target.id}/context-versions/`, { note });
      setRevising(false);
      onChanged();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  const ctx = target.context;
  // Keadaan data (NFR-08) dari run terbaru; sebelum riwayat dimuat dipakai ringkasan dari server.
  const state =
    inspections.runs?.[0]?.data_state ?? target.latest_inspection?.data_state ?? "not_inspected";

  return (
    <article className="card" aria-label={`Target ${target.normalized_url}`}>
      <header>
        <span className="badge">{label(meta.platforms, target.platform)}</span>{" "}
        <span className="badge">{label(meta.target_types, target.target_type)}</span>{" "}
        <DataStateBadge state={state} />
      </header>
      <p className="url">
        <a href={target.normalized_url} target="_blank" rel="noopener noreferrer">
          {target.normalized_url}
        </a>
      </p>

      {target.notices.map((n) => (
        <div key={n.code} className="message" data-level={n.level} role="note">
          <strong>{n.title}</strong>
          <p>{n.detail}</p>
          {n.action && <p className="action">{n.action}</p>}
        </div>
      ))}

      <InspectionPanel inspections={inspections} />

      {ctx && (
        <section>
          <h4>
            Catatan konteks (versi {ctx.version}) <ContextHelp id="targetNote" />
          </h4>
          {ctx.note ? (
            <p className="note">{ctx.note}</p>
          ) : (
            <p className="muted">(catatan kosong)</p>
          )}
          {ctx.stances.length > 0 && (
            <ul>
              {ctx.stances.map((s) => (
                <li key={s.proposition_id}>
                  {s.label}: <strong>{s.stance}</strong>{" "}
                  <span className="muted">- {s.statement}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="muted">
            Disimpan oleh {ctx.created_by}, {new Date(ctx.created_at).toLocaleString("id-ID")}
          </p>
        </section>
      )}

      {revising ? (
        <form onSubmit={revise}>
          <label>
            Revisi catatan (menjadi versi baru) <ContextHelp id="targetNote" />
            <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={4} />
          </label>
          <ErrorMessage error={error} />
          <button type="submit" disabled={busy}>
            Simpan versi baru
          </button>{" "}
          <button type="button" onClick={() => setRevising(false)}>
            Batal
          </button>
        </form>
      ) : (
        <button type="button" onClick={() => setRevising(true)}>
          Revisi catatan
        </button>
      )}

      {target.context_history.length > 1 && (
        <section>
          <button type="button" onClick={() => setShowHistory((v) => !v)}>
            {showHistory ? "Sembunyikan" : "Lihat"} riwayat versi ({target.context_history.length})
          </button>
          {showHistory && (
            <ol reversed>
              {target.context_history.map((v) => (
                <li key={v.version}>
                  <strong>Versi {v.version}</strong> - {v.created_by},{" "}
                  {new Date(v.created_at).toLocaleString("id-ID")}
                  <p className="note">{v.note || "(catatan kosong)"}</p>
                </li>
              ))}
            </ol>
          )}
        </section>
      )}
    </article>
  );
}
