import { describe, expect, it } from "vitest";

import type { CoordinationRow, GraphPayload } from "../api/types";
import { SIMILARITY_COLOR, buildElements, buildLegend } from "./graphElements";

const graph = {
  nodes: [
    { id: 1, label: "a01", actor: {}, attributes: { stance_summary: "PRO" }, metrics: {} },
    { id: 2, label: "a02", actor: {}, attributes: {}, metrics: {} },
  ],
  edges: [
    {
      id: 10,
      kind: "interaction",
      source: 1,
      target: 2,
      type: "reply_to",
      weight: 2,
      observation_ids: [5],
      stance_counts: {},
      first_published_at: null,
      last_published_at: null,
    },
    {
      id: 11,
      kind: "interaction",
      source: 1,
      target: 99,
      type: "mentions",
      weight: 1,
      observation_ids: [],
      stance_counts: {},
      first_published_at: null,
      last_published_at: null,
    },
  ],
} as unknown as GraphPayload;

const indicator = {
  id: 7,
  kind: "behavioral_similarity",
  indicator: "CO-02",
  variant: "v",
  actor_a: { id: 1 },
  actor_b: { id: 2 },
  value: 0.5,
  support: 3,
  explanation: "x",
  detail: {},
  baseline: {},
  observation_ids: [5],
  evidence_truncated: false,
  alternative_hypotheses: [],
} as unknown as CoordinationRow;

describe("buildElements", () => {
  it("edge interaksi berpanah; edge tanpa node dibuang", () => {
    const { elements } = buildElements(graph, [], { showSimilarity: false });
    const edges = elements.filter((e) => e.group === "edges");
    expect(edges).toHaveLength(1);
    expect(edges[0].classes).toBe("interaction");
  });

  it("node tanpa stance berwarna UNDETERMINED", () => {
    const { elements } = buildElements(graph, [], { showSimilarity: false });
    const nodes = elements.filter((e) => e.group === "nodes");
    expect(nodes[1].data.stance).toBe("UNDETERMINED");
    expect(nodes[0].data.stance).toBe("PRO");
    expect(nodes[0].data.color).not.toBe(nodes[1].data.color);
  });

  it("kesamaan perilaku hanya muncul bila diminta dan dibedakan dari interaksi", () => {
    expect(
      buildElements(graph, [indicator], { showSimilarity: false }).elements.filter(
        (e) => e.classes === "similarity",
      ),
    ).toHaveLength(0);
    const { elements } = buildElements(graph, [indicator], { showSimilarity: true });
    const sim = elements.filter((e) => e.classes === "similarity");
    expect(sim).toHaveLength(1);
    expect(sim[0].data.kind).toBe("behavioral_similarity");
    expect(sim[0].data.color ?? SIMILARITY_COLOR).toBe(SIMILARITY_COLOR);
  });
});

describe("buildLegend", () => {
  it("legenda kesamaan hanya ada bersama edge kesamaan (AT-12)", () => {
    const without = buildLegend({ showSimilarity: false })
      .map((l) => JSON.stringify(l))
      .join("");
    const withSim = buildLegend({ showSimilarity: true })
      .map((l) => JSON.stringify(l))
      .join("");
    expect(withSim.length).toBeGreaterThan(without.length);
    expect(withSim.toLowerCase()).toContain("kemiripan");
  });
});
