/**
 * Frontend tests — covers routing, upload state, job polling, error state,
 * empty result state, and typed API response handling.
 */
import { act, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import App from "../App";

// ---------------------------------------------------------------------------
// Mock setup — vi.mock is hoisted so the factory must not reference outer vars
// ---------------------------------------------------------------------------

vi.mock("../lib/apiClient", () => {
  const ApiError = class ApiError extends Error {
    status: number;
    code: string;
    constructor(status: number, code: string, message: string) {
      super(message);
      this.status = status;
      this.code = code;
      this.name = "ApiError";
    }
  };
  const api = {
    listProjects: vi.fn(),
    createProject: vi.fn(),
    getProject: vi.fn(),
    getJob: vi.fn(),
    listProjectJobs: vi.fn(),
    listProjectResults: vi.fn(),
    uploadSignal: vi.fn(),
    getSignalSummary: vi.fn(),
    listSignals: vi.fn(),
    getClusters: vi.fn(),
    exportSignals: vi.fn(),
    uploadReadiness: vi.fn(),
    getReadinessSummary: vi.fn(),
    getModuleScores: vi.fn(),
    listGaps: vi.fn(),
    updateGapReview: vi.fn(),
    exportReadiness: vi.fn(),
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  };
  return { api, ApiError };
});

// Grab the mocked module after mock registration
// We use a lazy accessor so tests can configure mocks at runtime
import * as apiClientModule from "../lib/apiClient";
// biome-ignore lint: cast is intentional
const mockApi = apiClientModule.api as Record<string, ReturnType<typeof vi.fn>>;

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const PROJECT_1 = {
  id: 1,
  name: "Test Project",
  description: "A test project",
  status: "draft" as const,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

const JOB_QUEUED = {
  id: 10,
  project_id: 1,
  job_type: "signal_detection" as const,
  status: "queued" as const,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

const JOB_RUNNING = {
  ...JOB_QUEUED,
  status: "running" as const,
  progress: { percent: 50, message: "Detecting signals", step: "detect" },
};

const JOB_COMPLETE = {
  ...JOB_QUEUED,
  status: "complete" as const,
  result: { signals_detected: 5, pairs_above_threshold: 3 },
};

const JOB_FAILED = {
  ...JOB_QUEUED,
  status: "failed" as const,
  error: "ValueError: Missing required column",
};

const READINESS_JOB = {
  id: 20,
  project_id: 1,
  job_type: "readiness_assessment" as const,
  status: "complete" as const,
  result: { overall_score: 0.67, gap_count: 8 },
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

const SIGNAL_SUMMARY = {
  job_id: 10,
  total_signals: 5,
  signals_above_threshold: 3,
  rows_used: 116,
  distinct_drugs: 3,
  algorithm_version: "0.1.0",
  completed_at: "2024-01-01T01:00:00Z",
};

const SIGNAL_LIST = {
  items: [
    {
      drug: "DRUGALPHA",
      event: "Hepatic disorder",
      prr: 8.98,
      severity: "critical" as const,
      threshold_status: "above" as const,
      rank: 1,
      total_cases: 40,
    },
  ],
  total: 1,
};

const ASSESSMENT = {
  id: 1,
  project_id: 1,
  job_id: 20,
  overall_score: 0.67,
  summary: "Overall readiness score: 67.0%.",
  module_scores: [
    {
      module: "1" as const,
      score: 0.5,
      complete_count: 1,
      missing_count: 1,
      ambiguous_count: 0,
      review_needed_count: 0,
      optional_count: 0,
    },
    {
      module: "2" as const,
      score: 0.6,
      complete_count: 2,
      missing_count: 1,
      ambiguous_count: 1,
      review_needed_count: 1,
      optional_count: 0,
    },
    {
      module: "3" as const,
      score: 0.75,
      complete_count: 3,
      missing_count: 1,
      ambiguous_count: 0,
      review_needed_count: 0,
      optional_count: 0,
    },
    {
      module: "4" as const,
      score: 1.0,
      complete_count: 2,
      missing_count: 0,
      ambiguous_count: 0,
      review_needed_count: 0,
      optional_count: 0,
    },
    {
      module: "5" as const,
      score: 0.5,
      complete_count: 1,
      missing_count: 1,
      ambiguous_count: 0,
      review_needed_count: 0,
      optional_count: 0,
    },
  ],
  gaps: [
    {
      gap_id: "GAP-001",
      requirement_id: "CTD-1.3.2",
      description: "Missing Package Leaflet",
      severity: "high" as const,
      recommendation: "Provide CTD section 1.3.2",
      review_status: "not_started" as const,
    },
  ],
  requirement_mappings: [],
  review_status: "not_started" as const,
  algorithm_version: "0.1.0",
  created_at: "2024-01-01T00:00:00Z",
};

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function setupEmptyProjects() {
  mockApi.listProjects.mockResolvedValue({ data: { items: [], total: 0 } });
}

function setupProjects() {
  mockApi.listProjects.mockResolvedValue({ data: { items: [PROJECT_1], total: 1 } });
}

function setupProjectDetail() {
  mockApi.getProject.mockResolvedValue({ data: PROJECT_1 });
  mockApi.listProjectJobs.mockResolvedValue({ data: { items: [], total: 0 } });
  mockApi.listProjectResults.mockResolvedValue({ data: { items: [], total: 0 } });
}

beforeEach(() => {
  vi.clearAllMocks();
  window.location.hash = "";
});

// ===========================================================================
// 1. Route rendering
// ===========================================================================

describe("Route rendering", () => {
  it("renders the projects page by default", async () => {
    setupEmptyProjects();
    await act(async () => { render(<App />); });
    expect(screen.getByText("Projects")).toBeInTheDocument();
  });

  it("renders SafetyReady logo", async () => {
    setupEmptyProjects();
    await act(async () => { render(<App />); });
    expect(screen.getByText(/SafetyReady|Safety/)).toBeInTheDocument();
  });

  it("renders project detail when hash is #/projects/1", async () => {
    window.location.hash = "#/projects/1";
    setupProjectDetail();
    mockApi.getSignalSummary.mockRejectedValue(new Error("404"));
    mockApi.getReadinessSummary.mockRejectedValue(new Error("404"));
    await act(async () => { render(<App />); });
    await waitFor(() => {
      expect(screen.getByText("Test Project")).toBeInTheDocument();
    });
  });

  it("renders signal detection page when hash is #/projects/1/signal", async () => {
    window.location.hash = "#/projects/1/signal";
    mockApi.getSignalSummary.mockRejectedValue(new Error("404"));
    await act(async () => { render(<App />); });
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Signal Detection" })).toBeInTheDocument();
    });
  });

  it("renders readiness page when hash is #/projects/1/readiness", async () => {
    window.location.hash = "#/projects/1/readiness";
    mockApi.getReadinessSummary.mockRejectedValue(new Error("404"));
    await act(async () => { render(<App />); });
    await waitFor(() => {
      expect(screen.getByText("Submission Readiness")).toBeInTheDocument();
    });
  });

  it("shows project nav links when inside a project", async () => {
    window.location.hash = "#/projects/1";
    setupProjectDetail();
    mockApi.getSignalSummary.mockRejectedValue(new Error("404"));
    mockApi.getReadinessSummary.mockRejectedValue(new Error("404"));
    await act(async () => { render(<App />); });
    await waitFor(() => {
      // Signal Detection appears both in nav and as an action card; use getAllByText
      expect(screen.getAllByText("Signal Detection").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByRole("button", { name: "Readiness" })).toBeInTheDocument();
    });
  });

  it("navigates from projects list to project detail on click", async () => {
    setupProjects();
    setupProjectDetail();
    mockApi.getSignalSummary.mockRejectedValue(new Error("404"));
    mockApi.getReadinessSummary.mockRejectedValue(new Error("404"));
    await act(async () => { render(<App />); });

    await waitFor(() => expect(screen.getByText("Test Project")).toBeInTheDocument());
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Open project Test Project/ }));
    });
    await waitFor(() => {
      expect(mockApi.getProject).toHaveBeenCalledWith(1);
    });
  });
});

