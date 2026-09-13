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
  ReviewStatus,
  SignalSummaryList,
} from "../types/api";

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
    request<{
      job_id: number;
      total_signals: number;
      signals_above_threshold: number;
      rows_used?: number;
      distinct_drugs?: number;
      algorithm_version: string;
      completed_at: string;
    }>(`/api/projects/${projectId}/signals/summary`),
  listSignals: (projectId: number, params?: { severity?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params?.severity) q.set("severity", params.severity);
    if (params?.limit !== undefined) q.set("limit", String(params.limit));
    if (params?.offset !== undefined) q.set("offset", String(params.offset));
    return request<SignalSummaryList>(`/api/projects/${projectId}/signals?${q}`);
  },
  getClusters: (projectId: number) =>
    request<{ job_id: number; clusters: unknown[]; total: number }>(
      `/api/projects/${projectId}/signals/clusters`,
    ),
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
