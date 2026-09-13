/**
 * Signal Detection page.
 *
 * States:
 *   upload   → UploadZone + submit button
 *   polling  → JobPoller (queued / running / failed)
 *   results  → dataset metrics, ranked table, clusters tab, signal detail drawer, export
 */
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../lib/apiClient";
import type { ClustersData, SignalSummaryData } from "../lib/apiClient";
import type { JobRead, SignalRead, SignalResult, SignalSummary } from "../types/api";
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
            hint="CSV or JSON file — FAERS-compatible format (case_id, drug, event columns required)"
            onFile={setFile}
            disabled={uploading}
          />
          {uploadError && (
            <div style={{ marginTop: "1rem" }}>
              <ErrorPanel message={uploadError} />
            </div>
          )}
          <div className="sr-upload-hint-box">
            <strong>Fixture file:</strong> use <code>tests/fixtures/faers_demo.csv</code> for a live demo.
          </div>
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
// Results view — metrics + ranked table + clusters tab
// ---------------------------------------------------------------------------

type ResultsTab = "Signals" | "Clusters";

function SignalResults({ projectId }: { projectId: number }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<SignalSummaryData | null>(null);
  const [signals, setSignals] = useState<SignalSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [severityFilter, setSeverityFilter] = useState("");
  const [sortBy, setSortBy] = useState<"rank" | "prr" | "total_cases">("rank");
  const [resultsTab, setResultsTab] = useState<ResultsTab>("Signals");
  const [clusters, setClusters] = useState<ClustersData | null>(null);
  const [clustersLoading, setClustersLoading] = useState(false);
  const [clustersError, setClustersError] = useState<string | null>(null);

  // Signal detail — fetched on row click
  const [selectedSignalSummary, setSelectedSignalSummary] = useState<SignalSummary | null>(null);
  const [detailSignal, setDetailSignal] = useState<SignalRead | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const [exportError, setExportError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sumRes, sigRes] = await Promise.all([
        api.getSignalSummary(projectId),
        api.listSignals(projectId, { severity: severityFilter || undefined, limit: 200 }),
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

  async function loadClusters() {
    if (clusters) return; // already loaded
    setClustersLoading(true);
    setClustersError(null);
    try {
      const res = await api.getClusters(projectId);
      setClusters(res.data);
    } catch (e) {
      setClustersError(e instanceof ApiError ? e.message : "Failed to load clusters");
    } finally {
      setClustersLoading(false);
    }
  }

  useEffect(() => {
    if (resultsTab === "Clusters") loadClusters();
  }, [resultsTab]); // eslint-disable-line react-hooks/exhaustive-deps

  async function openSignalDrawer(sig: SignalSummary) {
    setSelectedSignalSummary(sig);
    setDetailSignal(null);
    setDetailError(null);
    if (sig.id !== undefined) {
      setDetailLoading(true);
      try {
        const res = await api.getSignal(projectId, sig.id);
        setDetailSignal(res.data);
      } catch {
        setDetailError("Could not load full signal detail — showing summary.");
      }
      setDetailLoading(false);
    }
  }

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

  // Sort signals
  const sorted = [...signals].sort((a, b) => {
    if (sortBy === "rank") return a.rank - b.rank;
    if (sortBy === "prr") return b.prr - a.prr;
    return b.total_cases - a.total_cases;
  });

  return (
    <div>
      {/* Dataset processing metrics */}
      <div className="sr-section-heading">Dataset Processing</div>
      <div className="sr-metric-grid sr-mb-md">
        <MetricCard
          label="Total reports"
          value={summary.total_raw_rows ?? "—"}
          sub="raw input rows"
        />
        <MetricCard
          label="Usable reports"
          value={summary.rows_used ?? "—"}
          sub="after dedup + validation"
        />
        <MetricCard
          label="Duplicates removed"
          value={summary.duplicate_rows ?? "—"}
          sub="exact duplicate rows"
        />
        <MetricCard
          label="Excluded rows"
          value={summary.excluded_rows ?? "—"}
          sub="missing required fields"
        />
        <MetricCard
          label="Drugs"
          value={summary.distinct_drugs ?? "—"}
          sub="distinct canonical"
        />
        <MetricCard
          label="Events"
          value={summary.distinct_events ?? "—"}
          sub="distinct canonical"
        />
      </div>

      {/* Signal detection summary */}
      <div className="sr-section-heading">Detection Results</div>
      <div className="sr-metric-grid sr-mb-md">
        <MetricCard label="Total signals" value={summary.total_signals} />
        <MetricCard
          label="Above threshold"
          value={summary.signals_above_threshold}
          sub={`PRR ≥ 2.0, cases ≥ 3`}
        />
        <MetricCard
          label="Algorithm"
          value={<span className="sr-mono">{summary.algorithm_version}</span>}
        />
        <MetricCard
          label="Completed"
          value={new Date(summary.completed_at).toLocaleTimeString()}
          sub={new Date(summary.completed_at).toLocaleDateString()}
        />
      </div>

      {/* Sub-tabs: Signals / Clusters */}
      <div className="sr-sub-tabs">
        {(["Signals", "Clusters"] as ResultsTab[]).map((t) => (
          <button
            key={t}
            className={`sr-sub-tab ${resultsTab === t ? "active" : ""}`}
            onClick={() => setResultsTab(t)}
          >
            {t}
            {t === "Signals" && <span className="sr-sub-tab-count">{total}</span>}
            {t === "Clusters" && clusters && <span className="sr-sub-tab-count">{clusters.total}</span>}
          </button>
        ))}
      </div>

      {resultsTab === "Signals" && (
        <SignalTable
          signals={sorted}
          total={total}
          severityFilter={severityFilter}
          sortBy={sortBy}
          selectedSignal={selectedSignalSummary}
          onSeverityChange={setSeverityFilter}
          onSortChange={setSortBy}
          onSelect={openSignalDrawer}
          onExport={exportFile}
          exportError={exportError}
        />
      )}

      {resultsTab === "Clusters" && (
        <ClustersTab
          clusters={clusters}
          loading={clustersLoading}
          error={clustersError}
          onRetry={loadClusters}
        />
      )}

      {/* Signal detail drawer */}
      {selectedSignalSummary && (
        <Drawer
          title={`${selectedSignalSummary.drug} — ${selectedSignalSummary.event}`}
          onClose={() => { setSelectedSignalSummary(null); setDetailSignal(null); }}
        >
          <SignalDetailContent
            summary={selectedSignalSummary}
            detail={detailSignal?.result ?? null}
            loading={detailLoading}
            error={detailError}
            algorithmVersion={summary.algorithm_version}
          />
        </Drawer>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Signal table sub-component
// ---------------------------------------------------------------------------

interface SignalTableProps {
  signals: SignalSummary[];
  total: number;
  severityFilter: string;
  sortBy: "rank" | "prr" | "total_cases";
  selectedSignal: SignalSummary | null;
  onSeverityChange: (v: string) => void;
  onSortChange: (v: "rank" | "prr" | "total_cases") => void;
  onSelect: (s: SignalSummary) => void;
  onExport: (fmt: "json" | "csv") => Promise<void>;
  exportError: string | null;
}

function SignalTable({
  signals, total, severityFilter, sortBy, selectedSignal,
  onSeverityChange, onSortChange, onSelect, onExport, exportError,
}: SignalTableProps) {
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem", marginBottom: "0.75rem" }}>
        <div className="sr-filter-bar" style={{ margin: 0 }}>
          <span style={{ fontSize: "0.85rem", color: "var(--text)" }}>Severity:</span>
          <select
            value={severityFilter}
            onChange={(e) => onSeverityChange(e.target.value)}
            aria-label="Filter by severity"
          >
            <option value="">All</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <span style={{ fontSize: "0.85rem", color: "var(--text)" }}>Sort:</span>
          <select
            value={sortBy}
            onChange={(e) => onSortChange(e.target.value as "rank" | "prr" | "total_cases")}
            aria-label="Sort by"
          >
            <option value="rank">Rank</option>
            <option value="prr">PRR ↓</option>
            <option value="total_cases">Cases ↓</option>
          </select>
          <span style={{ fontSize: "0.8rem", color: "var(--text)", marginLeft: "auto" }}>
            {total} signal{total !== 1 ? "s" : ""}
          </span>
        </div>
        <div className="sr-export-group">
          <ExportButton label="Export JSON" onExport={() => onExport("json")} />
          <ExportButton label="Export CSV" onExport={() => onExport("csv")} />
        </div>
      </div>
      {exportError && <ErrorPanel message={exportError} />}

      {signals.length === 0 ? (
        <Empty icon="🔍" message="No signals match the current filter." />
      ) : (
        <div className="sr-table-wrap">
          <table className="sr-table" aria-label="Signal results">
            <thead>
              <tr>
                <th>#</th>
                <th>Drug</th>
                <th>Event / Cluster</th>
                <th title="Drug+Event cases">a</th>
                <th title="Drug+Other cases">b</th>
                <th title="Other+Event cases">c</th>
                <th title="Other+Other cases">d</th>
                <th>PRR</th>
                <th>Pairs</th>
                <th>Severity</th>
                <th>Threshold</th>
              </tr>
            </thead>
            <tbody>
              {signals.map((s, i) => (
                <tr
                  key={i}
                  onClick={() => onSelect(s)}
                  className={selectedSignal === s ? "selected" : ""}
                  aria-label={`Signal ${s.drug} ${s.event}`}
                >
                  <td className="sr-mono" style={{ color: "var(--text)" }}>{s.rank}</td>
                  <td><strong>{s.drug}</strong></td>
                  <td>{s.event}</td>
                  {/* a/b/c/d are only in SignalResult (full detail); show — in list view */}
                  <td className="sr-mono sr-cell-num">{s.total_cases}</td>
                  <td className="sr-mono sr-cell-num sr-text-muted">—</td>
                  <td className="sr-mono sr-cell-num sr-text-muted">—</td>
                  <td className="sr-mono sr-cell-num sr-text-muted">—</td>
                  <td className="sr-mono sr-cell-num">{s.prr.toFixed(2)}</td>
                  <td className="sr-mono sr-cell-num">{s.total_cases}</td>
                  <td><Badge value={s.severity} /></td>
                  <td><Badge value={s.threshold_status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Signal detail drawer content
// ---------------------------------------------------------------------------

interface SignalDetailContentProps {
  summary: SignalSummary;
  detail: SignalResult | null;
  loading: boolean;
  error: string | null;
  algorithmVersion: string;
}

function SignalDetailContent({ summary, detail, loading, error, algorithmVersion }: SignalDetailContentProps) {
  const a = detail?.a ?? summary.total_cases;
  const b = detail?.b;
  const c = detail?.c;
  const d = detail?.d;
  const prr = detail?.prr ?? summary.prr;
  const lci = detail?.prr_lower_ci;
  const uci = detail?.prr_upper_ci;
  const algVer = detail?.algorithm_version ?? algorithmVersion;
  const disclaimer = detail?.disclaimer;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      {loading && <Loading text="Loading detail…" />}
      {error && <ErrorPanel message={error} />}

      {/* Severity + threshold */}
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
        <Badge value={summary.severity} />
        <Badge value={summary.threshold_status} />
        <span style={{ fontSize: "0.8rem", color: "var(--text)", alignSelf: "center" }}>
          Rank #{summary.rank}
        </span>
      </div>

      <hr className="sr-drawer-sep" />

      {/* Exact PRR formula */}
      <div>
        <p className="sr-drawer-section-label">PRR Formula</p>
        <div className="sr-formula-box">
          <div className="sr-formula-row">
            <span className="sr-formula-label">a (drug+event)</span>
            <span className="sr-formula-value sr-mono">{a}</span>
          </div>
          {b !== undefined && (
            <div className="sr-formula-row">
              <span className="sr-formula-label">b (drug+other)</span>
              <span className="sr-formula-value sr-mono">{b}</span>
            </div>
          )}
          {c !== undefined && (
            <div className="sr-formula-row">
              <span className="sr-formula-label">c (other+event)</span>
              <span className="sr-formula-value sr-mono">{c}</span>
            </div>
          )}
          {d !== undefined && (
            <div className="sr-formula-row">
              <span className="sr-formula-label">d (other+other)</span>
              <span className="sr-formula-value sr-mono">{d}</span>
            </div>
          )}
          <div className="sr-formula-row sr-formula-result">
            <span className="sr-formula-label">
              PRR = [a/(a+b)] / [c/(c+d)]
            </span>
            <span className="sr-formula-value sr-mono">{prr.toFixed(4)}</span>
          </div>
          {lci !== undefined && uci !== undefined && (
            <div className="sr-formula-row">
              <span className="sr-formula-label">95% CI</span>
              <span className="sr-formula-value sr-mono">
                [{lci.toFixed(3)}, {uci.toFixed(3)}]
              </span>
            </div>
          )}
        </div>
      </div>

      <hr className="sr-drawer-sep" />

      {/* Event cluster provenance */}
      {detail?.event_cluster && (
        <div>
          <p className="sr-drawer-section-label">Event Cluster</p>
          <p className="sr-drawer-section-value" style={{ marginBottom: "0.35rem" }}>
            <strong>{detail.event_cluster.preferred_term}</strong>
            {detail.event_cluster.meddra_code && (
              <span className="sr-mono" style={{ fontSize: "0.78rem", marginLeft: "0.4rem", color: "var(--text)" }}>
                MedDRA {detail.event_cluster.meddra_code}
              </span>
            )}
          </p>
          {detail.event_cluster.raw_aliases.length > 0 && (
            <div className="sr-alias-list">
              <p className="sr-drawer-section-label" style={{ marginBottom: "0.25rem" }}>Raw aliases</p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.3rem" }}>
                {detail.event_cluster.raw_aliases.map((alias) => (
                  <span key={alias} className="sr-alias-tag">{alias}</span>
                ))}
              </div>
            </div>
          )}
          {detail.event_cluster.provenances.length > 0 && (
            <div style={{ marginTop: "0.5rem" }}>
              <p className="sr-drawer-section-label" style={{ marginBottom: "0.25rem" }}>Normalisation provenance</p>
              <div className="sr-table-wrap">
                <table className="sr-table sr-compact-table" aria-label="Normalisation provenance">
                  <thead>
                    <tr>
                      <th>Raw term</th>
                      <th>Canonical</th>
                      <th>Method</th>
                      <th>Confidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.event_cluster.provenances.map((p, i) => (
                      <tr key={i}>
                        <td className="sr-mono">{p.raw_term}</td>
                        <td className="sr-mono">{p.preferred_term}</td>
                        <td><Badge value={p.method} /></td>
                        <td className="sr-mono">{(p.confidence * 100).toFixed(0)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          <hr className="sr-drawer-sep" />
        </div>
      )}

      {/* Algorithm + source */}
      <div>
        <p className="sr-drawer-section-label">Algorithm version</p>
        <p className="sr-drawer-section-value sr-mono">{algVer}</p>
      </div>

      {/* Disclaimer */}
      {disclaimer && (
        <div className="sr-drawer-disclaimer">
          <p className="sr-drawer-section-label">Disclaimer</p>
          <p style={{ fontSize: "0.8rem", color: "var(--text)", lineHeight: 1.5 }}>{disclaimer}</p>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Clusters tab
// ---------------------------------------------------------------------------

interface ClustersTabProps {
  clusters: ClustersData | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

function ClustersTab({ clusters, loading, error, onRetry }: ClustersTabProps) {
  const [expandedCluster, setExpandedCluster] = useState<string | null>(null);

  if (loading) return <Loading text="Loading clusters…" />;
  if (error) return <ErrorPanel message={error} onRetry={onRetry} />;
  if (!clusters) return <Empty icon="🔍" message="Clusters will appear after analysis completes." />;
  if (clusters.clusters.length === 0) return <Empty icon="🔍" message="No clusters found." />;

  return (
    <div>
      <p style={{ fontSize: "0.85rem", color: "var(--text)", marginBottom: "0.75rem" }}>
        {clusters.total} event cluster{clusters.total !== 1 ? "s" : ""} — groups of raw adverse-event
        strings that resolved to the same preferred term.
      </p>
      <div className="sr-cluster-list">
        {clusters.clusters.map((c) => {
          const isExpanded = expandedCluster === c.preferred_term;
          return (
            <div key={c.preferred_term} className="sr-cluster-card">
              <button
                className="sr-cluster-header"
                onClick={() => setExpandedCluster(isExpanded ? null : c.preferred_term)}
                aria-expanded={isExpanded}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap" }}>
                  <strong style={{ fontSize: "0.9rem" }}>{c.preferred_term}</strong>
                  {c.meddra_code && (
                    <span className="sr-mono" style={{ fontSize: "0.75rem", color: "var(--text)" }}>
                      MedDRA {c.meddra_code}
                    </span>
                  )}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                  <span style={{ fontSize: "0.8rem", color: "var(--text)" }}>
                    {c.case_count} case{c.case_count !== 1 ? "s" : ""} · {c.raw_aliases.length} alias{c.raw_aliases.length !== 1 ? "es" : ""}
                  </span>
                  <span style={{ color: "var(--text)", fontSize: "0.8rem" }}>{isExpanded ? "▲" : "▼"}</span>
                </div>
              </button>

              {isExpanded && (
                <div className="sr-cluster-body">
                  <p className="sr-drawer-section-label">Member terms</p>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "0.3rem", marginBottom: "0.75rem" }}>
                    {c.raw_aliases.map((alias) => (
                      <span key={alias} className="sr-alias-tag">{alias}</span>
                    ))}
                  </div>
                  {c.provenances.length > 0 && (
                    <>
                      <p className="sr-drawer-section-label">Normalisation details</p>
                      <div className="sr-table-wrap">
                        <table className="sr-table sr-compact-table" aria-label={`Provenance for ${c.preferred_term}`}>
                          <thead>
                            <tr>
                              <th>Raw term</th>
                              <th>Method</th>
                              <th>Confidence</th>
                            </tr>
                          </thead>
                          <tbody>
                            {c.provenances.map((p, i) => (
                              <tr key={i}>
                                <td className="sr-mono">{p.raw_term}</td>
                                <td><Badge value={p.method} /></td>
                                <td className="sr-mono">{(p.confidence * 100).toFixed(0)}%</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