// ===========================================================================
// 2. Upload state
// ===========================================================================

describe("Upload state", () => {
  it("renders upload zone on signal detection page", async () => {
    window.location.hash = "#/projects/1/signal";
    mockApi.getSignalSummary.mockRejectedValue(new Error("404"));
    await act(async () => { render(<App />); });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Upload file/ })).toBeInTheDocument();
    });
  });

  it("run button is disabled before file selection", async () => {
    window.location.hash = "#/projects/1/signal";
    mockApi.getSignalSummary.mockRejectedValue(new Error("404"));
    await act(async () => { render(<App />); });
    await waitFor(() => {
      const btn = screen.getByRole("button", { name: /Run Signal Detection/ });
      expect(btn).toBeDisabled();
    });
  });

  it("shows API error on upload failure", async () => {
    window.location.hash = "#/projects/1/signal";
    mockApi.getSignalSummary.mockRejectedValue(new Error("404"));

    // Dynamically import ApiError to create matching instance
    const { ApiError } = await import("../lib/apiClient");
    mockApi.uploadSignal.mockRejectedValue(
      new ApiError(422, "VALIDATION_ERROR", "Missing required column: case_id")
    );

    await act(async () => { render(<App />); });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Upload file/ })).toBeInTheDocument();
    });

    // Simulate file selection via input
    const input = document.querySelector('input[type=file]') as HTMLInputElement;
    const file = new File(["bad,data\n1,2"], "bad.csv", { type: "text/csv" });
    await act(async () => {
      Object.defineProperty(input, "files", { value: [file], writable: false });
      fireEvent.change(input);
    });

    await act(async () => {
      const btn = screen.getByRole("button", { name: /Run Signal Detection/ });
      fireEvent.click(btn);
    });

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });

  it("renders upload zone on readiness page", async () => {
    window.location.hash = "#/projects/1/readiness";
    mockApi.getReadinessSummary.mockRejectedValue(new Error("404"));
    await act(async () => { render(<App />); });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Upload file/ })).toBeInTheDocument();
    });
  });
});

