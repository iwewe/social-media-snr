import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { errorText } from "../api/errorText";
import type { Account } from "../api/types";
import { useAuth } from "../auth/context";
import { ErrorMessage } from "../components/ErrorMessage";
import { formatTime } from "../inspection/labels";

/** Akun pengguna: khusus super admin (server menegakkan; halaman ini hanya menyembunyikannya). */
export function UsersPage() {
  const { user } = useAuth();
  const [accounts, setAccounts] = useState<Account[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [resetting, setResetting] = useState<number | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const allowed = user?.is_superuser === true;

  const load = useCallback(() => {
    api
      .get<Account[]>("/api/users/")
      .then((rows) => {
        setAccounts(rows);
        setError(null);
      })
      .catch((e: unknown) => setError(errorText(e)));
  }, []);

  useEffect(() => {
    if (allowed) load();
  }, [allowed, load]);

  if (!allowed) {
    return (
      <>
        <h1>Akun</h1>
        <p role="alert" className="error">
          Halaman ini khusus super admin.
        </p>
        <p>
          <Link to="/">&larr; Kembali</Link>
        </p>
      </>
    );
  }

  async function act(run: () => Promise<unknown>, done?: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await run();
      if (done) setNotice(done);
      load();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  function create(event: FormEvent) {
    event.preventDefault();
    void act(async () => {
      await api.post("/api/users/", { username: username.trim(), password });
      setUsername("");
      setPassword("");
    }, `Akun ${username.trim()} dibuat. Sampaikan kata sandi awal secara langsung; tambahkan ke investigasi lewat panel Tim.`);
  }

  function resetPassword(event: FormEvent, account: Account) {
    event.preventDefault();
    void act(async () => {
      await api.post(`/api/users/${account.id}/password/`, { password: newPassword });
      setResetting(null);
      setNewPassword("");
    }, `Kata sandi ${account.username} diganti.`);
  }

  return (
    <>
      <p>
        <Link to="/">&larr; Semua investigasi</Link>
      </p>
      <h1>Akun</h1>
      <ErrorMessage error={error} />
      {notice && (
        <p role="status" className="message" data-level="info">
          {notice}
        </p>
      )}
      {accounts === null && !error && <p className="muted">Memuat akun...</p>}
      {accounts && (
        <div className="table-scroll">
          <table aria-label="Akun pengguna">
            <thead>
              <tr>
                <th>Pengguna</th>
                <th>Status</th>
                <th>Masuk terakhir</th>
                <th>Investigasi</th>
                <th>Aksi</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((a) => (
                <tr key={a.id} data-account={a.username} data-active={a.is_active}>
                  <td>
                    <strong>{a.username}</strong>
                    {a.is_superuser && <span className="badge role"> Super admin</span>}
                    {a.username === user?.username && <span className="muted"> (Anda)</span>}
                  </td>
                  <td>{a.is_active ? "Aktif" : "Nonaktif"}</td>
                  <td>{a.last_login ? formatTime(a.last_login) : "belum pernah"}</td>
                  <td>{a.active_memberships}</td>
                  <td>
                    <div className="row">
                      <button
                        type="button"
                        aria-label={`${a.is_active ? "Nonaktifkan" : "Aktifkan"} ${a.username}`}
                        disabled={busy || a.username === user?.username}
                        onClick={() =>
                          void act(
                            () =>
                              api.post(`/api/users/${a.id}/activation/`, { active: !a.is_active }),
                            `${a.username} ${a.is_active ? "dinonaktifkan" : "diaktifkan"}.`,
                          )
                        }
                      >
                        {a.is_active ? "Nonaktifkan" : "Aktifkan"}
                      </button>
                      <button
                        type="button"
                        aria-label={`Atur kata sandi ${a.username}`}
                        disabled={busy}
                        onClick={() => {
                          setResetting(resetting === a.id ? null : a.id);
                          setNewPassword("");
                        }}
                      >
                        Atur kata sandi
                      </button>
                    </div>
                    {resetting === a.id && (
                      <form
                        onSubmit={(e) => resetPassword(e, a)}
                        aria-label={`Kata sandi ${a.username}`}
                      >
                        <label>
                          Kata sandi baru
                          <input
                            type="password"
                            value={newPassword}
                            onChange={(e) => setNewPassword(e.target.value)}
                            autoComplete="new-password"
                            required
                          />
                        </label>
                        <button type="submit" disabled={busy || !newPassword}>
                          Simpan kata sandi
                        </button>
                      </form>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <form onSubmit={create} className="card" aria-label="Buat akun">
        <h2>Buat akun anggota tim</h2>
        <label>
          Nama pengguna
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            maxLength={150}
            autoComplete="off"
          />
        </label>
        <label>
          Kata sandi awal
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="new-password"
          />
        </label>
        <p className="muted">
          Kata sandi harus memenuhi aturan keamanan (panjang, bukan yang umum, tidak mirip nama
          pengguna). Akun baru belum melihat investigasi apa pun sampai ditambahkan oleh Pemilik.
        </p>
        <button type="submit" disabled={busy || !username.trim() || !password}>
          Buat akun
        </button>
      </form>
    </>
  );
}
