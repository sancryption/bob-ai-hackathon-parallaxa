/**
 * Home / Dashboard page.
 *
 * Sections:
 *  A. Hero/welcome
 *  B. Capability cards (Signal Detection + Submission Readiness)
 *  C. Live workspace snapshot (project count from API)
 *  D. Recent projects (last 3 from listProjects)
 *  E. Trust/limitations strip
 */
import { useEffect, useState } from "react";
import { api } from "../lib/apiClient";
import type { ProjectRead } from "../types/api";
import { Badge, Loading } from "../components/shared";

interface HomePageProps {
  onOpenProjects: () => void;
  onCreateProject: () => void;
  onOpenProject: (id: number) => void;
}

// ---------------------------------------------------------------------------
// Inline SVG icons
// ---------------------------------------------------------------------------

function SignalWaveIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <polyline
        points="2,12 5,8 8,16 11,6 14,14 17,10 20,12 22,12"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

function DocumentCheckIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
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

function InfoIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" />
      <line x1="12" y1="8" x2="12" y2="8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <line x1="12" y1="12" x2="12" y2="16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

/** Decorative abstract dashboard SVG — no external dependency */
function HeroVisual() {
  return (
    <svg
      width="300"
      height="240"
      viewBox="0 0 300 240"
      fill="none"
      aria-hidden="true"
      role="presentation"
    >
      {/* Background card shapes */}
      <rect x="10" y="30" width="280" height="190" rx="16" fill="rgba(255,255,255,0.07)" />

      {/* Signal line chart */}
      <polyline
        points="30,160 60,120 90,140 120,80 150,110 180,70 210,90 240,60 270,80"
        stroke="rgba(13,202,240,0.8)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      {/* Area under signal */}
      <polygon
        points="30,160 60,120 90,140 120,80 150,110 180,70 210,90 240,60 270,80 270,180 30,180"
        fill="rgba(13,202,240,0.08)"
      />

      {/* Mini metric cards */}
      <rect x="30" y="50" width="70" height="40" rx="8" fill="rgba(255,255,255,0.1)" />
      <rect x="115" y="50" width="70" height="40" rx="8" fill="rgba(255,255,255,0.1)" />
      <rect x="200" y="50" width="70" height="40" rx="8" fill="rgba(255,255,255,0.1)" />

      {/* Metric values (placeholder lines) */}
      <rect x="42" y="60" width="20" height="8" rx="4" fill="rgba(255,255,255,0.6)" />
      <rect x="42" y="72" width="40" height="5" rx="3" fill="rgba(255,255,255,0.25)" />
      <rect x="127" y="60" width="20" height="8" rx="4" fill="rgba(13,202,240,0.7)" />
      <rect x="127" y="72" width="40" height="5" rx="3" fill="rgba(255,255,255,0.25)" />
      <rect x="212" y="60" width="20" height="8" rx="4" fill="rgba(255,255,255,0.6)" />
      <rect x="212" y="72" width="40" height="5" rx="3" fill="rgba(255,255,255,0.25)" />

      {/* Alert/signal badge */}
      <circle cx="240" cy="80" r="8" fill="rgba(220,53,69,0.85)" />
      <text x="240" y="84" textAnchor="middle" fill="white" fontSize="9" fontWeight="700">!</text>

      {/* Document icon bottom left */}
      <rect x="30" y="190" width="36" height="30" rx="4" fill="rgba(255,255,255,0.12)" />
      <line x1="36" y1="198" x2="58" y2="198" stroke="rgba(255,255,255,0.4)" strokeWidth="2" />
      <line x1="36" y1="203" x2="58" y2="203" stroke="rgba(255,255,255,0.4)" strokeWidth="2" />
      <line x1="36" y1="208" x2="50" y2="208" stroke="rgba(255,255,255,0.4)" strokeWidth="2" />

      {/* Check indicator */}
      <circle cx="240" cy="205" r="14" fill="rgba(25,135,84,0.7)" />
      <polyline
        points="232,205 238,211 248,199"
        stroke="white"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Empty-state SVG for no projects */
function NoProjectsIllustration() {
  return (
    <svg
      width="120"
      height="100"
      viewBox="0 0 120 100"
      fill="none"
      className="sr-empty-svg"
      aria-hidden="true"
    >
      <rect x="15" y="20" width="90" height="65" rx="8" fill="var(--code-bg)" stroke="var(--border)" strokeWidth="1.5" />
      <rect x="30" y="35" width="60" height="6" rx="3" fill="var(--border)" />
      <rect x="30" y="47" width="45" height="5" rx="3" fill="var(--border)" />
      <rect x="30" y="59" width="52" height="5" rx="3" fill="var(--border)" />
      <circle cx="85" cy="28" r="14" fill="var(--accent-bg)" stroke="var(--accent-border)" strokeWidth="1.5" />
      <line x1="85" y1="22" x2="85" y2="28" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" />
      <line x1="82" y1="31" x2="88" y2="31" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// HomePage component
// ---------------------------------------------------------------------------

export function HomePage({ onOpenProjects, onCreateProject, onOpenProject }: HomePageProps) {
  const [projects, setProjects] = useState<ProjectRead[] | null>(null);
  const [total, setTotal] = useState<number | null>(null);
  const [loadingProjects, setLoadingProjects] = useState(true);

  useEffect(() => {
    api.listProjects(0, 50)
      .then((res) => {
        setProjects(res.data.items);
        setTotal(res.data.total);
      })
      .catch(() => {
        setProjects([]);
        setTotal(0);
      })
      .finally(() => setLoadingProjects(false));
  }, []);

  const recentProjects = (projects ?? []).slice(0, 3);

  return (
    <div style={{ margin: "-2rem -1.5rem" }}>
      {/* ================================================================= */}
      {/* A. Hero section                                                     */}
      {/* ================================================================= */}
      <section className="sr-hero">
        <div className="sr-hero-inner">
          <div className="sr-hero-content">
            <p className="sr-hero-eyebrow">SAFETY INTELLIGENCE WORKSPACE</p>
            <h1 className="sr-hero-title">
              Turn complex pharmaceutical data<br />into confident review decisions.
            </h1>
            <p className="sr-hero-sub">
              SafetyReady provides two deterministic workflows: PRR-based
              safety-signal detection from spontaneous reports, and ICH M4
              submission-readiness analysis for regulatory CTD dossiers.
            </p>
            <div className="sr-hero-ctas">
              <button
                className="sr-btn sr-btn-hero-primary"
                onClick={onOpenProjects}
              >
                Open Projects
              </button>
              <button
                className="sr-btn sr-btn-hero-secondary"
                onClick={onCreateProject}
              >
                + Create New Project
              </button>
            </div>
          </div>
          <div className="sr-hero-visual" aria-hidden="true">
            <HeroVisual />
          </div>
        </div>
      </section>

      {/* ================================================================= */}
      {/* B. Capability cards                                                 */}
      {/* ================================================================= */}
      <section className="sr-home-section" style={{ borderBottom: "1px solid var(--border)" }}>
        <h2 className="sr-home-section-title">Analysis Workflows</h2>
        <div className="sr-capability-grid">
          {/* Signal Detection */}
          <div className="sr-capability-card sr-capability-card-signal">
            <div className="sr-mode-icon sr-mode-icon-signal">
              <SignalWaveIcon />
            </div>
            <div>
              <h3 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-h)", margin: "0 0 0.4rem" }}>
                Signal Detection
              </h3>
              <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", lineHeight: 1.55, margin: 0 }}>
                Upload FAERS-compatible CSV or JSON adverse-event data and run
                Proportional Reporting Ratio (PRR) disproportionality analysis.
                Review ranked signals, event clusters, and evidence grids.
              </p>
            </div>
            <div className="sr-mode-steps">
              <span className="sr-mode-step">Upload</span>
              <span className="sr-mode-step-arrow">→</span>
              <span className="sr-mode-step">Analyze</span>
              <span className="sr-mode-step-arrow">→</span>
              <span className="sr-mode-step">Review</span>
            </div>
            <button className="sr-btn sr-btn-primary" onClick={onOpenProjects}>
              Explore workflow
            </button>
          </div>

          {/* Submission Readiness */}
          <div className="sr-capability-card sr-capability-card-readiness">
            <div className="sr-mode-icon sr-mode-icon-readiness">
              <DocumentCheckIcon />
            </div>
            <div>
              <h3 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-h)", margin: "0 0 0.4rem" }}>
                Submission Readiness
              </h3>
              <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", lineHeight: 1.55, margin: 0 }}>
                Assess CTD dossier completeness against the prototype ICH M4 catalog.
                Surface gaps by module, severity, and review status.
                Export findings as JSON or Markdown.
              </p>
            </div>
            <div className="sr-mode-steps">
              <span className="sr-mode-step">Upload</span>
              <span className="sr-mode-step-arrow">→</span>
              <span className="sr-mode-step">Assess</span>
              <span className="sr-mode-step-arrow">→</span>
              <span className="sr-mode-step">Review</span>
            </div>
            <button className="sr-btn sr-btn-teal" onClick={onOpenProjects}>
              Explore workflow
            </button>
          </div>
        </div>
      </section>

      {/* ================================================================= */}
      {/* C. Workspace snapshot                                               */}
      {/* ================================================================= */}
      <section className="sr-home-section" style={{ borderBottom: "1px solid var(--border)" }}>
        <h2 className="sr-home-section-title">Workspace Snapshot</h2>
        <div className="sr-snapshot-grid">
          <div className="sr-snapshot-card">
            <div className="sr-snapshot-value">
              {total === null ? "—" : total}
            </div>
            <div className="sr-snapshot-label">Projects</div>
          </div>
          <div className="sr-snapshot-card">
            <div className="sr-snapshot-value" style={{ color: "var(--accent)", fontSize: "1.25rem" }}>
              PRR
            </div>
            <div className="sr-snapshot-label">Signal workflow</div>
          </div>
          <div className="sr-snapshot-card">
            <div className="sr-snapshot-value" style={{ color: "var(--sr-teal-dark)", fontSize: "1.25rem" }}>
              CTD
            </div>
            <div className="sr-snapshot-label">Readiness workflow</div>
          </div>
        </div>
      </section>

      {/* ================================================================= */}
      {/* D. Recent projects                                                  */}
      {/* ================================================================= */}
      <section className="sr-home-section" style={{ borderBottom: "1px solid var(--border)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.25rem", gap: "0.75rem", flexWrap: "wrap" }}>
          <h2 className="sr-home-section-title" style={{ margin: 0 }}>Recent Projects</h2>
          <button className="sr-btn sr-btn-secondary" onClick={onOpenProjects} style={{ fontSize: "0.82rem" }}>
            View all projects
          </button>
        </div>

        {loadingProjects && <Loading text="Loading projects…" />}

        {!loadingProjects && recentProjects.length === 0 && (
          <div className="sr-empty" style={{ padding: "2.5rem 1rem" }}>
            <NoProjectsIllustration />
            <p className="sr-empty-title">No projects yet</p>
            <p className="sr-empty-desc">
              Create your first SafetyReady project to get started with Signal
              Detection or Submission Readiness workflows.
            </p>
            <button className="sr-btn sr-btn-primary" onClick={onCreateProject}>
              + Create your first project
            </button>
          </div>
        )}

        {!loadingProjects && recentProjects.length > 0 && (
          <div className="sr-recent-list">
            {recentProjects.map((p) => (
              <div
                key={p.id}
                className="sr-recent-row"
                role="button"
                tabIndex={0}
                onClick={() => onOpenProject(p.id)}
                onKeyDown={(e) => e.key === "Enter" && onOpenProject(p.id)}
                aria-label={`Open project ${p.name}`}
              >
                <span className="sr-recent-name">{p.name}</span>
                <div className="sr-recent-meta">
                  <Badge value={p.status} />
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                    {new Date(p.created_at).toLocaleDateString()}
                  </span>
                  <button
                    className="sr-btn sr-btn-secondary"
                    style={{ fontSize: "0.78rem", padding: "0.3rem 0.7rem" }}
                    onClick={(e) => { e.stopPropagation(); onOpenProject(p.id); }}
                  >
                    Open project
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ================================================================= */}
      {/* E. Trust / limitations strip                                        */}
      {/* ================================================================= */}
      <div className="sr-trust-strip">
        <div className="sr-trust-strip-inner">
          <span className="sr-trust-icon"><InfoIcon /></span>
          <span>
            <strong style={{ color: "var(--text-h)" }}>Assumptions &amp; Limitations: </strong>
            SafetyReady results are deterministic screening and assessment outputs
            generated from structured input data. They do NOT constitute proof of
            causality or regulatory compliance. All outputs require expert review by
            qualified pharmacovigilance or regulatory professionals before any
            decision is made. Always consult current ICH, FDA, EMA, or other
            applicable authority guidance.
          </span>
        </div>
      </div>
    </div>
  );
}
