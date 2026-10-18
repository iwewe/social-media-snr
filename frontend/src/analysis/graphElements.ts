import type { CoordinationRow, GraphEdgeData, GraphNodeData, GraphPayload } from "../api/types";
import { INDICATOR_LABELS, RELATION_LABELS } from "./labels";

/** Warna node = ATRIBUT stance dari klasifikasi mesin; bukan label akun. */
export const STANCE_COLORS: Record<string, string> = {
  PRO: "#2e7d32",
  CONTRA: "#c62828",
  MIXED: "#6a1b9a",
  UNDETERMINED: "#757575",
};

/** Edge interaksi: garis penuh berpanah. Edge kesamaan perilaku: garis putus-putus, tanpa panah. */
export const INTERACTION_COLORS: Record<string, string> = {
  reply_to: "#1565c0",
  quote_of: "#00838f",
  repost_of: "#5d4037",
  mentions: "#455a64",
};
export const SIMILARITY_COLOR = "#e65100";

export interface CyElement {
  group: "nodes" | "edges";
  data: Record<string, unknown>;
  classes?: string;
}

export interface GraphView {
  elements: CyElement[];
  /** Akun dari indikator yang tidak ada pada graf (ditambahkan sebagai node tanpa atribut). */
  extraNodes: number[];
}

function similarityId(row: CoordinationRow): string {
  return `s${row.id}`;
}

export function buildElements(
  graph: GraphPayload,
  indicators: CoordinationRow[],
  options: { showSimilarity: boolean },
): GraphView {
  const elements: CyElement[] = [];
  const known = new Set<number>();
  for (const n of graph.nodes) {
    known.add(n.id);
    elements.push({
      group: "nodes",
      data: {
        id: `n${n.id}`,
        actorId: n.id,
        label: n.label,
        stance: n.attributes.stance_summary ?? "UNDETERMINED",
        color: STANCE_COLORS[n.attributes.stance_summary ?? "UNDETERMINED"],
      },
    });
  }
  for (const e of graph.edges) {
    if (!known.has(e.source) || !known.has(e.target)) continue;
    elements.push({
      group: "edges",
      classes: "interaction",
      data: {
        id: `i${e.id}`,
        edgeId: e.id,
        kind: "interaction",
        source: `n${e.source}`,
        target: `n${e.target}`,
        type: e.type,
        weight: e.weight,
        width: Math.min(8, 1 + e.weight),
        color: INTERACTION_COLORS[e.type] ?? "#455a64",
        label: "",
      },
    });
  }
  const extraNodes: number[] = [];
  if (options.showSimilarity) {
    for (const row of indicators) {
      for (const actor of [row.actor_a, row.actor_b]) {
        if (!known.has(actor.id)) {
          known.add(actor.id);
          extraNodes.push(actor.id);
          elements.push({
            group: "nodes",
            classes: "extra",
            data: {
              id: `n${actor.id}`,
              actorId: actor.id,
              label: actor.handle ?? actor.external_actor_id ?? `akun ${actor.id}`,
              stance: "UNDETERMINED",
              color: STANCE_COLORS.UNDETERMINED,
            },
          });
        }
      }
      elements.push({
        group: "edges",
        classes: "similarity",
        data: {
          id: similarityId(row),
          indicatorId: row.id,
          kind: "behavioral_similarity",
          source: `n${row.actor_a.id}`,
          target: `n${row.actor_b.id}`,
          indicator: row.indicator,
          variant: row.variant,
          support: row.support,
          width: Math.min(6, 1 + row.support),
          color: SIMILARITY_COLOR,
          label: row.variant ? `${row.indicator}:${row.variant}` : row.indicator,
        },
      });
    }
  }
  return { elements, extraNodes };
}

/** Gaya Cytoscape: dua jenis edge sengaja berbeda bentuk (garis penuh berpanah vs putus-putus). */
export const GRAPH_STYLE = [
  {
    selector: "node",
    style: {
      label: "data(label)",
      "background-color": "data(color)",
      color: "#222",
      "font-size": 10,
      "text-valign": "bottom",
      "text-margin-y": 3,
      width: 18,
      height: 18,
    },
  },
  {
    selector: "node.extra",
    style: { "border-width": 2, "border-style": "dashed", "border-color": "#999" },
  },
  {
    selector: "edge.interaction",
    style: {
      "curve-style": "bezier",
      "line-style": "solid",
      "line-color": "data(color)",
      "target-arrow-color": "data(color)",
      "target-arrow-shape": "triangle",
      width: "data(width)",
      opacity: 0.85,
    },
  },
  {
    selector: "edge.similarity",
    style: {
      "curve-style": "bezier",
      "line-style": "dashed",
      "line-dash-pattern": [6, 4],
      "line-color": "data(color)",
      "target-arrow-shape": "none",
      width: "data(width)",
      label: "data(label)",
      "font-size": 9,
      color: SIMILARITY_COLOR,
      "text-background-color": "#fff",
      "text-background-opacity": 0.8,
    },
  },
  {
    selector: ":selected",
    style: { "border-width": 3, "border-color": "#000", "overlay-opacity": 0.1 },
  },
] as const;

export interface LegendEntry {
  key: string;
  label: string;
  color: string;
  shape: "node" | "solid-arrow" | "dashed";
  note?: string;
}

export function buildLegend(options: { showSimilarity: boolean }): LegendEntry[] {
  const legend: LegendEntry[] = [
    ...Object.entries(STANCE_COLORS).map(([k, color]) => ({
      key: `stance-${k}`,
      label: `Node: stance ${k === "UNDETERMINED" ? "belum dapat ditentukan" : k.toLowerCase()}`,
      color,
      shape: "node" as const,
      note: "atribut dari klasifikasi mesin, bukan label akun",
    })),
    ...Object.entries(INTERACTION_COLORS).map(([k, color]) => ({
      key: `interaction-${k}`,
      label: `Edge interaksi: ${RELATION_LABELS[k].toLowerCase()}`,
      color,
      shape: "solid-arrow" as const,
      note: "relasi nyata yang teramati (berpanah dari penulis ke yang dituju)",
    })),
  ];
  if (options.showSimilarity) {
    legend.push({
      key: "similarity",
      label: "Edge kesamaan perilaku (indikator)",
      color: SIMILARITY_COLOR,
      shape: "dashed",
      note: "nilai terhitung dari kemiripan perilaku; bukan interaksi dan bukan bukti koordinasi",
    });
  }
  return legend;
}

export function similarityTitle(row: CoordinationRow): string {
  const base = INDICATOR_LABELS[row.indicator] ?? row.indicator;
  return row.variant ? `${base} (${row.variant})` : base;
}

export function edgeSummary(e: GraphEdgeData, nodes: GraphNodeData[]): string {
  const name = (id: number) => nodes.find((n) => n.id === id)?.label ?? `akun ${id}`;
  return `${name(e.source)} → ${name(e.target)}: ${RELATION_LABELS[e.type]} (bobot ${e.weight})`;
}
