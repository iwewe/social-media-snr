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
  latest_inspection: { status: string } | null;
}

export interface InvestigationDetail extends InvestigationSummary {
  issues: Issue[];
  targets: Target[];
}

export interface StanceInput {
  proposition: number;
  stance: InitialStance;
}
