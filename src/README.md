# SafetyReady — Source Code

This directory contains all source code for SafetyReady.

For full setup and run instructions see [`../docs/setup-guide.md`](../docs/setup-guide.md).

---

## Layout

```
src/
├── backend/                   Python 3.11+ / FastAPI
│   ├── app/
│   │   ├── db/                Engine, session factory, FastAPI dependency
│   │   ├── models/            SQLModel ORM table definitions
│   │   ├── routers/           Thin FastAPI route handlers
│   │   │   ├── health.py      GET /api/health
│   │   │   ├── projects.py    CRUD for projects
│   │   │   ├── jobs.py        Job status polling
│   │   │   ├── signals.py     Signal upload, results, export
│   │   │   └── readiness.py   Readiness upload, summary, gaps, export
│   │   ├── services/
│   │   │   ├── signal/        PRR signal detection pipeline
│   │   │   │   ├── engine.py        Orchestrator — ingest → normalise → PRR → persist
│   │   │   │   ├── ingestion.py     CSV/JSON parsing, deduplication
│   │   │   │   ├── normalisation.py Drug/event alias dict + rapidfuzz clustering
│   │   │   │   ├── prr.py           Contingency tables, PRR, CI, thresholds, ranking
│   │   │   │   └── types.py         Internal dataclasses
│   │   │   └── readiness/     CTD readiness assessment pipeline
│   │   │       ├── engine.py        Orchestrator — parse → catalog → map → score → persist
│   │   │       ├── catalog.py       Versioned 20-entry ICH CTD requirements catalog
│   │   │       ├── mapper.py        4-tier requirement → section matching
│   │   │       ├── scorer.py        Per-module weighted scoring + overall mean
│   │   │       ├── gaps.py          Gap record generation with severity + recommendations
│   │   │       ├── parser.py        JSON/CSV dossier outline parser
│   │   │       └── types.py         Internal dataclasses
│   │   ├── config.py          Pydantic-settings (DATABASE_URL, APP_PORT, APP_ENV)
│   │   ├── main.py            FastAPI app factory with CORS and lifespan
│   │   └── schemas.py         Pydantic request/response schemas (API contract)
│   ├── tests/
│   │   ├── fixtures/          faers_demo.csv, dossier_outline.json, expected_results.json
│   │   ├── test_signal_engine.py
│   │   ├── test_readiness_engine.py
│   │   ├── test_api.py
│   │   ├── test_projects.py
│   │   ├── test_contracts.py
│   │   ├── test_database.py
│   │   ├── test_health.py
│   │   ├── _manual_flow.py    End-to-end smoke test (no HTTP server needed)
│   │   └── conftest.py        Shared pytest fixtures (in-memory DB session)
│   ├── pytest.ini
│   └── requirements.txt
│
└── frontend/                  TypeScript / React 19 / Vite 8
    ├── src/
    │   ├── components/
    │   │   ├── UploadZone.tsx  Drag-and-drop file upload input
    │   │   ├── JobPoller.tsx   Polls job status until complete or failed
    │   │   └── shared.tsx      Reusable UI primitives (Badge, Drawer, ScoreBar, etc.)
    │   ├── lib/
    │   │   └── apiClient.ts    Typed wrapper for all backend REST endpoints
    │   ├── pages/
    │   │   ├── ProjectsPage.tsx        Project list + create
    │   │   ├── ProjectDetailPage.tsx   Tab router: Signal Detection / Readiness
    │   │   ├── SignalDetectionPage.tsx Signal upload → poll → ranked table → detail drawer
    │   │   └── ReadinessPage.tsx       Dossier upload → poll → score cards + gap table
    │   ├── types/
    │   │   └── api.ts          TypeScript mirror of backend schemas.py
    │   └── App.tsx             Hash-based SPA router
    ├── .env.example
    └── package.json
```

---

## Environment Variables

**Backend** (all optional — defaults work out of the box):

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./safetyready.db` | SQLAlchemy database URL |
| `APP_PORT` | `8000` | Uvicorn port |
| `APP_ENV` | `development` | Environment name |

**Frontend**:

| Variable | Default | Description |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | Backend API base URL |

Copy examples:

```bash
cp src/.env.example src/backend/.env
cp src/frontend/.env.example src/frontend/.env
```

No API keys or external service credentials are required.

---

## Quick Start

```bash
# Backend
cd src/backend
python -m venv .venv && .venv\Scripts\activate    # Windows
# or: source .venv/bin/activate                   # macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd src/frontend
npm install && npm run dev
```

See [`../docs/setup-guide.md`](../docs/setup-guide.md) for the full tested walkthrough.
