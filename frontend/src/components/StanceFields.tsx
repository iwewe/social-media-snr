import type { Choice, InitialStance, Issue } from "../api/types";
import { ContextHelp } from "../help/ContextHelp";
import type { StanceChoices } from "./stances";

/** Posisi awal target per proposition aktif (FR-013). Kosong = tidak diisi. */
export function StanceFields({
  issues,
  stances,
  choices,
  onChange,
}: {
  issues: Issue[];
  stances: Choice[];
  choices: StanceChoices;
  onChange: (next: StanceChoices) => void;
}) {
  const propositions = issues.flatMap((issue) =>
    issue.propositions.filter((p) => !p.retired).map((p) => ({ ...p, issue: issue.title })),
  );
  if (propositions.length === 0) {
    return (
      <p className="muted">
        Belum ada proposition; posisi awal dapat diisi setelah proposition dibuat.
      </p>
    );
  }
  return (
    <fieldset>
      <legend>
        Posisi awal target terhadap proposition (opsional) <ContextHelp id="uncertaintyLabels" />
      </legend>
      {propositions.map((p) => (
        <label key={p.id}>
          {p.label}: {p.statement}
          <select
            value={choices[p.id] ?? ""}
            onChange={(e) => onChange({ ...choices, [p.id]: e.target.value as InitialStance | "" })}
          >
            <option value="">(tidak diisi)</option>
            {stances.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
      ))}
    </fieldset>
  );
}
