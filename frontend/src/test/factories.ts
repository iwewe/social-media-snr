import { vi } from "vitest";

import type { Coverage, LatestInspection, RunSummary, Target } from "../api/types";

export const coverage = (over: Partial<Coverage> = {}): Coverage => ({
  scope: ["inspect_post", "inspect_replies"],
  pagination_complete: true,
  platform_displayed_count: 4,
  observed_reply_count: 4,
  observed_object_count: 5,
  notes: [],
  outcome: "COMPLETED",
  ...over,
});

export const run = (over: Partial<RunSummary> = {}): RunSummary => ({
  id: 1,
  target_id: 1,
  sequence: 1,
  status: "COMPLETED",
  data_state: "has_data",
  requested: ["inspect_post", "inspect_replies"],
  requested_by: "analis",
  created_at: "2026-10-17T01:00:00Z",
  started_at: "2026-10-17T01:00:01Z",
  finished_at: "2026-10-17T01:00:05Z",
  collector: { name: "fixture-dataset", version: "1" },
  source_method: "synthetic_fixture",
  coverage: coverage(),
  limitations: [],
  ingestion: null,
  reconciliation: { state: "DONE", counts: { NEW: 5 }, baseline_run_count: 0 },
  preservation: null,
  review: null,
  messages: [
    {
      code: "run_completed",
      level: "info",
      title: "Pemeriksaan selesai",
      detail: "Selesai berarti cakupan terbaca.",
      action: null,
    },
  ],
  ...over,
});

export const latest = (over: Partial<LatestInspection> = {}): LatestInspection => ({
  id: 1,
  sequence: 1,
  status: "COMPLETED",
  data_state: "has_data",
  finished_at: "2026-10-17T01:00:05Z",
  created_at: "2026-10-17T01:00:00Z",
  coverage: coverage(),
  headline: null,
  run_count: 1,
  ...over,
});

export const target = (over: Partial<Target> = {}): Target => ({
  id: 1,
  platform: "x",
  target_type: "post",
  url: "https://x.com/u/status/1",
  normalized_url: "https://x.com/u/status/1",
  created_at: "2026-10-16T05:00:00Z",
  context: null,
  context_history: [],
  latest_inspection: null,
  notices: [],
  ...over,
});

type Handler = (body: unknown) => { status?: number; body: unknown };

/** fetch palsu per "METHOD path"; mencatat panggilan. CSRF dianggap sudah ada. */
export function mockApi(routes: Record<string, Handler>) {
  document.cookie = "csrftoken=uji";
  const calls: string[] = [];
  const fetchMock = vi.fn(async (path: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${path}`;
    calls.push(key);
    const handler = routes[key];
    if (!handler) throw new Error(`rute tidak dimock: ${key}`);
    const { status = 200, body } = handler(init?.body ? JSON.parse(String(init.body)) : undefined);
    return new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls, fetchMock };
}