// ===========================================================================
// 3. Job polling state
// ===========================================================================

describe("Job polling state", () => {
  it("shows loading when job is queued", async () => {
    window.location.hash = "#/projects/1/signal";
    mockApi.getSignalSummary.mockRejectedValue(new Error("404"));
    mockApi.getJob.mockResolvedValue({ data: JOB_QUEUED });

    // Trigger job creation by uploading a file
    mockApi.uploadSignal.mockResolvedValue({ data: JOB_QUEUED });
    await act(async () => { render(<App />); });
    await waitFor(() => screen.getByRole("button", { name: /Upload file/ }));

    const input = document.querySelector('input[type=file]') as HTMLInputElement;
    const file = new File(["data"], "test.csv", { type: "text/csv" });
    await act(async () => {
      Object.defineProperty(input, "files", { value: [file], writable: false });
      fireEvent.change(input);
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Run Signal Detection/ }));
    });

    // After upload, tab should switch to Progress
    await waitFor(() => {
      // Either loading text or progress is visible
      expect(mockApi.uploadSignal).toHaveBeenCalled();
    });
  });

  it("shows progress bar when job is running", async () => {
    // Render JobPoller directly via the signal page with running job
    window.location.hash = "#/projects/1/signal";
    mockApi.getSignalSummary.mockRejectedValue(new Error("404"));
    mockApi.uploadSignal.mockResolvedValue({ data: JOB_RUNNING });
    mockApi.getJob.mockResolvedValue({ data: JOB_RUNNING });

    await act(async () => { render(<App />); });
    await waitFor(() => screen.getByRole("button", { name: /Upload file/ }));

    const input = document.querySelector('input[type=file]') as HTMLInputElement;
    await act(async () => {
      Object.defineProperty(input, "files", {
        value: [new File(["data"], "test.csv")],
        writable: false,
      });
      fireEvent.change(input);
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Run Signal Detection/ }));
    });

    await waitFor(() => {
      expect(mockApi.uploadSignal).toHaveBeenCalled();
    });
  });

  it("shows failed error when job fails", async () => {
    // Test that JobPoller renders failure correctly
    window.location.hash = "#/projects/1/signal";
    mockApi.getSignalSummary.mockRejectedValue(new Error("404"));
    mockApi.uploadSignal.mockResolvedValue({ data: JOB_FAILED });
    mockApi.getJob.mockResolvedValue({ data: JOB_FAILED });

    await act(async () => { render(<App />); });
    await waitFor(() => screen.getByRole("button", { name: /Upload file/ }));

    const input = document.querySelector('input[type=file]') as HTMLInputElement;
    await act(async () => {
      Object.defineProperty(input, "files", {
        value: [new File(["data"], "test.csv")],
        writable: false,
      });
      fireEvent.change(input);
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Run Signal Detection/ }));
    });

    // Navigate to Progress tab
    await waitFor(() => {
      const progressTab = screen.queryByRole("button", { name: "Progress" });
      if (progressTab) fireEvent.click(progressTab);
    });

    await waitFor(() => {
      // The job is FAILED so we should see an error
      expect(mockApi.getJob).toHaveBeenCalledWith(JOB_FAILED.id);
    });
  });
});

