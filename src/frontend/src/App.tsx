/**
 * App root — hash-based client-side router.
 * Routes: / | /projects/:id | /projects/:id/signal | /projects/:id/readiness
 *
 * No external routing library is required — the route is stored in state
 * and updated via the URL hash for deep-linkable pages.
 */
import { useEffect, useState } from "react";
import "./App.css";
import { ProjectsPage } from "./pages/ProjectsPage";
import { ProjectDetailPage } from "./pages/ProjectDetailPage";
import { SignalDetectionPage } from "./pages/SignalDetectionPage";
import { ReadinessPage } from "./pages/ReadinessPage";

// ---------------------------------------------------------------------------
// Route types
// ---------------------------------------------------------------------------

type Route =
  | { page: "projects" }
  | { page: "project"; projectId: number }
  | { page: "signal"; projectId: number }
  | { page: "readiness"; projectId: number };

function parseHash(hash: string): Route {
  const path = hash.replace(/^#\/?/, "");
  const parts = path.split("/");
  if (parts[0] === "projects" && parts[1]) {
    const id = parseInt(parts[1], 10);
    if (!isNaN(id)) {
      if (parts[2] === "signal") return { page: "signal", projectId: id };
      if (parts[2] === "readiness") return { page: "readiness", projectId: id };
      return { page: "project", projectId: id };
    }
  }
  return { page: "projects" };
}

function routeToHash(route: Route): string {
  if (route.page === "projects") return "#/";
  if (route.page === "project") return `#/projects/${route.projectId}`;
  if (route.page === "signal") return `#/projects/${route.projectId}/signal`;
  if (route.page === "readiness") return `#/projects/${route.projectId}/readiness`;
  return "#/";
}

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

export default function App() {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));

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
    }
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  function navigate(next: Route) {
    setRoute(next);
  }

  const projectId =
    route.page === "project" ||
    route.page === "signal" ||
    route.page === "readiness"
      ? route.projectId
      : null;

  return (
    <div className="sr-layout">
      {/* Header */}
      <header className="sr-header">
        <button
          className="sr-logo"
          onClick={() => navigate({ page: "projects" })}
          aria-label="SafetyReady home"
        >
          Safety<span className="sr-logo-dot">Ready</span>
        </button>

        {projectId !== null && (
          <nav className="sr-nav">
            <button
              className={`sr-nav-link ${route.page === "project" ? "active" : ""}`}
              onClick={() => navigate({ page: "project", projectId: projectId! })}
            >
              Overview
            </button>
            <button
              className={`sr-nav-link ${route.page === "signal" ? "active" : ""}`}
              onClick={() => navigate({ page: "signal", projectId: projectId! })}
            >
              Signal Detection
            </button>
            <button
              className={`sr-nav-link ${route.page === "readiness" ? "active" : ""}`}
              onClick={() => navigate({ page: "readiness", projectId: projectId! })}
            >
              Readiness
            </button>
          </nav>
        )}
      </header>

      {/* Main */}
      <main className="sr-main">
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
