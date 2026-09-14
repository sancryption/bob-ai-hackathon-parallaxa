/**
 * Projects page — workspace index.
 * Lists all projects, search/filter from loaded data, polished empty state,
 * and redesigned create-project modal.
 */
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../lib/apiClient";
import type { ProjectRead } from "../types/api";
import { Badge, ErrorPanel, Loading } from "../components/shared";

interface ProjectsPageProps {
  onOpenProject: (id: number) => void;
}

// ---------------------------------------------------------------------------
// Inline SVG icons
// ---------------------------------------------------------------------------

function PlusIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <line x1="12" y1="5" x2="12" y2="19" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <line x1="5" y1="12" x2="19" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function FolderPlusIllustration() {
  return (
    <svg
      width="130"
      height="110"
      viewBox="0 0 130 110"
      fill="none"
      className="sr-empty-svg"
      aria-hidden="true"
    >
      {/* Folder shape */}
      <path
        d="M10 30 Q10 25 15 25 L50 25 L58 18 L115 18 Q120 18 120 23 L120 90 Q120 95 115 95 L15 95 Q10 95 10 90 Z"
        fill="var(--code-bg)"
        stroke="var(--border)"
        strokeWidth="1.5"
      />
      {/* Plus badge */}
      <circle cx="100" cy="50" r="18" fill="var(--accent-bg)" stroke="var(--accent-border)" strokeWidth="1.5" />
      <line x1="100" y1="42" x2="100" y2="58" stroke="var(--accent)" strokeWidth="2.5" strokeLinecap="round" />
      <line x1="92" y1="50" x2="108" y2="50" stroke="var(--accent)" strokeWidth="2.5" strokeLinecap="round" />
      {/* Document lines */}
      <rect x="28" y="55" width="44" height="5" rx="2.5" fill="var(--border)" />
      <rect x="28" y="66" width="34" height="4" rx="2" fill="var(--border)" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Projects page
// ---------------------------------------------------------------------------

export function ProjectsPage({ onOpenProject }: ProjectsPageProps) {
  const [projects, setProjects] = useState<ProjectRead[] | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [search, setSearch] = useState("");

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

  const filtered = search.trim()
    ? (projects ?? []).filter(
        (p) =>
          p.name.toLowerCase().includes(search.toLowerCase()) ||
          (p.description ?? "").toLowerCase().includes(search.toLowerCase()),
      )
    : (projects ?? []);

  return (
    <div className="sr-content">
      {/* Page header */}
      <div className="sr-page-header">
        <p className="sr-page-eyebrow">WORKSPACE</p>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "1rem", flexWrap: "wrap" }}>
          <div>
            <h1 className="sr-page-title">Projects</h1>
            <p className="sr-page-subtitle">
              Organize safety-signal analyses and CTD readiness assessments in one workspace.
            </p>
          </div>
          <button className="sr-btn sr-btn-primary" onClick={() => setShowCreate(true)}>
            <PlusIcon /> New Project
          </button>
        </div>
      </div>

      {/* Summary row */}
      {!loading && !error && (
        <div style={{ display: "flex", alignItems: "center", gap: "1.25rem", marginBottom: "1.25rem", flexWrap: "wrap" }}>
          <span style={{ fontSize: "0.88rem", color: "var(--text-muted)" }}>
            <strong style={{ color: "var(--text-h)" }}>{total}</strong> project{total !== 1 ? "s" : ""}
          </span>
          {total > 0 && (
            <input
              className="sr-input"
              style={{ maxWidth: 260, padding: "0.38rem 0.7rem", fontSize: "0.85rem" }}
              placeholder="Search projects…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search projects"
            />
          )}
        </div>
      )}

      {error && <ErrorPanel message={error} onRetry={load} />}
      {loading && <Loading />}

      {/* Empty state */}
      {!loading && !error && projects?.length === 0 && (
        <div className="sr-empty">
          <FolderPlusIllustration />
          <p className="sr-empty-title">Start your first SafetyReady workspace</p>
          <p className="sr-empty-desc">
            A project holds your uploads, analysis jobs, and results for both
            Signal Detection and Submission Readiness workflows.
          </p>
          <button className="sr-btn sr-btn-primary" onClick={() => setShowCreate(true)}>
            + Create your first project
          </button>
          <p style={{ marginTop: "0.75rem", fontSize: "0.8rem", color: "var(--text-muted)" }}>
            You can run Signal Detection or Submission Readiness after the workspace is created.
          </p>
        </div>
      )}

      {/* Search empty */}
      {!loading && !error && projects && projects.length > 0 && filtered.length === 0 && (
        <div className="sr-empty" style={{ padding: "2rem 1rem" }}>
          <p style={{ color: "var(--text-muted)" }}>No projects match &ldquo;{search}&rdquo;</p>
        </div>
      )}

      {/* Projects grid */}
      {!loading && filtered.length > 0 && (
        <div className="sr-project-grid">
          {filtered.map((p) => (
            <ProjectCard
              key={p.id}
              project={p}
              onOpen={() => onOpenProject(p.id)}
            />
          ))}
        </div>
      )}

      {/* Create modal */}
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
// Project card
// ---------------------------------------------------------------------------

interface ProjectCardProps {
  project: ProjectRead;
  onOpen: () => void;
}

function ProjectCard({ project: p, onOpen }: ProjectCardProps) {
  return (
    <div
      className="sr-project-card"
      onClick={onOpen}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && onOpen()}
      aria-label={`Open project ${p.name}`}
    >
      <p className="sr-project-card-name">{p.name}</p>
      <p className="sr-project-card-desc">
        {p.description || <span style={{ fontStyle: "italic" }}>No description provided</span>}
      </p>
      <div className="sr-project-card-meta">
        <Badge value={p.status} />
        <span className="sr-project-card-date">
          {new Date(p.created_at).toLocaleDateString()}
        </span>
      </div>
      <div className="sr-project-card-footer">
        <div className="sr-project-workflow-icons">
          <span className="sr-workflow-chip">Signal</span>
          <span className="sr-workflow-chip">Readiness</span>
        </div>
        <button
          className="sr-btn sr-btn-primary"
          style={{ fontSize: "0.8rem", padding: "0.35rem 0.8rem" }}
          onClick={(e) => { e.stopPropagation(); onOpen(); }}
          aria-label={`Open workspace for ${p.name}`}
        >
          Open workspace
        </button>
      </div>
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
  const nameRef = useRef<HTMLInputElement>(null);

  // Focus first field on mount
  useEffect(() => {
    nameRef.current?.focus();
  }, []);

  // Escape to close
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const res = await api.createProject({ name: name.trim(), description: description.trim() || undefined });
      onCreated(res.data.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create project");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="sr-modal-overlay"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-project-title"
    >
      <div
        className="sr-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sr-modal-header">
          <h2 className="sr-modal-title" id="create-project-title">New Project</h2>
          <p className="sr-modal-subtitle">
            Create a workspace to run Signal Detection or Submission Readiness analysis.
          </p>
        </div>

        {error && (
          <div style={{ marginBottom: "1rem" }}>
            <ErrorPanel message={error} />
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="sr-form-group">
            <label className="sr-label sr-label-required" htmlFor="proj-name">
              Project name
            </label>
            <input
              id="proj-name"
              ref={nameRef}
              className="sr-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Phase III NDA — Drug X Safety Review"
              required
              maxLength={255}
              autoComplete="off"
            />
          </div>
          <div className="sr-form-group">
            <label className="sr-label" htmlFor="proj-desc">Description</label>
            <textarea
              id="proj-desc"
              className="sr-input sr-textarea"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional — describe the drug, indication, or regulatory submission context"
              maxLength={2000}
            />
          </div>
          <div className="sr-modal-footer">
            <button
              type="button"
              className="sr-btn sr-btn-secondary"
              onClick={onClose}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="sr-btn sr-btn-primary"
              disabled={saving || !name.trim()}
            >
              {saving ? "Creating…" : "Create project"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
