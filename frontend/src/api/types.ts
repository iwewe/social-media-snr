export type Platform = "x" | "threads" | "tiktok" | "instagram" | "facebook";
export type TargetType = "post" | "account";
export type InitialStance = "PRO" | "CONTRA" | "MIXED" | "UNDETERMINED";

export interface User {
  username: string;
  is_staff: boolean;
  is_superuser: boolean;
}

export type Role = "OWNER" | "MEMBER" | "VIEWER";

/** Anggota aktif sebuah investigasi. */
export interface Member {
  user_id: number;
  username: string;
  role: Role;
  since: string;
  added_by: string;
}

/** Akun untuk super admin (tanpa hash kata sandi). */
export interface Account {
  id: number;
  username: string;
  is_active: boolean;
  is_superuser: boolean;
  last_login: string | null;
  date_joined: string;
  active_memberships: number;
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
  /** Peran pengguna ini; ADMIN = super admin. */
  my_role: Role | "ADMIN" | null;
  member_count: number;
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
  context_history: {
    version: number;
    definition: string;
    created_at: string;
    created_by: string;
  }[];
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
  last_verification: {
    result: VerificationResult;
    verified_at: string | null;
    verified_by: string;
    purpose: string;
  } | null;
}

export type VerificationResult = "MATCH" | "MISMATCH" | "MISSING" | "UNREADABLE";

/** Hasil menghitung ulang SHA-256 dari berkas pada disk. Bukan bukti keaslian konten platform. */
export interface Verification {
  id: number;
  artifact_id: number;
  result: VerificationResult;
  purpose: string;
  verified_at: string | null;
  verified_by: string;
  expected_sha256: string;
  actual_sha256: string | null;
  expected_size_bytes: number;
  actual_size_bytes: number | null;
  message: RunMessage;
  statement: string;
}

export type ManifestState = "CONSISTENT" | "ABSENT" | "INCONSISTENT" | "UNTRUSTED";

export interface RunVerification {
  all_match: boolean;
  summary: Record<string, number>;
  verifications: Verification[];
  manifest: { state: ManifestState; problems: string[]; message: RunMessage };
  statement: string;
}

