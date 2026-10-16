import { createContext, useContext } from "react";

import type { User } from "../api/types";

export interface AuthState {
  /** undefined = masih memeriksa sesi; null = belum login. */
  user: User | null | undefined;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth harus dipakai di dalam AuthProvider");
  return ctx;
}
