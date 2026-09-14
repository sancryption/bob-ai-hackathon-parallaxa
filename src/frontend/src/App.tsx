/**
 * App root — hash-based client-side router.
 * Routes:
 *   #/                      → Home/Dashboard
 *   #/projects              → Projects list
 *   #/projects/:id          → Project detail
 *   #/projects/:id/signal   → Signal Detection
 *   #/projects/:id/readiness → Submission Readiness
 *
 * No external routing library — route is stored in state, URL hash for deep links.
 */
import { useEffect, useState } from "react";
import "./App.css";
import { ProjectsPage } from "./pages/ProjectsPage";
import { ProjectDetailPage } from "./pages/ProjectDetailPage";
import { SignalDetectionPage } from "./pages/SignalDetectionPage";
import { ReadinessPage } from "./pages/ReadinessPage";
import { HomePage } from "./pages/HomePage";

// ---------------------------------------------------------------------------
// Route types
// ---------------------------------------------------------------------------

type Route =
  | { page: "home" }
  | { page: "projects" }
  | { page: "project"; projectId: number }
  | { page: "signal"; projectId: number }
  | { page: "readiness"; projectId: number };

function parseHash(hash: string): Route {
  const path = hash.replace(/^#\/?/, "");
  const parts = path.split("/");

  if (parts[0] === "projects") {
    if (parts[1]) {
      const id = parseInt(parts[1], 10);
      if (!isNaN(id)) {
        if (parts[2] === "signal") return { page: "signal", projectId: id };
        if (parts[2] === "readiness") return { page: "readiness", projectId: id };
        return { page: "project", projectId: id };
      }
    }
    return { page: "projects" };
  }

  if (path === "" || path === "/") return { page: "home" };
  return { page: "home" };
}

function routeToHash(route: Route): string {
  if (route.page === "home") return "#/";
  if (route.page === "projects") return "#/projects";
  if (route.page === "project") return `#/projects/${route.projectId}`;
  if (route.page === "signal") return `#/projects/${route.projectId}/signal`;
  if (route.page === "readiness") return `#/projects/${route.projectId}/readiness`;
  return "#/";
}

// ---------------------------------------------------------------------------
// SVG icons (inline, no external dependency)
// ---------------------------------------------------------------------------

function ShieldIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 2L3 7v5c0 5.25 3.75 10.15 9 11.5C17.25 22.15 21 17.25 21 12V7l-9-5z"
        fill="currentColor"
        opacity="0.9"
      />
      <path
        d="M9 12l2 2 4-4"
        stroke="#fff"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function HamburgerIcon({ open }: { open: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      {open ? (
        <>
          <line x1="4" y1="4" x2="20" y2="20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          <line x1="20" y1="4" x2="4" y2="20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </>
      ) : (
        <>
          <line x1="3" y1="6" x2="21" y2="6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          <line x1="3" y1="12" x2="21" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          <line x1="3" y1="18" x2="21" y2="18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </>
      )}
    </svg>
  );
}

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

export default function App() {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Keep hash in sync with route state
  useEffect(() => {
    const hash = routeToHash(route);
    if (window.location.hash !== hash) {
      window.location.hash = hash;
    }
  }, [route]);

  // Sync route state from hash changes (back/forward navigation)
  useEffect(() => {
    function onHashChange() {
      setRoute(parseHash(window.location.hash));
      setMobileMenuOpen(false);
    }
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  function navigate(next: Route) {
    setRoute(next);
    setMobileMenuOpen(false);
  }

  const projectId =
    route.page === "project" ||
    route.page === "signal" ||
    route.page === "readiness"
      ? route.projectId
      : null;

  const isHome = route.page === "home";
  const isProjects = route.page === "projects";

  return (
    <div className="sr-layout">
      {/* ---- Header ---- */}
      <header className="sr-header">
        <div className="sr-header-inner">
          {/* Logo */}
          <button
            className="sr-logo"
            onClick={() => navigate({ page: "home" })}
            aria-label="SafetyReady home"
          >
            <span className="sr-logo-mark">
              <ShieldIcon />
            </span>
            <span className="sr-logo-text">
              Safety<span className="sr-logo-accent">Ready</span>
            </span>
          </button>

          {/* Primary nav (desktop) */}
          <nav className="sr-nav-primary" aria-label="Primary navigation">
            <button
              className={`sr-nav-link${isHome ? " active" : ""}`}
              onClick={() => navigate({ page: "home" })}
            >
              Home
            </button>
            <button
              className={`sr-nav-link${isProjects ? " active" : ""}`}
              onClick={() => navigate({ page: "projects" })}
            >
              Projects
            </button>
          </nav>

          {/* Project-context nav (desktop) */}
          {projectId !== null && (
            <>
              <div className="sr-nav-sep" aria-hidden="true" />
              <nav className="sr-nav-context" aria-label="Project navigation">
                <button
                  className={`sr-nav-link${route.page === "project" ? " active" : ""}`}
                  onClick={() => navigate({ page: "project", projectId: projectId! })}
                >
                  Overview
                </button>
                <button
                  className={`sr-nav-link${route.page === "signal" ? " active" : ""}`}
                  onClick={() => navigate({ page: "signal", projectId: projectId! })}
                >
                  Signal Detection
                </button>
                <button
                  className={`sr-nav-link${route.page === "readiness" ? " active" : ""}`}
                  onClick={() => navigate({ page: "readiness", projectId: projectId! })}
                  aria-label="Readiness"
                >
                  Readiness
                </button>
              </nav>
            </>
          )}

          {/* Right side */}
          <div className="sr-header-right">
            <span className="sr-workspace-badge">Workspace</span>
          </div>

          {/* Mobile menu toggle */}
          <button
            className="sr-mobile-menu-btn"
            onClick={() => setMobileMenuOpen((o) => !o)}
            aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
            aria-expanded={mobileMenuOpen}
          >
            <HamburgerIcon open={mobileMenuOpen} />
          </button>
        </div>
      </header>

      {/* Mobile nav dropdown */}
      <nav
        className={`sr-mobile-nav${mobileMenuOpen ? " open" : ""}`}
        aria-label="Mobile navigation"
      >
        <button
          className={`sr-nav-link${isHome ? " active" : ""}`}
          onClick={() => navigate({ page: "home" })}
        >
          Home
        </button>
        <button
          className={`sr-nav-link${isProjects ? " active" : ""}`}
          onClick={() => navigate({ page: "projects" })}
        >
          Projects
        </button>
        {projectId !== null && (
          <>
            <button
              className={`sr-nav-link${route.page === "project" ? " active" : ""}`}
              onClick={() => navigate({ page: "project", projectId: projectId! })}
            >
              Overview
            </button>
            <button
              className={`sr-nav-link${route.page === "signal" ? " active" : ""}`}
              onClick={() => navigate({ page: "signal", projectId: projectId! })}
            >
              Signal Detection
            </button>
            <button
              className={`sr-nav-link${route.page === "readiness" ? " active" : ""}`}
              onClick={() => navigate({ page: "readiness", projectId: projectId! })}
              aria-label="Readiness"
            >
              Readiness
            </button>
          </>
        )}
      </nav>

      {/* ---- Main ---- */}
      <main className="sr-main">
        {route.page === "home" && (
          <HomePage
            onOpenProjects={() => navigate({ page: "projects" })}
            onCreateProject={() => navigate({ page: "projects" })}
            onOpenProject={(id) => navigate({ page: "project", projectId: id })}
          />
        )}

        {route.page === "projects" && (
          <ProjectsPage
            onOpenProject={(id) => navigate({ page: "project", projectId: id })}
          />
        )}

        {route.page === "project" && (
          <ProjectDetailPage
            projectId={route.projectId}
            onNavigate={(r) => navigate({ page: r, projectId: route.projectId })}
            onBack={() => navigate({ page: "projects" })}
          />
        )}

        {route.page === "signal" && (
          <SignalDetectionPage projectId={route.projectId} />
        )}

        {route.page === "readiness" && (
          <ReadinessPage projectId={route.projectId} />
        )}
      </main>
    </div>
  );
}
