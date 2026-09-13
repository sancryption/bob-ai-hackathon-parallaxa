/**
 * Typed API client.  All fetch calls go through here so base URL and
 * error handling are centralised.  The `multipart` helper bypasses the
 * JSON Content-Type header so the browser can set the correct boundary.
 */
import type {
  ErrorEnvelope,
  GapResult,
  JobRead,
  OkEnvelope,
  ProjectCreate,
  ProjectList,
  ProjectRead,
  ReadinessAssessmentRead,
  RequirementsMatrixResponse,
  ReviewStatus,
  SignalRead,
  SignalSummaryList,
} from "../types/api";

export type { RequirementsMatrixResponse };

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<OkEnvelope<T>> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });

  const json = await response.json();

  if (!response.ok) {
    const envelope = json as ErrorEnvelope;
    throw new ApiError(
      response.status,
      envelope.error?.code ?? "UNKNOWN",
      envelope.error?.message ?? "Unknown error",
    );
  }

  return json as OkEnvelope<T>;
}

async function multipart<T>(
  path: string,
  form: FormData,
  method = "POST",
): Promise<OkEnvelope<T>> {
  const response = await fetch(`${BASE_URL}${path}`, { method, body: form });
  const json = await response.json();
  if (!response.ok) {
    const envelope = json as ErrorEnvelope;
    throw new ApiError(
      response.status,
      envelope.error?.code ?? "UNKNOWN",
      envelope.error?.message ?? "Unknown error",
    );
  }
  return json as OkEnvelope<T>;
}

async function download(path: string): Promise<Response> {
  const response = await fetch(`${BASE_URL}${path}`);
  if (!response.ok) throw new ApiError(response.status, "DOWNLOAD_ERROR", "Export failed");
  return response;
}

// ---------------------------------------------------------------------------
// Signal summary type (extended with processing metrics)
// ---------------------------------------------------------------------------

export interface SignalSummaryData {
  job_id: number;
  total_signals: number;
  signals_above_threshold: number;
  rows_used?: number;
  total_raw_rows?: number;
  duplicate_rows?: number;
  excluded_rows?: number;
  distinct_drugs?: number;
  distinct_events?: number;
  algorithm_version: string;
  completed_at: string;
}

export interface ClustersData {
  job_id: number;
  clusters: Array<{
    preferred_term: string;
    raw_aliases: string[];
    meddra_code?: string;
    case_count: number;
    provenances: Array<{
      raw_term: string;
      preferred_term: string;
      meddra_code?: string;
      method: string;
      confidence: number;
    }>;
  }>;
  total: number;
}

// ---------------------------------------------------------------------------
// Typed endpoints
// ---------------------------------------------------------------------------

export const api = {
  // generic helpers kept for existing code
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),

  // Projects
  createProject: (payload: ProjectCreate) =>
    request<ProjectRead>("/api/projects", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listProjects: (offset = 0, limit = 50) =>
    request<ProjectList>(`/api/projects?offset=${offset}&limit=${limit}`),
  getProject: (id: number) => request<ProjectRead>(`/api/projects/${id}`),

  // Jobs
  getJob: (jobId: number) => request<JobRead>(`/api/jobs/${jobId}`),
  listProjectJobs: (projectId: number) =>
    request<{ items: JobRead[]; total: number }>(`/api/projects/${projectId}/jobs`),
  listProjectResults: (projectId: number) =>
    request<{ items: unknown[]; total: number }>(`/api/projects/${projectId}/results`),

  // Signal detection
  uploadSignal: (projectId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return multipart<JobRead>(`/api/projects/${projectId}/signals/upload`, form);
  },
  getSignalSummary: (projectId: number) =>
    request<SignalSummaryData>(`/api/projects/${projectId}/signals/summary`),
  listSignals: (projectId: number, params?: { severity?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params?.severity) q.set("severity", params.severity);
    if (params?.limit !== undefined) q.set("limit", String(params.limit));
    if (params?.offset !== undefined) q.set("offset", String(params.offset));
    return request<SignalSummaryList>(`/api/projects/${projectId}/signals?${q}`);
  },
  getSignal: (projectId: number, signalId: number) =>
    request<SignalRead>(`/api/projects/${projectId}/signals/${signalId}`),
  getClusters: (projectId: number) =>
    request<ClustersData>(`/api/projects/${projectId}/signals/clusters`),
  exportSignals: (projectId: number, fmt: "json" | "csv") =>
    download(`/api/projects/${projectId}/signals/export?fmt=${fmt}`),

  // Readiness assessment
  uploadReadiness: (projectId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return multipart<JobRead>(`/api/projects/${projectId}/readiness/upload`, form);
  },
  getReadinessSummary: (projectId: number) =>
    request<ReadinessAssessmentRead>(`/api/projects/${projectId}/readiness/summary`),
  getModuleScores: (projectId: number) =>
    request<{ assessment_id: number; overall_score: number; module_scores: unknown[] }>(
      `/api/projects/${projectId}/readiness/modules`,
    ),
  getRequirementsMatrix: (projectId: number) =>
    request<RequirementsMatrixResponse>(`/api/projects/${projectId}/readiness/requirements`),
  listGaps: (projectId: number, params?: { severity?: string; review_status?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.severity) q.set("severity", params.severity);
    if (params?.review_status) q.set("review_status", params.review_status);
    if (params?.limit !== undefined) q.set("limit", String(params.limit));
    return request<{ items: GapResult[]; total: number }>(
      `/api/projects/${projectId}/readiness/gaps?${q}`,
    );
  },
  updateGapReview: (projectId: number, gapId: number, review_status: ReviewStatus, notes?: string) =>
    request<GapResult>(`/api/projects/${projectId}/readiness/gaps/${gapId}`, {
      method: "PATCH",
      body: JSON.stringify({ review_status, notes }),
    }),
  exportReadiness: (projectId: number, fmt: "json" | "markdown") =>
    download(`/api/projects/${projectId}/readiness/export?fmt=${fmt}`),
};
