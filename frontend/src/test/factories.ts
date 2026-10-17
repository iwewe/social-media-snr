import { vi } from "vitest";

import type {
  Account,
  Coverage,
  InvestigationDetail,
  LatestInspection,
  Member,
  ObservationPage,
  ObservationRow,
  RunArtifact,
  RunDetail,
  RunSummary,
  RunVerification,
  Target,
  Verification,
} from "../api/types";

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
    // Status 204 tidak boleh memiliki badan (Response melempar galat).
    return new Response(status === 204 ? null : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls, fetchMock };
}

export const row = (over: Partial<ObservationRow> = {}): ObservationRow => ({
  post_id: 1,
  external_post_id: "9000000011",
  identity_status: "VERIFIED",
  object_type: "reply",
  reconciliation: "NEW",
  changed_fields: [],
  evidence: null,
  observed_in_this_run: true,
  last_seen_run_sequence: null,
  author: {
    external_actor_id: "a02",
    handle: "akun_a02",
    display_name: null,
    needs_verification: false,
  },
  text: "Setuju, kajian publik perlu dilakukan.",
  published_at: "2026-10-15T08:10:00Z",
  observed_at: "2026-10-16T01:00:00Z",
  parent_external_post_id: "9000000001",
  parent_unknown: false,
  collection_status: "COMPLETED",
  artifact_ids: [],
  ...over,
});

export const obsPage = (
  rows: ObservationRow[],
  over: Partial<ObservationPage> = {},
): ObservationPage => ({
  count: rows.length,
  page: 1,
  page_size: 25,
  reconciled: true,
  results: rows,
  ...over,
});

export const artifact = (over: Partial<RunArtifact> = {}): RunArtifact => ({
  id: 1,
  kind: "dom_snapshot",
  sha256: "a".repeat(64),
  size_bytes: 2048,
  content_type: "text/html",
  stored_at: "2026-10-17T01:00:05Z",
  post_id: null,
  last_verification: null,
  ...over,
});

export const runDetail = (over: Partial<RunDetail> = {}): RunDetail => ({
  ...run(),
  my_role: "OWNER",
  target: {
    id: 1,
    platform: "x",
    target_type: "post",
    normalized_url: "https://x.com/u/status/1",
    investigation_id: 9,
  },
  artifacts: [],
  ...over,
});

const MESSAGES = {
  MATCH: {
    code: "verification_match",
    level: "info",
    title: "Hash cocok",
    detail: "Berkas yang tersimpan masih sama dengan saat disimpan.",
    action: null,
  },
  MISMATCH: {
    code: "verification_mismatch",
    level: "error",
    title: "Berkas berbeda dari saat disimpan",
    detail: "Berkas ini tidak boleh dipakai sebagai bukti sampai penyebabnya dijelaskan.",
    action: "Laporkan ke administrator.",
  },
  MISSING: {
    code: "verification_missing",
    level: "error",
    title: "Berkas bukti tidak ditemukan",
    detail: "Catatan artefak ada, tetapi berkasnya tidak ada.",
    action: null,
  },
  UNREADABLE: {
    code: "verification_unreadable",
    level: "error",
    title: "Berkas bukti tidak dapat diverifikasi",
    detail: "Berkas tidak dapat dibaca secara aman.",
    action: null,
  },
} as const;

export const verification = (
  result: Verification["result"] = "MATCH",
  over: Partial<Verification> = {},
): Verification => ({
  id: 1,
  artifact_id: 1,
  result,
  purpose: "verify",
  verified_at: "2026-10-17T03:00:00Z",
  verified_by: "analis",
  expected_sha256: "a".repeat(64),
  actual_sha256:
    result === "MATCH" ? "a".repeat(64) : result === "MISMATCH" ? "b".repeat(64) : null,
  expected_size_bytes: 2048,
  actual_size_bytes: result === "MATCH" ? 2048 : null,
  message: { ...MESSAGES[result] },
  statement: "Hash tidak membuktikan keaslian konten platform.",
  ...over,
});

export const runVerification = (over: Partial<RunVerification> = {}): RunVerification => ({
  all_match: true,
  summary: { MATCH: 2 },
  verifications: [
    verification("MATCH", { artifact_id: 1 }),
    verification("MATCH", { artifact_id: 2, id: 2 }),
  ],
  manifest: {
    state: "CONSISTENT",
    problems: [],
    message: {
      code: "manifest_consistent",
      level: "info",
      title: "Manifest konsisten",
      detail: "Daftar artefak di manifest sama dengan catatan.",
      action: null,
    },
  },
  statement: "Hash tidak membuktikan keaslian konten platform.",
  ...over,
});

export const member = (over: Partial<Member> = {}): Member => ({
  user_id: 1,
  username: "pemilik",
  role: "OWNER",
  since: "2026-10-17T01:00:00Z",
  added_by: "pemilik",
  ...over,
});

export const account = (over: Partial<Account> = {}): Account => ({
  id: 1,
  username: "admin",
  is_active: true,
  is_superuser: true,
  last_login: "2026-10-17T02:00:00Z",
  date_joined: "2026-10-01T00:00:00Z",
  active_memberships: 0,
  ...over,
});

export const detail = (
  role: InvestigationDetail["my_role"],
  over: Partial<InvestigationDetail> = {},
): InvestigationDetail => ({
  id: 1,
  name: "Uji tim",
  description: "",
  created_at: "2026-10-16T05:00:00Z",
  created_by: "pemilik",
  issue_count: 1,
  target_count: 1,
  my_role: role,
  member_count: 2,
  issues: [
    {
      id: 7,
      title: "Isu uji",
      created_at: "2026-10-16T05:00:00Z",
      context: null,
      propositions: [],
    },
  ],
  targets: [target()],
  ...over,
});
