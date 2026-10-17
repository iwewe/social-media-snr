import { describe, expect, it } from "vitest";

import { ASSIGNABLE_ROLES, ROLE_DESCRIPTIONS, ROLE_LABELS, canManage, canWrite } from "./roles";

describe("peran dan hak (tampilan; server yang menegakkan)", () => {
  it("canWrite: ADMIN, OWNER, MEMBER ya; VIEWER, kosong, tak dikenal tidak", () => {
    expect(canWrite("ADMIN")).toBe(true);
    expect(canWrite("OWNER")).toBe(true);
    expect(canWrite("MEMBER")).toBe(true);
    expect(canWrite("VIEWER")).toBe(false);
    expect(canWrite(null)).toBe(false);
    expect(canWrite(undefined)).toBe(false);
  });

  it("canManage: hanya ADMIN dan OWNER", () => {
    expect(canManage("ADMIN")).toBe(true);
    expect(canManage("OWNER")).toBe(true);
    expect(canManage("MEMBER")).toBe(false);
    expect(canManage("VIEWER")).toBe(false);
    expect(canManage(null)).toBe(false);
  });

  it("setiap peran punya label dan penjelasan; super admin bukan peran yang dapat diberikan", () => {
    for (const role of ["ADMIN", "OWNER", "MEMBER", "VIEWER"] as const) {
      expect(ROLE_LABELS[role].length).toBeGreaterThan(2);
      expect(ROLE_DESCRIPTIONS[role].length).toBeGreaterThan(20);
    }
    expect([...ASSIGNABLE_ROLES]).toEqual(["OWNER", "MEMBER", "VIEWER"]);
  });

  it("label berbeda untuk setiap peran", () => {
    const labels = Object.values(ROLE_LABELS);
    expect(new Set(labels).size).toBe(labels.length);
  });
});
