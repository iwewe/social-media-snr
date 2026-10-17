import type { Role } from "../api/types";

/** Peran efektif pada satu investigasi; ADMIN = super admin (bukan anggota). */
export type EffectiveRole = Role | "ADMIN";

export const ROLE_LABELS: Record<EffectiveRole, string> = {
  ADMIN: "Super admin",
  OWNER: "Pemilik",
  MEMBER: "Anggota",
  VIEWER: "Pembaca",
};

export const ROLE_DESCRIPTIONS: Record<EffectiveRole, string> = {
  ADMIN: "Melihat dan mengelola semua investigasi dan akun.",
  OWNER: "Mengelola anggota, dan melakukan semua yang dapat dilakukan Anggota.",
  MEMBER:
    "Menulis issue, proposition, target, dan konteks; menjalankan inspeksi; mengakui tinjauan.",
  VIEWER: "Hanya membaca (termasuk bukti dan verifikasi hash); tidak dapat mengubah apa pun.",
};

/** Peran yang dapat dipilih saat menambah/mengubah anggota (super admin bukan peran anggota). */
export const ASSIGNABLE_ROLES: readonly Role[] = ["OWNER", "MEMBER", "VIEWER"];

/** Menulis data investigasi dan menjalankan inspeksi. Server tetap menegakkan; ini hanya tampilan. */
export function canWrite(role: EffectiveRole | null | undefined): boolean {
  return role === "ADMIN" || role === "OWNER" || role === "MEMBER";
}

/** Mengelola anggota. */
export function canManage(role: EffectiveRole | null | undefined): boolean {
  return role === "ADMIN" || role === "OWNER";
}
