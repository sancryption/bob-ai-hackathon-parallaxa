/**
 * Shared API contract types — mirrors backend app/schemas.py exactly.
 * These are the single source of truth for the frontend API surface.
 * Do NOT add computed or UI-only fields here.
 */

// ---------------------------------------------------------------------------
// Generic envelopes
// ---------------------------------------------------------------------------

export interface ValidationDetail {
  loc: string[];
  msg: string;
  type: string;
}

export interface ErrorDetail {
  code: string;
  message: string;
  field?: string;
  validation_errors?: ValidationDetail[];
}

export interface ErrorEnvelope {
  error: ErrorDetail;
}

export interface OkEnvelope<T> {
  data: T;
}

// ---------------------------------------------------------------------------
// Project
// ---------------------------------------------------------------------------

export type ProjectStatus = "draft" | "processing" | "ready" | "error";

export interface ProjectCreate {
  name: string;
  description?: string;
}

export interface ProjectRead {
  id: number;
  name: string;
  description?: string;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
}

export interface ProjectList {
  items: ProjectRead[];
  total: number;
}

// ---------------------------------------------------------------------------
// Upload
// ---------------------------------------------------------------------------

export type UploadStatus = "pending" | "processing" | "complete" | "failed";

export interface UploadRead {
  id: number;
  project_id: number;
  filename: string;
  content_type: string;
  size_bytes?: number;
  row_count?: number;
  duplicate_count?: number;
  status: UploadStatus;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Job
// ---------------------------------------------------------------------------

export type JobType = "signal_detection" | "readiness_assessment";
export type JobStatus = "queued" | "running" | "complete" | "failed";

export interface JobProgress {
  percent: number; // 0–100
  message: string;
  step: string;
}

export interface JobRead {
  id: number;
  project_id: number;
  job_type: JobType;
  status: JobStatus;
  progress?: JobProgress;
  result?: unknown;
  error?: string;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Event cluster / normalisation provenance
// ---------------------------------------------------------------------------

export interface NormalizationProvenance {
  raw_term: string;
  preferred_term: string;
  meddra_code?: string;
  /** "exact_match" | "alias_lookup" | "fuzzy" */
  method: string;
  /** 0.0–1.0 */
  confidence: number;
}

export interface EventCluster {
  preferred_term: string;
  raw_aliases: string[];
  meddra_code?: string;
  case_count: number;
  provenances: NormalizationProvenance[];
}

// ---------------------------------------------------------------------------
// Signal
// ---------------------------------------------------------------------------

export type SignalSeverity = "low" | "medium" | "high" | "critical";
export type ThresholdStatus = "below" | "at" | "above";

/** Lightweight summary for list / dashboard views. */
export interface SignalSummary {
  drug: string;
  event: string;
  /** Proportional Reporting Ratio */
  prr: number;
  severity: SignalSeverity;
  threshold_status: ThresholdStatus;
  rank: number;
  total_cases: number;
}

/** Full disproportionality result for a single drug–event pair. */
export interface SignalResult {
  drug: string;
  event: string;
  /** Drug+Event cases */
  a: number;
  /** Drug+Other-event cases */
  b: number;
  /** Other-drug+Event cases */
  c: number;
  /** Other-drug+Other-event cases */
  d: number;
  prr: number;
  prr_lower_ci?: number;
  prr_upper_ci?: number;
  threshold_status: ThresholdStatus;
  severity: SignalSeverity;
  rank: number;
  algorithm_version: string;
  disclaimer: string;
  event_cluster?: EventCluster;
}

export interface SignalRead {
  id: number;
  project_id: number;
  job_id: number;
  title: string;
  description: string;
  severity: SignalSeverity;
  source_ref?: string;
  result?: SignalResult;
  created_at: string;
}

export interface SignalList {
  items: SignalRead[];
  total: number;
}

export interface SignalSummaryList {
  items: SignalSummary[];
  total: number;
}

// ---------------------------------------------------------------------------
// CTD / Dossier
// ---------------------------------------------------------------------------

export type CtdModule = "1" | "2" | "3" | "4" | "5";
export type SectionStatus =
  | "complete"
  | "missing"
  | "ambiguous"
  | "optional"
  | "review_needed";

export interface CtdRequirement {
  /** Stable ID, e.g. "CTD-3.2.S.1" */
  requirement_id: string;
  module: CtdModule;
  /** e.g. "3.2.S.1" */
  section: string;
  title: string;
  description: string;
  is_mandatory: boolean;
  /** e.g. ICH guideline reference */
  guidance_ref?: string;
}

export interface DossierSection {
  section_id: string;
  module: CtdModule;
  title: string;
  content_summary?: string;
  status: SectionStatus;
  /** e.g. "p.42" or document filename */
  page_ref?: string;
}

export interface RequirementMapping {
  requirement_id: string;
  dossier_section_id?: string;
  status: SectionStatus;
  notes?: string;
}

// ---------------------------------------------------------------------------
// Readiness Assessment
// ---------------------------------------------------------------------------

export type ReviewStatus =
  | "not_started"
  | "in_progress"
  | "approved"
  | "rejected";

export interface ModuleScore {
  module: CtdModule;
  /** 0.0–1.0 */
  score: number;
  complete_count: number;
  missing_count: number;
  ambiguous_count: number;
  review_needed_count: number;
  optional_count: number;
}

export type GapSeverity = "low" | "medium" | "high";

export interface GapResult {
  gap_id: string;
  requirement_id: string;
  dossier_section_id?: string;
  description: string;
  severity: GapSeverity;
  recommendation: string;
  review_status: ReviewStatus;
  notes?: string;
}

export interface GapList {
  items: GapResult[];
  total: number;
}

export interface ReadinessAssessmentRead {
  id: number;
  project_id: number;
  job_id: number;
  /** 0.0–1.0 */
  overall_score: number;
  summary: string;
  module_scores: ModuleScore[];
  gaps: GapResult[];
  requirement_mappings: RequirementMapping[];
  review_status: ReviewStatus;
  algorithm_version: string;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Legacy aliases (kept for existing code that imported the old names)
// ---------------------------------------------------------------------------

/** @deprecated Use GapResult */
export type GapRead = GapResult;

export interface RequirementRead {
  id: number;
  project_id: number;
  text: string;
  source_ref?: string;
  created_at: string;
}

export interface RequirementList {
  items: RequirementRead[];
  total: number;
}
