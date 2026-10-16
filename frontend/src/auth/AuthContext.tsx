import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { ApiError, api, ensureCsrf } from "../api/client";
import type { User } from "../api/types";
import { AuthContext } from "./context";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    api
      .get<User>("/api/auth/me/")
      .then((u) => !cancelled && setUser(u))
      .catch((error: unknown) => {
        // 401 = belum login. Galat lain juga diperlakukan sebagai belum login; halaman login
        // menampilkan galat sebenarnya saat pengguna mencoba masuk.
        if (!cancelled) setUser(null);
        if (!(error instanceof ApiError) || error.status !== 401) console.warn(error);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    await ensureCsrf();
    setUser(await api.post<User>("/api/auth/login/", { username, password }));
  }, []);

  const logout = useCallback(async () => {
    await api.post<void>("/api/auth/logout/");
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, login, logout }), [user, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
