/**
 * Project overview — command center for a single project.
 * Shows project metadata, job/result counts, and workflow launch cards.
 */
import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/apiClient";
import type { ProjectRead } from "../types/api";
import { Badge, Loading, ErrorPanel, MetricCard } from "../components/shared";

interface ProjectDetailPageProps {
  projectId: number;
  onNavigate: (route: "signal" | "readiness") => void;
  onBack: () => void;
}

// ---------------------------------------------------------------------------
// Inline SVG icons
// ---------------------------------------------------------------------------

function SignalWaveIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <polyline
        points="2,12 5,8 8,16 11,6 14,14 17,10 20,12 22,12"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function DocumentCheckIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <polyline
        points="14,2 14,8 20,8"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <polyline
        points="9,15 11,17 15,13"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ChevronLeftIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <polyline points="15,18 9,12 15,6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ProjectDetailPage({ projectId, onNavigate, onBack }: ProjectDetailPageProps) {
  const [project, setProject] = useState<ProjectRead | null>(null);
  const [jobCount, setJobCount] = useState(0);
  const [resultCount, setResultCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [projRes, jobsRes, resultsRes] = await Promise.all([
          api.getProject(projectId),
          api.listProjectJobs(projectId),
          api.listProjectResults(projectId),
        ]);
        setProject(projRes.data);
        setJobCount(jobsRes.data.total);
        setResultCount(resultsRes.data.total);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Failed to load project");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [projectId]);

  if (loading) return <Loading />;
  if (error) return <ErrorPanel message={error} />;
  if (!project) return null;

  return (
    <div className="sr-content">
      {/* Breadcrumb */}
      <nav className="sr-breadcrumb" aria-label="Breadcrumb">
        <button className="sr-breadcrumb-item" onClick={onBack}>Projects</button>
        <span className="sr-breadcrumb-sep" aria-hidden="true">/</span>
        <span className="sr-breadcrumb-current">{project.name}</span>
      </nav>

      {/* Page header */}
      <div className="sr-page-header">
        <button
          className="sr-btn sr-btn-ghost"
          onClick={onBack}
          style={{ padding: "0.3rem 0.5rem", marginBottom: "0.6rem", fontSize: "0.85rem" }}
        >
          <ChevronLeftIcon /> All Projects
        </button>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
          <div>
            <p className="sr-page-eyebrow">PROJECT WORKSPACE</p>
            <h1 className="sr-page-title">{project.name}</h1>
            {project.description && (
              <p className="sr-page-subtitle">{project.description}</p>
            )}
          </div>
          <Badge value={project.status} />
        </div>
      </div>

      {/* Metrics */}
      <div className="sr-metric-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", maxWidth: 560 }}>
        <MetricCard label="Jobs run" value={jobCount} sub="analysis jobs" />
        <MetricCard label="Completed results" value={resultCount} sub="stored outputs" />
        <MetricCard
          label="Created"
          value={new Date(project.created_at).toLocaleDateString()}
          sub={new Date(project.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        />
      </div>

      {/* Workflow cards */}
      <h2 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-h)", margin: "1.5rem 0 1rem", letterSpacing: "-0.01em" }}>
        Analysis Workflows
      </h2>
      <div className="sr-mode-grid">
        <WorkflowCard
          variant="signal"
          icon={<SignalWaveIcon />}
          title="Signal Detection"
          description="Run PRR-based disproportionality analysis on FAERS-compatible CSV or JSON data. Review ranked signals, event clusters, and evidence tables."
          buttonLabel="Open Signal Detection"
          onClick={() => onNavigate("signal")}
        />
        <WorkflowCard
          variant="readiness"
          icon={<DocumentCheckIcon />}
          title="Submission Readiness"
          description="Assess CTD dossier readiness against the prototype ICH M4 catalog. Review gaps by module, severity, and review status."
          buttonLabel="Open Submission Readiness"
          onClick={() => onNavigate("readiness")}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Workflow card
// ---------------------------------------------------------------------------

interface WorkflowCardProps {
  variant: "signal" | "readiness";
  icon: React.ReactNode;
  title: string;
  description: string;
  buttonLabel: string;
  onClick: () => void;
}

function WorkflowCard({ variant, icon, title, description, buttonLabel, onClick }: WorkflowCardProps) {
  const isSignal = variant === "signal";
  return (
    <div
      className={`sr-mode-card sr-mode-card-${variant}`}
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => e.key === "Enter" && onClick()}
      aria-label={title}
    >
      <div className={`sr-mode-icon sr-mode-icon-${variant}`}>
        {icon}
      </div>
      <h3 className="sr-mode-card-title">{title}</h3>
      <p className="sr-mode-card-desc">{description}</p>
      <div className="sr-mode-steps">
        <span className="sr-mode-step">Upload</span>
        <span className="sr-mode-step-arrow">→</span>
        <span className="sr-mode-step">{isSignal ? "Analyze" : "Assess"}</span>
        <span className="sr-mode-step-arrow">→</span>
        <span className="sr-mode-step">Review</span>
      </div>
      <button
        className={`sr-btn ${isSignal ? "sr-btn-primary" : "sr-btn-teal"}`}
        onClick={(e) => { e.stopPropagation(); onClick(); }}
        style={{ marginTop: "auto" }}
      >
        {buttonLabel}
      </button>
    </div>
  );
}