export interface RunDetail extends RunSummary {
  my_role: Role | "ADMIN" | null;
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

// --- Analisis I2 (WP-2.7): respons M2, graf M4, indikator, profil M3, temuan M5, jejak bukti ---

/** Empat kategori tampilan (FR-094). */
export type Category = "observed_fact" | "machine_result" | "human_reviewed" | "reviewed_finding";

export interface TierInfo {
  tier: 1 | 2 | 3 | 4;
  tier_name: string;
  tier_label: string;
  category: Category;
  category_label: string;
}

export interface AnalysisRunInfo {
  id: number;
  method: string;
  method_version: string;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";
  created_at: string;
  created_by: string;
  dataset: {
    id: number;
    number: number;
    platform: Platform;
    observation_count: number;
    digest: string;
  };
  error?: string | null;
  previous_run: number | null;
  tier: TierInfo | null;
}

export interface ActorRef {
  id: number;
  handle: string | null;
  display_name: string | null;
  external_actor_id: string | null;
}

export interface ObservationRef {
  id: number;
  external_post_id: string | null;
  type: string;
  text: string | null;
  published_at: string | null;
  observed_at: string;
  run_id: number;
  author: ActorRef | null;
}

export type IssueStance = "PRO" | "CONTRA" | "MIXED" | "NEUTRAL" | "UNDETERMINED" | "NOT_RELEVANT";
export type Alignment = "SUPPORT" | "OPPOSE" | "UNCLEAR";

export interface ResponseLabels {
  issue_stance: IssueStance;
  target_alignment: Alignment;
  expression_sentiment: string | null;
  response_character: { code: string; name: string }[];
  narrative_function: string | null;
}

export interface ParentTurn {
  observation_id: number;
  text: string | null;
  stance: IssueStance | null;
  author: ActorRef | null;
}

export interface ResponseRow extends TierInfo {
  assessment_id: number;
  proposition: { id: number; label: string };
  observation: ObservationRef;
  parent_chain: ParentTurn[];
  parent_unknown: boolean;
  labels: ResponseLabels;
  source: "MACHINE" | "HUMAN";
  needs_human_review: boolean;
  basis: {
    method: string | null;
    rules: string[];
    matched: Record<string, unknown> | null;
    changed: Record<string, [unknown, unknown]> | null;
    evidence: unknown;
  };
  review: { by: string; reason: string; at: string } | null;
  versions: number;
  artifact_ids: number[];
}

export interface ResponsesPage {
  run: AnalysisRunInfo;
  proposition: { id: number };
  results: ResponseRow[];
  total: number;
  page: number;
  page_size: number;
  notice: string;
}

export interface GraphNodeData {
  id: number;
  label: string;
  actor: ActorRef;
  attributes: {
    posts?: number;
    observations?: number;
    responses_assessed?: number;
    stance_counts?: Record<string, number>;
    stance_summary?: "PRO" | "CONTRA" | "MIXED" | "UNDETERMINED";
  };
  metrics: Record<string, number | undefined>;
}

export interface GraphEdgeData {
  id: number;
  kind: "interaction";
  source: number;
  target: number;
  type: "reply_to" | "quote_of" | "repost_of" | "mentions";
  weight: number;
  observation_ids: number[];
  stance_counts: Record<string, number>;
  first_published_at: string | null;
  last_published_at: string | null;
}

export interface GraphPayload extends TierInfo {
  run: AnalysisRunInfo;
  platform: Platform;
  definition: Record<string, unknown>;
  metrics: {
    note?: string;
    community_detection?: {
      status: string;
      communities?: number;
      modularity?: number | null;
      stability?: {
        seeds: number;
        distinct_partitions: number;
        mean_rand_index_vs_first: number;
        min_rand_index_vs_first: number;
        note: string;
      };
    };
  } & Record<string, unknown>;
  exclusions: Record<string, number>;
  filters: Record<string, unknown>;
  nodes: GraphNodeData[];
  edges: GraphEdgeData[];
  total_nodes: number;
  truncated: boolean;
  notice: string | null;
}

export interface CoordinationRow {
  id: number;
  kind: "behavioral_similarity";
  indicator: string;
  variant: string;
  actor_a: ActorRef;
  actor_b: ActorRef;
  value: number;
  support: number;
  explanation: string;
  detail: Record<string, unknown>;
  baseline: {
    status?: string;
    permutations?: number;
    p_max_ge?: number | null;
    baseline_p95_of_max?: number | null;
    exceeds_baseline_p95?: boolean;
  };
  overlaps_with: string[];
  observation_ids: number[];
  evidence_truncated: boolean;
  alternative_hypotheses: string[];
}

export interface CoordinationPage extends TierInfo {
  run: AnalysisRunInfo;
  platform: Platform;
  notice: string;
  alternative_hypotheses: string[];
  baseline: Record<string, unknown>;
  exclusions: Record<string, number>;
  results: CoordinationRow[];
  total: number;
  page: number;
  page_size: number;
}

export interface DimensionResult {
  status: "OK" | "INSUFFICIENT_DATA";
  reason?: string;
  observed?: number;
  required_minimum?: number;
  [key: string]: unknown;
}

export interface ProfileSummary {
  id: number;
  actor: ActorRef;
  level: string;
  participation: DimensionResult & {
    responses?: number;
    observations?: number;
    responses_with_changed_text?: number;
    distinct_targets?: number;
  };
  coverage_statement: string;
  partial_coverage: boolean;
}

export interface ProfilesPage extends TierInfo {
  run: AnalysisRunInfo;
  results: ProfileSummary[];
  total: number;
  page: number;
  page_size: number;
  notice: string;
}

export interface ProfileDetail extends TierInfo {
  id: number;
  run: AnalysisRunInfo;
  actor: ActorRef;
  platform: Platform;
  proposition_id: number;
  level: string;
  period: { start: string; end: string };
  coverage: {
    statement: string;
    partial_coverage: boolean;
    targets_covered: number[];
    targets_in_investigation: number[];
    incomplete_runs: { run: number; status: string }[];
    responses_without_known_time: number;
    responses_excluded_outside_period: number;
    responses_without_author: number;
  };
  dimensions: Record<string, DimensionResult>;
}

export type FindingStatus = "DRAFT" | "ENDORSED" | "WITHDRAWN" | "SUPERSEDED";
export type ConfidenceLevel = "HIGH" | "MODERATE" | "LOW" | "NOT_ASSESSABLE";

export interface FindingSummary extends TierInfo {
  id: number;
  title: string;
  status: FindingStatus;
  confidence: ConfidenceLevel;
  synthetic_data: boolean;
  platform: Platform;
  created_by: string;
  created_at: string;
  supersedes: number | null;
  superseded_by: number | null;
}

export interface EvidenceAxis {
  level: "GOOD" | "ACCEPTABLE" | "POOR" | "NOT_ASSESSABLE";
  reason: string;
  override_reason: string;
  system_suggestion: { level: string; reason: string };
}

export interface FindingDetail extends FindingSummary {
  statement: string;
  interpretation: string;
  confidence_reason: string;
  evidence_quality: Record<string, EvidenceAxis | Record<string, unknown>>;
  alternatives: Record<string, { outcome: string; reasoning: string }>;
  alternative_titles: Record<string, string>;
  independent_evidence_groups: number | null;
  notice: string;
  history: { id: number; status: FindingStatus; created_at: string }[];
  reviews: { action: "ENDORSE" | "WITHDRAW"; reviewer: string; note: string; at: string }[];
  runs: AnalysisRunInfo[];
  observation_count: number;
  observations: ObservationRef[];
  indicator_ids: number[];
}

export interface ObservationTrail extends TierInfo {
  observation: ObservationRef;
  parent_chain: ObservationRef[];
  run: { id: number; sequence: number; status: string; target_id: number; source_method: string };
  artifacts: {
    id: number;
    kind: string;
    content_type: string;
    size_bytes: number;
    sha256: string;
    post_specific: boolean;
    last_verification: { result: string; at: string } | null;
  }[];
  assessments: {
    assessment_id: number;
    analysis_run_id: number;
    labels: ResponseLabels;
    source: "MACHINE" | "HUMAN";
    category: Category;
    category_label: string;
  }[];
  finding_ids: number[];
  classification_trail: AuditEvent[];
}

export interface EvidenceSuggestion {
  axes: string[];
  facts: { synthetic: boolean } & Record<string, unknown>;
  suggestions: Record<string, { level: string; reason: string }>;
}

export type AuditAction =
  | "ISSUE_CONTEXT"
  | "TARGET_CONTEXT"
  | "CLASSIFICATION_REVIEW"
  | "FINDING_DRAFT"
  | "FINDING_REVISE"
  | "FINDING_ENDORSE"
  | "FINDING_WITHDRAW"
  | "ANALYSIS_RUN";
export type AuditSubject = "issue" | "target" | "response_assessment" | "finding" | "analysis_run";

export interface AuditEvent {
  id: number;
  at: string;
  actor: string;
  action: AuditAction;
  action_label: string;
  subject_type: AuditSubject;
  subject_type_label: string;
  subject_id: number;
  before: Record<string, unknown> | null;
  after: Record<string, unknown>;
  reason: string;
}

export interface AuditPage {
  count: number;
  page: number;
  page_size: number;
  results: AuditEvent[];
  notice: string;
}

export interface EvidenceAccessRow {
  id: number;
  at: string;
  user: string;
  purpose: "verify" | "verify_run" | "download";
  purpose_label: string;
  result: "MATCH" | "MISMATCH" | "MISSING" | "UNREADABLE";
  artifact: { id: number; kind: string; run_id: number; run_sequence: number };
}

export interface EvidenceAccessPage {
  count: number;
  page: number;
  page_size: number;
  results: EvidenceAccessRow[];
  notice: string;
}

export interface DatasetInfo {
  id: number;
  number: number;
  platform: Platform;
  observation_count: number;
  inspection_runs: number;
  note: string;
  created_at: string;
}

export interface AnalysisSetup {
  datasets: DatasetInfo[];
  inspection_runs: {
    id: number;
    target_id: number;
    target_url: string;
    platform: Platform;
    sequence: number;
    status: string;
    finished_at: string | null;
  }[];
  propositions: {
    id: number;
    label: string;
    statement: string;
    issue: { id: number; title: string };
  }[];
  m2_runs: { id: number; dataset_id: number; created_at: string }[];
  examples: {
    m3: Record<string, number>;
    m4: Record<string, unknown>;
    co: Record<string, number>;
  };
  notes: { exploratory: string; context: string };
}
