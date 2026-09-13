/**
 * Project overview — summary of all jobs/results for one project,
 * with navigation to Signal Detection and Readiness Assessment.
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
    <div>
      <div className="sr-page-header">
        <button className="sr-btn sr-btn-ghost" onClick={onBack} style={{ padding: 0, marginBottom: "0.5rem" }}>
          ← All Projects
        </button>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "1rem" }}>
          <div>
            <h1 className="sr-page-title">{project.name}</h1>
            {project.description && (
              <p className="sr-page-subtitle">{project.description}</p>
            )}
          </div>
          <Badge value={project.status} />
        </div>
      </div>

      <div className="sr-metric-grid">
        <MetricCard label="Jobs run" value={jobCount} />
        <MetricCard label="Completed results" value={resultCount} />
        <MetricCard
          label="Created"
          value={new Date(project.created_at).toLocaleDateString()}
        />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "1rem", marginTop: "1rem" }}>
        <ActionCard
          icon="🔍"
          title="Signal Detection"
          description="Run disproportionality analysis (PRR) on FAERS-compatible CSV or JSON data."
          onClick={() => onNavigate("signal")}
        />
        <ActionCard
          icon="📋"
          title="Submission Readiness"
          description="Assess CTD dossier readiness against the prototype ICH catalog."
          onClick={() => onNavigate("readiness")}
        />
      </div>
    </div>
  );
}

interface ActionCardProps {
  icon: string;
  title: string;
  description: string;
  onClick: () => void;
}

function ActionCard({ icon, title, description, onClick }: ActionCardProps) {
  return (
    <div
      className="sr-project-card"
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && onClick()}
      aria-label={title}
    >
      <div style={{ fontSize: "1.75rem", marginBottom: "0.5rem" }}>{icon}</div>
      <p className="sr-project-card-name">{title}</p>
      <p className="sr-project-card-desc">{description}</p>
      <span className="sr-btn sr-btn-primary" style={{ marginTop: "0.5rem", cursor: "default" }}>
        Open →
      </span>
    </div>
  );
}
