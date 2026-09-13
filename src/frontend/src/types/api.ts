/**
 * Shared API contract types — mirrors backend app/schemas.py.
 * These are the single source of truth for the frontend API surface.
 */

// ---------------------------------------------------------------------------
// Generic envelopes
// ---------------------------------------------------------------------------

export interface ErrorDetail {
  code: string;
  message: string;
  field?: string;
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
  status: UploadStatus;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Job
// ---------------------------------------------------------------------------

export type JobType = "signal_detection" | "readiness_assessment";
export type JobStatus = "queued" | "running" | "complete" | "failed";

export interface JobRead {
  id: number;
  project_id: number;
  job_type: JobType;
  status: JobStatus;
  result?: unknown;
  error?: string;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Signal
// ---------------------------------------------------------------------------

export type SignalSeverity = "low" | "medium" | "high" | "critical";

export interface SignalRead {
  id: number;
  project_id: number;
  job_id: number;
  title: string;
  description: string;
  severity: SignalSeverity;
  source_ref?: string;
  created_at: string;
}

export interface SignalList {
  items: SignalRead[];
  total: number;
}

// ---------------------------------------------------------------------------
// Requirement
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Gap
// ---------------------------------------------------------------------------

export type GapSeverity = "low" | "medium" | "high";

export interface GapRead {
  id: number;
  project_id: number;
  requirement_id: number;
  description: string;
  severity: GapSeverity;
  created_at: string;
}

export interface GapList {
  items: GapRead[];
  total: number;
}

// ---------------------------------------------------------------------------
// Readiness Assessment
// ---------------------------------------------------------------------------

export interface ReadinessAssessmentRead {
  id: number;
  project_id: number;
  job_id: number;
  score: number;
  summary: string;
  gaps: GapRead[];
  created_at: string;
}