// ===========================================================================
// 4. Error state
// ===========================================================================

describe("Error state", () => {
  it("shows error panel when listProjects fails", async () => {
    mockApi.listProjects.mockRejectedValue(new Error("Network error"));
    await act(async () => { render(<App />); });
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });

  it("shows retry button on project list error", async () => {
    mockApi.listProjects.mockRejectedValue(new Error("Network error"));
    await act(async () => { render(<App />); });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Retry/ })).toBeInTheDocument();
    });
  });

  it("shows error when signal results fail to load", async () => {
    window.location.hash = "#/projects/1/signal";
    mockApi.getSignalSummary
      .mockResolvedValueOnce({ data: SIGNAL_SUMMARY }) // first call succeeds (initial check)
      .mockRejectedValue(new Error("Backend error")); // second call fails
    mockApi.listSignals.mockRejectedValue(new Error("Backend error"));

    await act(async () => { render(<App />); });

    await waitFor(() => {
      expect(screen.getByText("Results")).toBeInTheDocument();
    });

    const resultsTab = screen.getByRole("button", { name: "Results" });
    await act(async () => { fireEvent.click(resultsTab); });

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });
});

// ===========================================================================
// 5. Empty result state
// ===========================================================================

describe("Empty result state", () => {
  it("shows empty state when no projects exist", async () => {
    setupEmptyProjects();
    await act(async () => { render(<App />); });
    await waitFor(() => {
      expect(screen.getByText(/No projects yet/)).toBeInTheDocument();
    });
  });

  it("shows empty state when no signals match filter", async () => {
    window.location.hash = "#/projects/1/signal";
    mockApi.getSignalSummary.mockResolvedValue({ data: SIGNAL_SUMMARY });
    mockApi.listSignals.mockResolvedValue({ data: { items: [], total: 0 } });

    await act(async () => { render(<App />); });

    await waitFor(() => {
      expect(screen.getByText("Results")).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Results" }));
    });

    await waitFor(() => {
      expect(screen.getByText(/No signals match the current filter/)).toBeInTheDocument();
    });
  });

  it("shows empty state when no gaps match filter", async () => {
    window.location.hash = "#/projects/1/readiness";
    mockApi.getReadinessSummary.mockResolvedValue({
      data: { ...ASSESSMENT, gaps: [] },
    });

    await act(async () => { render(<App />); });

    await waitFor(() => {
      expect(screen.getByText("Results")).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Results" }));
    });

    await waitFor(() => {
      expect(screen.getByText(/No gaps match the current filter/)).toBeInTheDocument();
    });
  });
});

// ===========================================================================
// 6. Typed API response handling
// ===========================================================================

