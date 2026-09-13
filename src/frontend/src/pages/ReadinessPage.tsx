/**
 * Submission Readiness page.
 *
 * States:
 *   upload  → UploadZone + submit
 *   polling → JobPoller
 *   results → overall score, module bars, gaps table, gap detail drawer, exports
 */
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../lib/apiClient";
import type { GapResult, JobRead, ModuleScore, ReadinessAssessmentRead, ReviewStatus } from "../types/api";
import { UploadZone } from "../components/UploadZone";
import { JobPoller } from "../components/JobPoller";
import {
  Badge,
  DisclaimerPanel,
  Drawer,
  Empty,
  ErrorPanel,
  ExportButton,
  Loading,
  MetricCard,
  ScoreBar,
  Tabs,
} from "../components/shared";

const READINESS_DISCLAIMER =
  "This submission readiness score is a prototype estimate generated from " +
  "structured dossier metadata. It does NOT establish regulatory compliance. " +
  "Always consult current ICH, FDA, EMA, or other applicable authority guidance " +
  "before submitting a regulatory dossier.";

interface ReadinessPageProps {
  projectId: number;
}

export function ReadinessPage({ projectId }: ReadinessPageProps) {
  const [tab, setTab] = useState("Upload");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<number | null>(null);
  const [initialChecking, setInitialChecking] = useState(true);
  const [hasResults, setHasResults] = useState(false);

  useEffect(() => {
    api.getReadinessSummary(projectId)
      .then(() => { setHasResults(true); setTab("Results"); })
      .catch(() => { /* no results yet */ })
      .finally(() => setInitialChecking(false));
  }, [projectId]);

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    try {
      const res = await api.uploadReadiness(projectId, file);
      setActiveJobId(res.data.id);
      setTab("Progress");
    } catch (e) {
      const msg = e instanceof ApiError
        ? `${e.code}: ${e.message}`
        : "Upload failed";
      setUploadError(msg);
    } finally {
      setUploading(false);
    }
  }

  function handleJobComplete(_job: JobRead) {
    setActiveJobId(null);
    setHasResults(true);
    setTab("Results");
  }

  if (initialChecking) return <Loading text="Checking for results…" />;

  const tabs = hasResults
    ? ["Upload", "Progress", "Results"]
    : ["Upload", "Progress"];

  return (
    <div>
      <div className="sr-page-header">
        <h1 className="sr-page-title">Submission Readiness</h1>
        <p className="sr-page-subtitle">
          Upload a CTD dossier outline (JSON or CSV) to assess regulatory
          submission readiness against the prototype ICH CTD catalog.
        </p>
      </div>

      <Tabs tabs={tabs} active={tab} onChange={setTab} />

      {tab === "Upload" && (
        <div style={{ maxWidth: 560 }}>
          <UploadZone
            accept=".json,.csv"
            hint="JSON or CSV dossier outline"
            onFile={setFile}
            disabled={uploading}
          />
          {uploadError && (
            <div style={{ marginTop: "1rem" }}>
              <ErrorPanel message={uploadError} />
            </div>
          )}
          <div style={{ marginTop: "1rem", display: "flex", justifyContent: "flex-end" }}>
            <button
              className="sr-btn sr-btn-primary"
              disabled={!file || uploading}
              onClick={handleUpload}
            >
              {uploading ? "Uploading…" : "Run Assessment"}
            </button>
          </div>
        </div>
      )}

      {tab === "Progress" && (
        <div style={{ maxWidth: 560 }}>
          {activeJobId ? (
            <JobPoller jobId={activeJobId} onComplete={handleJobComplete}>
              {() => null}
            </JobPoller>
          ) : (
            <Empty icon="📋" message="No job running. Upload a dossier outline to start." />
          )}
        </div>
      )}

      {tab === "Results" && <ReadinessResults projectId={projectId} />}

      <DisclaimerPanel text={READINESS_DISCLAIMER} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Readiness results view
// ---------------------------------------------------------------------------

function ReadinessResults({ projectId }: { projectId: number }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [assessment, setAssessment] = useState<ReadinessAssessmentRead | null>(null);
  const [severityFilter, setSeverityFilter] = useState("");
  const [reviewFilter, setReviewFilter] = useState("");
  const [selectedGap, setSelectedGap] = useState<GapResult | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getReadinessSummary(projectId);
      setAssessment(res.data);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load assessment");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  async function handleGapReviewUpdate(gap: GapResult, status: ReviewStatus) {
    // The backend PATCH endpoint uses integer DB IDs.
    // We use a best-effort search: the gap_id "GAP-001" → numeric suffix as a hint.
    // For simplicity in this shell, we search by trying numeric ID extraction.
    const match = gap.gap_id.match(/\d+$/);
    if (!match) return;
    const numId = parseInt(match[0], 10);
    try {
      const res = await api.updateGapReview(projectId, numId, status);
      // Update locally
      if (assessment) {
        const updated = assessment.gaps.map((g) =>
          g.gap_id === gap.gap_id ? res.data : g
        );
        setAssessment({ ...assessment, gaps: updated });
        if (selectedGap?.gap_id === gap.gap_id) setSelectedGap(res.data);
      }
    } catch {
      // silently log — review update is non-critical
    }
  }

  async function exportFile(fmt: "json" | "markdown") {
    setExportError(null);
    try {
      const res = await api.exportReadiness(projectId, fmt);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `readiness_project_${projectId}.${fmt === "json" ? "json" : "md"}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setExportError(e instanceof ApiError ? e.message : "Export failed");
    }
  }

  if (loading) return <Loading />;
  if (error) return <ErrorPanel message={error} onRetry={load} />;
  if (!assessment) return <Empty icon="📄" message="No assessment yet." />;

  // Apply filters
  const filteredGaps = assessment.gaps.filter((g) => {
    if (severityFilter && g.severity !== severityFilter) return false;
    if (reviewFilter && g.review_status !== reviewFilter) return false;
    return true;
  });

  return (
    <div>
      {/* Overall score */}
      <div className="sr-metric-grid">
        <MetricCard
          label="Overall Score"
          value={`${Math.round(assessment.overall_score * 100)}%`}
        />
        <MetricCard label="Total Gaps" value={assessment.gaps.length} />
        <MetricCard
          label="High Gaps"
          value={assessment.gaps.filter((g) => g.severity === "high").length}
        />
        <MetricCard
          label="Algorithm"
          value={<span className="sr-mono">{assessment.algorithm_version}</span>}
        />
      </div>

      {/* Summary */}
      <div className="sr-card sr-mb-md">
        <p style={{ fontSize: "0.9rem", color: "var(--text-h)", margin: 0 }}>{assessment.summary}</p>
      </div>

      {/* Module scores */}
      <div className="sr-section">
        <p className="sr-section-title">Module Scores</p>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          {assessment.module_scores.map((ms: ModuleScore) => (
            <ModuleScoreRow key={ms.module} ms={ms} />
          ))}
        </div>
      </div>

      {/* Gap filters + export */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem", marginBottom: "0.75rem" }}>
        <div className="sr-filter-bar" style={{ margin: 0 }}>
          <span style={{ fontSize: "0.85rem", color: "var(--text)" }}>Severity:</span>
          <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)} aria-label="Filter by severity">
            <option value="">All</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <span style={{ fontSize: "0.85rem", color: "var(--text)" }}>Review:</span>
          <select value={reviewFilter} onChange={(e) => setReviewFilter(e.target.value)} aria-label="Filter by review status">
            <option value="">All</option>
            <option value="not_started">Not started</option>
            <option value="in_progress">In progress</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </select>
          <span style={{ fontSize: "0.8rem", color: "var(--text)" }}>
            {filteredGaps.length} gap{filteredGaps.length !== 1 ? "s" : ""}
          </span>
        </div>
        <div className="sr-export-group">
          <ExportButton label="Export JSON" onExport={() => exportFile("json")} />
          <ExportButton label="Export Markdown" onExport={() => exportFile("markdown")} />
        </div>
      </div>
      {exportError && <ErrorPanel message={exportError} />}

      {/* Gaps table */}
      {filteredGaps.length === 0 ? (
        <Empty icon="✅" message="No gaps match the current filter." />
      ) : (
        <div className="sr-table-wrap">
          <table className="sr-table" aria-label="Gap list">
            <thead>
              <tr>
                <th>Gap ID</th>
                <th>Requirement</th>
                <th>Severity</th>
                <th>Review Status</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {filteredGaps.map((g) => (
                <tr
                  key={g.gap_id}
                  onClick={() => setSelectedGap(g)}
                  className={selectedGap?.gap_id === g.gap_id ? "selected" : ""}
                >
                  <td className="sr-mono">{g.gap_id}</td>
                  <td className="sr-mono">{g.requirement_id}</td>
                  <td><Badge value={g.severity} /></td>
                  <td><Badge value={g.review_status} /></td>
                  <td style={{ maxWidth: 320, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {g.description}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Gap detail drawer */}
      {selectedGap && (
        <Drawer
          title={`${selectedGap.gap_id} — ${selectedGap.requirement_id}`}
          onClose={() => setSelectedGap(null)}
        >
          <div>
            <p className="sr-drawer-section-label">Severity</p>
            <Badge value={selectedGap.severity} />
          </div>
          <hr className="sr-drawer-sep" />
          <div>
            <p className="sr-drawer-section-label">Description</p>
            <p className="sr-drawer-section-value">{selectedGap.description}</p>
          </div>
          <div>
            <p className="sr-drawer-section-label">Recommendation</p>
            <p className="sr-drawer-section-value">{selectedGap.recommendation}</p>
          </div>
          <hr className="sr-drawer-sep" />
          <div>
            <p className="sr-drawer-section-label">Review Status</p>
            <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
              {(["not_started", "in_progress", "approved", "rejected"] as ReviewStatus[]).map((s) => (
                <button
                  key={s}
                  className={`sr-btn sr-btn-secondary ${selectedGap.review_status === s ? "active" : ""}`}
                  style={selectedGap.review_status === s
                    ? { borderColor: "var(--accent)", color: "var(--accent)" }
                    : {}}
                  onClick={() => handleGapReviewUpdate(selectedGap, s)}
                >
                  {s.replace("_", " ")}
                </button>
              ))}
            </div>
          </div>
          {selectedGap.notes && (
            <div>
              <p className="sr-drawer-section-label">Notes</p>
              <p className="sr-drawer-section-value">{selectedGap.notes}</p>
            </div>
          )}
        </Drawer>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Module score row
// ---------------------------------------------------------------------------

function ModuleScoreRow({ ms }: { ms: ModuleScore }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
      <span style={{ fontWeight: 600, fontSize: "0.85rem", color: "var(--text-h)", minWidth: 70 }}>
        Module {ms.module}
      </span>
      <div style={{ flex: 1, minWidth: 120 }}>
        <ScoreBar score={ms.score} />
      </div>
      <span style={{ fontSize: "0.78rem", color: "var(--text)", whiteSpace: "nowrap" }}>
        ✓ {ms.complete_count} / ✗ {ms.missing_count} / 🔍 {ms.review_needed_count}
      </span>
    </div>
  );
}
