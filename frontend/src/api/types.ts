export type Platform = "x" | "threads" | "tiktok" | "instagram" | "facebook";
export type TargetType = "post" | "account";
export type InitialStance = "PRO" | "CONTRA" | "MIXED" | "UNDETERMINED";

export interface User {
  username: string;
  is_staff: boolean;
}

export interface Choice {
  value: string;
  label: string;
}

export interface Meta {
  platforms: Choice[];
  target_types: Choice[];
  initial_stances: Choice[];
}

export interface InvestigationSummary {
  id: number;
  name: string;
  description: string;
  created_at: string;
  created_by: string;
  issue_count: number;
  target_count: number;
}

export interface Proposition {
  id: number;
  number: number;
  label: string;
  statement: string;
  retired: boolean;
}

export interface Issue {
  id: number;
  title: string;
  created_at: string;
  context: { version: number; definition: string } | null;
  propositions: Proposition[];
}

export interface StanceEntry {
  proposition_id: number;
  label: string;
  statement: string;
  stance: InitialStance;
}

export interface TargetContext {
  version: number;
  note: string;
  created_at: string;
  created_by: string;
  stances: StanceEntry[];
}

export interface Target {
  id: number;
  platform: Platform;
  target_type: TargetType;
  url: string;
  normalized_url: string;
  created_at: string;
  context: TargetContext | null;
  context_history: TargetContext[];
  /** null = belum pernah diperiksa (bukan "tidak ada data"). */
  latest_inspection: LatestInspection | null;
  notices: RunMessage[];
}

/** Keadaan data (NFR-08), dihitung server. Kegagalan akses TIDAK PERNAH berarti "tidak ada data". */
export type DataState =
  | "not_inspected"
  | "in_progress"
  | "has_data"
  | "no_data"
  | "partial"
  | "access_failed"
  | "needs_review";

export type RunStatus =
  | "PENDING"
  | "RUNNING"
  | "COMPLETED"
  | "PARTIAL"
  | "FAILED"
  | "ACCESS_RESTRICTED"
  | "UNSUPPORTED"
  | "REVIEW_REQUIRED";

export type MessageLevel = "info" | "warning" | "error";

export interface RunMessage {
  code: string;
  level: MessageLevel;
  title: string;
  detail: string;
  action: string | null;
}

/** null = tidak diketahui; jangan dianggap 0. */
export interface Coverage {
  scope: string[];
  pagination_complete: boolean | null;
  /** Jumlah yang DITAMPILKAN platform. */
  platform_displayed_count: number | null;
  /** Jumlah unik yang benar-benar TERAMATI. Dua angka ini tidak boleh digabung (PRD 9.3). */
  observed_reply_count: number | null;
  observed_object_count: number | null;
  notes: string[];
  outcome: string | null;
}

export interface LatestInspection {
  id: number;
  sequence: number;
  status: RunStatus;
  data_state: DataState;
  finished_at: string | null;
  created_at: string;
  coverage: Coverage | null;
  headline: RunMessage | null;
  run_count: number;
}

export interface RunLimitation {
  code: string;
  message: string;
  capability: string | null;
}

export interface RunSummary {
  id: number;
  target_id: number;
  sequence: number;
  status: RunStatus;
  data_state: DataState;
  requested: string[];
  requested_by: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  collector: { name: string; version: string } | null;
  source_method: string | null;
  coverage: Coverage | null;
  limitations: RunLimitation[];
  ingestion: {
    state: string | null;
    observations_received: number | null;
    observations_created: number | null;
    failed_batches: number;
    problem_codes: string[];
  } | null;
  reconciliation: {
    state: string | null;
    counts: Record<string, number>;
    baseline_run_count: number;
  } | null;
  preservation: {
    state: string | null;
    stored: number | null;
    rejected_count: number;
    failed_count: number;
  } | null;
  review: {
    reasons: string[];
    outcome: string | null;
    acknowledged: { by: string; at: string; note: string } | null;
  } | null;
  messages: RunMessage[];
}

export interface InvestigationDetail extends InvestigationSummary {
  issues: Issue[];
  targets: Target[];
}

export interface StanceInput {
  proposition: number;
  stance: InitialStance;
}

export interface RunArtifact {
  id: number;
  kind: string;
  sha256: string;
  size_bytes: number;
  content_type: string;
  stored_at: string | null;
  post_id: number | null;
}

export interface RunDetail extends RunSummary {
  target: {
    id: number;
    platform: Platform;
    target_type: TargetType;
    normalized_url: string;
    investigation_id: number;
  };
  artifacts: RunArtifact[];
}

export type ReconciliationStatus =
  "NEW" | "UNCHANGED" | "MODIFIED" | "NOT_OBSERVED" | "CONFIRMED_UNAVAILABLE";

/** Satu respons mentah pada satu run (belum diklasifikasi). null = tidak diketahui. */
export interface ObservationRow {
  post_id: number;
  external_post_id: string | null;
  identity_status: string;
  object_type: string;
  reconciliation: ReconciliationStatus | null;
  changed_fields: string[];
  evidence: string | null;
  observed_in_this_run: boolean;
  last_seen_run_sequence: number | null;
  author: {
    external_actor_id: string | null;
    handle: string | null;
    display_name: string | null;
    needs_verification: boolean;
  };
  text: string | null;
  published_at: string | null;
  observed_at: string | null;
  parent_external_post_id: string | null;
  parent_unknown: boolean;
  collection_status: string;
  artifact_ids: number[];
}

export interface ObservationPage {
  count: number;
  page: number;
  page_size: number;
  reconciled: boolean;
  results: ObservationRow[];
}
