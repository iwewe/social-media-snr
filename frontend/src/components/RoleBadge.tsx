import { ROLE_DESCRIPTIONS, ROLE_LABELS } from "../team/roles";
import type { EffectiveRole } from "../team/roles";

export function RoleBadge({ role }: { role: EffectiveRole | null | undefined }) {
  if (!role) return null;
  return (
    <span className="badge role" data-role={role} title={ROLE_DESCRIPTIONS[role]}>
      {ROLE_LABELS[role]}
    </span>
  );
}
