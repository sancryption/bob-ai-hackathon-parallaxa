/**
 * Projects page — list all projects + create new project modal.
 */
import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/apiClient";
import type { ProjectRead } from "../types/api";
import { Badge, Empty, ErrorPanel, Loading, MetricCard } from "../components/shared";

interface ProjectsPageProps {
  onOpenProject: (id: number) => void;
}

export function ProjectsPage({ onOpenProject }: ProjectsPageProps) {
  const [projects, setProjects] = useState<ProjectRead[] | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listProjects();
      setProjects(res.data.items);
      setTotal(res.data.total);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load projects");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <div>
      <div className="sr-page-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h1 className="sr-page-title">Projects</h1>
            <p className="sr-page-subtitle">Create a project to run signal detection or readiness assessment.</p>
          </div>
          <button className="sr-btn sr-btn-primary" onClick={() => setShowCreate(true)}>
            + New Project
          </button>
        </div>
      </div>

      <div className="sr-metric-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", maxWidth: 360 }}>
        <MetricCard label="Total projects" value={total} />
      </div>

      {error && <ErrorPanel message={error} onRetry={load} />}
      {loading && <Loading />}
      {!loading && !error && projects?.length === 0 && (
        <Empty
          icon="🗂️"
          message="No projects yet."
          action={
            <button className="sr-btn sr-btn-primary" onClick={() => setShowCreate(true)}>
              Create your first project
            </button>
          }
        />
      )}

      {!loading && projects && projects.length > 0 && (
        <div className="sr-project-grid">
          {projects.map((p) => (
            <div
              key={p.id}
              className="sr-project-card"
              onClick={() => onOpenProject(p.id)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === "Enter" && onOpenProject(p.id)}
              aria-label={`Open project ${p.name}`}
            >
              <p className="sr-project-card-name">{p.name}</p>
              {p.description && (
                <p className="sr-project-card-desc">{p.description}</p>
              )}
              <div className="sr-project-card-meta">
                <Badge value={p.status} />
                <span style={{ fontSize: "0.78rem", color: "var(--text)" }}>
                  {new Date(p.created_at).toLocaleDateString()}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreate && (
        <CreateProjectModal
          onClose={() => setShowCreate(false)}
          onCreated={(id) => { setShowCreate(false); onOpenProject(id); }}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Create project modal
// ---------------------------------------------------------------------------

interface CreateProjectModalProps {
  onClose: () => void;
  onCreated: (id: number) => void;
}

function CreateProjectModal({ onClose, onCreated }: CreateProjectModalProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const res = await api.createProject({ name: name.trim(), description: description.trim() || undefined });
      onCreated(res.data.id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to create project");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="sr-modal-overlay" onClick={onClose}>
      <div className="sr-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Create project">
        <h2 className="sr-modal-title">New Project</h2>
        {error && <ErrorPanel message={error} />}
        <form onSubmit={handleSubmit}>
          <div className="sr-form-group">
            <label className="sr-label" htmlFor="proj-name">Name *</label>
            <input
              id="proj-name"
              className="sr-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Phase III NDA Review"
              required
              maxLength={255}
            />
          </div>
          <div className="sr-form-group">
            <label className="sr-label" htmlFor="proj-desc">Description</label>
            <textarea
              id="proj-desc"
              className="sr-input sr-textarea"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
              maxLength={2000}
            />
          </div>
          <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
            <button type="button" className="sr-btn sr-btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="sr-btn sr-btn-primary" disabled={saving || !name.trim()}>
              {saving ? "Creating…" : "Create"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
