import { HELP, type HelpId } from "./helpTexts";

/** Petunjuk kontekstual: tombol "?" yang membuka teks bantuan di tempat. */
export function ContextHelp({ id }: { id: HelpId }) {
  const help = HELP[id];
  return (
    <details className="help">
      <summary aria-label={`Petunjuk: ${help.title}`} title={help.title}>
        ?
      </summary>
      <div role="note" className="help-body">
        <strong>{help.title}</strong>
        <p>{help.body}</p>
      </div>
    </details>
  );
}