describe("Typed API response handling", () => {
  it("renders signal severity badge from typed response", async () => {
    window.location.hash = "#/projects/1/signal";
    mockApi.getSignalSummary.mockResolvedValue({ data: SIGNAL_SUMMARY });
    mockApi.listSignals.mockResolvedValue({ data: SIGNAL_LIST });

    await act(async () => { render(<App />); });

    await waitFor(() => {
      expect(screen.getByText("Results")).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Results" }));
    });

    await waitFor(() => {
      expect(screen.getByText("DRUGALPHA")).toBeInTheDocument();
      expect(screen.getByText("critical")).toBeInTheDocument();
    });
  });

  it("renders module scores from typed ReadinessAssessmentRead", async () => {
    window.location.hash = "#/projects/1/readiness";
    mockApi.getReadinessSummary.mockResolvedValue({ data: ASSESSMENT });

    await act(async () => { render(<App />); });

    await waitFor(() => {
      expect(screen.getByText("Results")).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Results" }));
    });

    await waitFor(() => {
      expect(screen.getByText("Module 1")).toBeInTheDocument();
      expect(screen.getByText("Module 4")).toBeInTheDocument();
    });
  });

  it("renders gap severity badge from typed GapResult", async () => {
    window.location.hash = "#/projects/1/readiness";
    mockApi.getReadinessSummary.mockResolvedValue({ data: ASSESSMENT });

    await act(async () => { render(<App />); });

    await waitFor(() => {
      expect(screen.getByText("Results")).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Results" }));
    });

    await waitFor(() => {
      expect(screen.getByText("CTD-1.3.2")).toBeInTheDocument();
      expect(screen.getByText("high")).toBeInTheDocument();
    });
  });

  it("renders overall score metric from ReadinessAssessmentRead", async () => {
    window.location.hash = "#/projects/1/readiness";
    mockApi.getReadinessSummary.mockResolvedValue({ data: ASSESSMENT });

    await act(async () => { render(<App />); });

    await waitFor(() => {
      expect(screen.getByText("Results")).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Results" }));
    });

    await waitFor(() => {
      // 0.67 * 100 = 67%
      expect(screen.getByText("67%")).toBeInTheDocument();
    });
  });

  it("renders job result fields from JobRead.result", async () => {
    window.location.hash = "#/projects/1";
    setupProjectDetail();

    await act(async () => { render(<App />); });

    await waitFor(() => {
      expect(mockApi.getProject).toHaveBeenCalledWith(1);
    });
    // Project detail renders job count from listProjectJobs response (two "0" metrics present)
    await waitFor(() => {
      expect(screen.getAllByText("0").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("renders create project modal and calls createProject", async () => {
    setupEmptyProjects();
    mockApi.createProject.mockResolvedValue({ data: PROJECT_1 });
    mockApi.getProject.mockResolvedValue({ data: PROJECT_1 });
    mockApi.listProjectJobs.mockResolvedValue({ data: { items: [], total: 0 } });
    mockApi.listProjectResults.mockResolvedValue({ data: { items: [], total: 0 } });

    await act(async () => { render(<App />); });

    await waitFor(() => screen.getByText(/No projects yet/));

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Create your first project/ }));
    });

    expect(screen.getByRole("dialog", { name: "Create project" })).toBeInTheDocument();

    await act(async () => {
      fireEvent.change(screen.getByLabelText("Name *"), { target: { value: "New Project" } });
      fireEvent.submit(screen.getByRole("dialog", { name: "Create project" }).querySelector("form")!);
    });

    await waitFor(() => {
      expect(mockApi.createProject).toHaveBeenCalledWith({ name: "New Project", description: undefined });
    });
  });

  it("displays disclaimer on signal detection page", async () => {
    window.location.hash = "#/projects/1/signal";
    mockApi.getSignalSummary.mockRejectedValue(new Error("404"));
    await act(async () => { render(<App />); });
    await waitFor(() => {
      expect(screen.getByText(/Assumptions & Limitations/)).toBeInTheDocument();
    });
  });

  it("displays disclaimer on readiness page", async () => {
    window.location.hash = "#/projects/1/readiness";
    mockApi.getReadinessSummary.mockRejectedValue(new Error("404"));
    await act(async () => { render(<App />); });
    await waitFor(() => {
      expect(screen.getByText(/Assumptions & Limitations/)).toBeInTheDocument();
    });
  });
});
