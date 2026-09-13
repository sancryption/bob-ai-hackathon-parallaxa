/**
 * Signal Detection page.
 *
 * States:
 *   upload  → UploadZone + submit button
 *   polling → JobPoller (queued / running / failed)
 *   results → summary metrics, ranked table, clusters drawer, export buttons
 */
import { useEffect, useState, useCallback } from "react";
import { api, ApiError } from "../lib/apiClient";
import type { JobRead, SignalSummary } from "../types/api";
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
  Tabs,
} from "../components/shared";

const SIGNAL_DISCLAIMER =
  "These results are generated from post-marketing spontaneous reports and " +
  "do not constitute proof of causality. For investigational use only.";

interface SignalDetectionPageProps {
  projectId: number;
}

export function SignalDetectionPage({ projectId }: SignalDetectionPageProps) {
  const [tab, setTab] = useState("Upload");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<number | null>(null);

  // Check for existing completed job on mount
  const [initialChecking, setInitialChecking] = useState(true);
  const [hasResults, setHasResults] = useState(false);

  useEffect(() => {
    api.getSignalSummary(projectId)
      .then(() => { setHasResults(true); setTab("Results"); })
      .catch(() => { /* no results yet */ })
      .finally(() => setInitialChecking(false));
  }, [projectId]);

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    try {
      const res = await api.uploadSignal(projectId, file);
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
        <h1 className="sr-page-title">Signal Detection</h1>
        <p className="sr-page-subtitle">
          Upload a FAERS-compatible CSV or JSON file to run the PRR-based
          disproportionality analysis.
        </p>
      </div>

      <Tabs tabs={tabs} active={tab} onChange={setTab} />

      {tab === "Upload" && (
        <div style={{ maxWidth: 560 }}>
          <UploadZone
            accept=".csv,.json"
            hint="CSV or JSON file — FAERS-compatible format"
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
              {uploading ? "Uploading…" : "Run Signal Detection"}
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
            <Empty icon="📋" message="No job running. Upload a file to start." />
          )}
        </div>
      )}

      {tab === "Results" && <SignalResults projectId={projectId} />}

      <DisclaimerPanel text={SIGNAL_DISCLAIMER} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Signal results view
// ---------------------------------------------------------------------------

function SignalResults({ projectId }: { projectId: number }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<{
    job_id: number;
    total_signals: number;
    signals_above_threshold: number;
    rows_used?: number;
    distinct_drugs?: number;
    algorithm_version: string;
    completed_at: string;
  } | null>(null);
  const [signals, setSignals] = useState<SignalSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [severityFilter, setSeverityFilter] = useState("");
  const [selectedSignal, setSelectedSignal] = useState<SignalSummary | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sumRes, sigRes] = await Promise.all([
        api.getSignalSummary(projectId),
        api.listSignals(projectId, { severity: severityFilter || undefined, limit: 100 }),
      ]);
      setSummary(sumRes.data);
      setSignals(sigRes.data.items);
      setTotal(sigRes.data.total);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load results");
    } finally {
      setLoading(false);
    }
  }, [projectId, severityFilter]);

  useEffect(() => { load(); }, [load]);

  async function exportFile(fmt: "json" | "csv") {
    setExportError(null);
    try {
      const res = await api.exportSignals(projectId, fmt);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `signals_project_${projectId}.${fmt}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setExportError(e instanceof ApiError ? e.message : "Export failed");
    }
  }

  if (loading) return <Loading />;
  if (error) return <ErrorPanel message={error} onRetry={load} />;
  if (!summary) return <Empty icon="📊" message="No results yet." />;

  return (
    <div>
      {/* Metrics */}
      <div className="sr-metric-grid">
        <MetricCard label="Total signals" value={summary.total_signals} />
        <MetricCard label="Above threshold" value={summary.signals_above_threshold} />
        <MetricCard label="Rows used" value={summary.rows_used ?? "—"} />
        <MetricCard label="Drugs" value={summary.distinct_drugs ?? "—"} />
        <MetricCard
          label="Algorithm"
          value={<span className="sr-mono">{summary.algorithm_version}</span>}
        />
      </div>

      {/* Filter bar */}
      <div className="sr-filter-bar">
        <span style={{ fontSize: "0.85rem", color: "var(--text)" }}>Severity:</span>
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          aria-label="Filter by severity"
        >
          <option value="">All</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <span style={{ fontSize: "0.8rem", color: "var(--text)", marginLeft: "auto" }}>
          {total} signal{total !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Export */}
      <div className="sr-export-group sr-mb-md">
        <ExportButton label="Export JSON" onExport={() => exportFile("json")} />
        <ExportButton label="Export CSV" onExport={() => exportFile("csv")} />
      </div>
      {exportError && <ErrorPanel message={exportError} />}

      {/* Signals table */}
      {signals.length === 0 ? (
        <Empty icon="🔍" message="No signals match the current filter." />
      ) : (
        <div className="sr-table-wrap">
          <table className="sr-table" aria-label="Signal results">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Drug</th>
                <th>Event</th>
                <th>PRR</th>
                <th>Cases (a)</th>
                <th>Severity</th>
                <th>Threshold</th>
              </tr>
            </thead>
            <tbody>
              {signals.map((s, i) => (
                <tr
                  key={i}
                  onClick={() => setSelectedSignal(s)}
                  className={selectedSignal === s ? "selected" : ""}
                >
                  <td>{s.rank}</td>
                  <td><strong>{s.drug}</strong></td>
                  <td>{s.event}</td>
                  <td className="sr-mono">{s.prr.toFixed(2)}</td>
                  <td>{s.total_cases}</td>
                  <td><Badge value={s.severity} /></td>
                  <td><Badge value={s.threshold_status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Signal detail drawer */}
      {selectedSignal && (
        <Drawer
          title={`${selectedSignal.drug} — ${selectedSignal.event}`}
          onClose={() => setSelectedSignal(null)}
        >
          <div>
            <p className="sr-drawer-section-label">PRR</p>
            <p className="sr-drawer-section-value sr-mono">{selectedSignal.prr.toFixed(3)}</p>
          </div>
          <hr className="sr-drawer-sep" />
          <div>
            <p className="sr-drawer-section-label">Severity</p>
            <Badge value={selectedSignal.severity} />
          </div>
          <div>
            <p className="sr-drawer-section-label">Threshold</p>
            <Badge value={selectedSignal.threshold_status} />
          </div>
          <div>
            <p className="sr-drawer-section-label">Cases (a)</p>
            <p className="sr-drawer-section-value">{selectedSignal.total_cases}</p>
          </div>
          <div>
            <p className="sr-drawer-section-label">Rank</p>
            <p className="sr-drawer-section-value">{selectedSignal.rank}</p>
          </div>
        </Drawer>
      )}
    </div>
  );
}
