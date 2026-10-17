import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import { api } from "../api/client";
import { errorText } from "../api/errorText";
import type { Member, Role } from "../api/types";
import { ContextHelp } from "../help/ContextHelp";
import { formatTime } from "../inspection/labels";
import { ASSIGNABLE_ROLES, ROLE_LABELS, canManage } from "../team/roles";
import type { EffectiveRole } from "../team/roles";
import { ErrorMessage } from "./ErrorMessage";

/**
 * Anggota investigasi. Semua peran melihat siapa timnya; hanya Pemilik dan Super admin mengubahnya.
 * Pencabutan meminta konfirmasi dua langkah. Aturan (mis. Pemilik terakhir) ditegakkan server dan
 * pesannya ditampilkan apa adanya.
 */
export function TeamPanel({
  investigationId,
  role,
  username,
  onLeft,
}: {
  investigationId: number;
  role: EffectiveRole;
  username: string;
  onLeft?: () => void;
}) {
  const [members, setMembers] = useState<Member[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [newName, setNewName] = useState("");
  const [newRole, setNewRole] = useState<Role>("VIEWER");
  const [confirming, setConfirming] = useState<number | null>(null);
  const manage = canManage(role);
  const base = `/api/investigations/${investigationId}/members/`;

  const load = useCallback(() => {
    api
      .get<Member[]>(base)
      .then((rows) => {
        setMembers(rows);
        setError(null);
      })
      .catch((e: unknown) => setError(errorText(e)));
  }, [base]);

  useEffect(load, [load]);

  async function act(run: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await run();
      load();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  function add(event: FormEvent) {
    event.preventDefault();
    void act(async () => {
      await api.post(base, { username: newName.trim(), role: newRole });
      setNewName("");
    });
  }

  function revoke(member: Member) {
    setConfirming(null);
    void act(async () => {
      await api.post(`${base}${member.user_id}/revoke/`);
      if (member.username === username) onLeft?.();
    });
  }

  return (
    <section aria-label="Tim">
      <h2>
        Tim <ContextHelp id="teamRoles" />
      </h2>
      <ErrorMessage error={error} />
      {members === null && !error && <p className="muted">Memuat anggota...</p>}
      {members && (
        <div className="table-scroll">
          <table aria-label="Anggota">
            <thead>
              <tr>
                <th>Pengguna</th>
                <th>Peran</th>
                <th>Sejak</th>
                <th>Ditambahkan oleh</th>
                {manage && <th>Aksi</th>}
              </tr>
            </thead>
            <tbody>
              {members.map((m) => (
                <tr key={m.user_id} data-member={m.username}>
                  <td>
                    <strong>{m.username}</strong>
                    {m.username === username && <span className="muted"> (Anda)</span>}
                  </td>
                  <td>
                    {manage ? (
                      <select
                        aria-label={`Peran ${m.username}`}
                        value={m.role}
                        disabled={busy}
                        onChange={(e) =>
                          void act(() =>
                            api.post(`${base}${m.user_id}/role/`, { role: e.target.value }),
                          )
                        }
                      >
                        {ASSIGNABLE_ROLES.map((r) => (
                          <option key={r} value={r}>
                            {ROLE_LABELS[r]}
                          </option>
                        ))}
                      </select>
                    ) : (
                      ROLE_LABELS[m.role]
                    )}
                  </td>
                  <td>{formatTime(m.since)}</td>
                  <td>{m.added_by}</td>
                  {manage && (
                    <td>
                      {confirming === m.user_id ? (
                        <span className="row">
                          <span>
                            {m.username === username ? "Keluar dari investigasi?" : "Cabut akses?"}
                          </span>
                          <button type="button" onClick={() => revoke(m)} disabled={busy}>
                            Ya
                          </button>
                          <button type="button" onClick={() => setConfirming(null)}>
                            Batal
                          </button>
                        </span>
                      ) : (
                        <button
                          type="button"
                          aria-label={`Cabut ${m.username}`}
                          onClick={() => setConfirming(m.user_id)}
                          disabled={busy}
                        >
                          Cabut
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {manage ? (
        <form onSubmit={add} className="card" aria-label="Tambah anggota">
          <h3>Tambah anggota</h3>
          <div className="row">
            <label>
              Nama pengguna
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                required
                maxLength={150}
                autoComplete="off"
              />
            </label>
            <label>
              Peran
              <select value={newRole} onChange={(e) => setNewRole(e.target.value as Role)}>
                {ASSIGNABLE_ROLES.map((r) => (
                  <option key={r} value={r}>
                    {ROLE_LABELS[r]}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p className="muted">
            Akun dibuat oleh super admin di halaman Akun. Mencabut akses tidak menghapus riwayat.
          </p>
          <button type="submit" disabled={busy || !newName.trim()}>
            Tambahkan
          </button>
        </form>
      ) : (
        <p className="muted">Hanya Pemilik dan Super admin yang dapat mengubah tim.</p>
      )}
    </section>
  );
}
