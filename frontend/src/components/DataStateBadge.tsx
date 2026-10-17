import type { DataState } from "../api/types";
import { DATA_STATE_INFO } from "../inspection/labels";

/** Lencana keadaan data. `data-state` dipakai gaya dan tes; deskripsi muncul sebagai tooltip. */
export function DataStateBadge({ state }: { state: DataState }) {
  const info = DATA_STATE_INFO[state];
  return (
    <span className="badge state" data-state={state} title={info.description}>
      {info.label}
    </span>
  );
}
