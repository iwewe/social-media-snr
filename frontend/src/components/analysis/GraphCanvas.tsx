import cytoscape from "cytoscape";
import { useEffect, useRef } from "react";

import { GRAPH_STYLE, type CyElement } from "../../analysis/graphElements";

export type GraphSelection =
  | { kind: "node"; id: number }
  | { kind: "interaction"; id: number }
  | { kind: "behavioral_similarity"; id: number };

/** Kanvas Cytoscape. Logika elemen/gaya ada di analysis/graphElements (murni, diuji terpisah). */
export function GraphCanvas({
  elements,
  onSelect,
}: {
  elements: CyElement[];
  onSelect: (selection: GraphSelection | null) => void;
}) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;
    const cy = cytoscape({
      container: container.current,
      elements: elements as unknown as cytoscape.ElementDefinition[],
      style: GRAPH_STYLE as unknown as cytoscape.StylesheetJson,
      layout: { name: "cose", animate: false, randomize: false } as cytoscape.LayoutOptions,
      wheelSensitivity: 0.3,
    });
    cy.on("tap", "node", (e) => onSelect({ kind: "node", id: Number(e.target.data("actorId")) }));
    cy.on("tap", "edge", (e) => {
      const data = e.target.data();
      if (data.kind === "interaction") onSelect({ kind: "interaction", id: Number(data.edgeId) });
      else onSelect({ kind: "behavioral_similarity", id: Number(data.indicatorId) });
    });
    cy.on("tap", (e) => {
      if (e.target === cy) onSelect(null);
    });
    return () => cy.destroy();
  }, [elements, onSelect]);

  return <div ref={container} role="img" aria-label="Graf jaringan" className="graph-canvas" />;
}
