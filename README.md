# SafetyReady

> Pharmacovigilance signal detection and ICH CTD submission readiness assessment — fully offline, no API keys required.

---

## 👥 Team

| Field | Value |
|---|---|
| **Team Name** | Parallaxa |
| **Track** | AI |
| **Team Lead** | Saniya Khatun Shaikh — 25bsit117@charusat.edu.in |
| **Members** | Vidhi Shah, Darshan Solanki, Khushi Patel |

---

## 🎯 Problem Statement

Pharmaceutical teams preparing new-drug regulatory submissions face two time-consuming, error-prone tasks: manually scanning large adverse-event datasets for drug-safety signals, and auditing whether a dossier covers every required ICH CTD section before submission. Both tasks are typically done with spreadsheets and tribal knowledge, leading to missed signals and costly late-stage regulatory rejections.

---

## 💡 Solution

SafetyReady is a full-stack pharmacovigilance and submission-readiness platform that automates both tasks. It ingests FAERS-style adverse-event reports and runs a deterministic PRR (Proportional Reporting Ratio) pipeline to surface ranked drug-safety signals with 95% confidence intervals. A second workflow accepts a structured dossier outline and maps it against a versioned ICH CTD requirements catalog, scoring each module and generating a prioritised gap list with specific recommendations. Both workflows run entirely offline with no external API dependencies.

---

## ✨ Key Features

- **PRR Signal Detection Engine:** Full 2×2 contingency tables, Evans 95% confidence intervals, configurable thresholds (PRR ≥ 2.0, a ≥ 3), severity ranking (low / medium / high / critical), and JSON/CSV export.
- **MedDRA-Aligned Event Normalisation:** Alias dictionary + rapidfuzz fuzzy clustering maps raw adverse-event strings to preferred MedDRA terms, with per-term provenance tracking and event cluster views.
- **ICH CTD Submission Readiness Assessment:** 4-tier requirement matching (exact code → normalised code → keyword/title → fuzzy title), per-module weighted scoring across all five ICH CTD modules, and a gap list with severity and actionable recommendations.
- **Background Job Runner with Live Polling:** Upload → queued → running → complete/failed lifecycle managed via FastAPI BackgroundTasks; the frontend polls without a page reload.
- **Comprehensive Test Suite:** 304 backend tests (pytest) and 51 frontend tests (Vitest), covering both engine pipelines against known fixture data with range-based assertions.

---

## 🛠️ Tech Stack

| Category | Technologies |
|---|---|
| **Languages** | Python 3.11+, TypeScript |
| **Frameworks** | FastAPI 0.115, React 19, Vite 8, SQLModel, Pydantic 2, Vitest |
| **IBM Technologies** | IBM Bob (used as development environment throughout the project) |
| **Databases** | SQLite via SQLAlchemy 2 / SQLModel |
| **Other** | rapidfuzz, uvicorn, python-multipart, GitHub Actions |

---

## 📁 Repository Structure

```
bob-ai-hackathon-parallaxa/
├── src/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── db/           # Engine, session, dependency
│   │   │   ├── models/       # SQLModel ORM models
│   │   │   ├── routers/      # FastAPI route handlers (health, projects, jobs, signals, readiness)
│   │   │   ├── services/
│   │   │   │   ├── signal/   # engine, ingestion, normalisation, prr, types
│   │   │   │   └── readiness/# engine, catalog, mapper, scorer, gaps, parser, types
│   │   │   ├── config.py
│   │   │   ├── main.py
│   │   │   └── schemas.py
│   │   ├── tests/            # 304 tests + fixtures (faers_demo.csv, dossier_outline.json)
│   │   └── requirements.txt
│   └── frontend/
│       └── src/
│           ├── components/   # UploadZone, JobPoller, shared UI
│           ├── lib/          # apiClient.ts
│           ├── pages/        # ProjectsPage, ProjectDetailPage, SignalDetectionPage, ReadinessPage
│           └── types/        # api.ts — TypeScript mirror of backend schemas
├── docs/                     # Architecture, setup, contracts, problem statement, solution overview
├── demo/                     # Demo video link, screenshots
└── submission.yaml
```

---

## ⚡ How to Run

See [`docs/setup-guide.md`](docs/setup-guide.md) for the full tested guide. Quick start:

```bash
# 1. Clone the repo
git clone https://github.com/sancryption/bob-ai-hackathon-parallaxa.git
cd bob-ai-hackathon-parallaxa

# 2. Backend
cd src/backend
python -m venv .venv
# Windows: .venv\Scripts\activate   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 3. Frontend (new terminal)
cd src/frontend
npm install
npm run dev
```

- **Frontend:** http://localhost:5173
- **API docs (Swagger):** http://localhost:8000/api/docs
- **Health check:** http://localhost:8000/api/health

No API keys or cloud accounts required.

---

## 🧪 Tests

```bash
# Backend (304 tests)
cd src/backend && pytest tests/ -v

# Frontend (51 tests)
cd src/frontend && npm test

# Manual end-to-end flow
cd src/backend && python tests/_manual_flow.py
```

---

## 🖥️ Demo

| Artifact | Link |
|---|---|
| 📹 Demo Video | [See demo/demo-video-link.txt](demo/demo-video-link.txt) |
| 🌐 Live Demo | [See demo/live-demo-url.txt](demo/live-demo-url.txt) |
| 🖼️ Screenshots | [See demo/screenshots/](demo/screenshots/) |
| 📊 Presentation | [See presentation/](presentation/) |

---

## ⚠️ Known Limitations

- **CTD catalog is illustrative:** The 20-entry prototype covers representative requirements from all 5 ICH CTD modules; it is not a complete jurisdiction-specific regulatory checklist.
- **Text/PDF dossier parsing is a stub:** Only JSON and CSV dossier outlines are processed; `parse_text_outline()` returns an empty list.
- **No authentication:** All API endpoints are public — suitable for local/demo use only.
- **SQLite only:** Not suitable for concurrent multi-user production deployments.
- **In-process job runner:** FastAPI `BackgroundTasks` runs in the same process as the web server — production would require Celery + Redis.
- **Drug alias dictionary:** Seeded with representative entries; real-world use requires extension.
- **No Alembic migrations:** Schema evolution requires manual `ALTER TABLE` or deleting `safetyready.db`.

---

## 🏅 What We're Most Proud Of

The two fully implemented analysis engines. The PRR signal detection engine is a complete, standards-based pharmacovigilance algorithm — not scaffolding — with case-version deduplication, MedDRA alias clustering, Evans confidence intervals, configurable thresholds, and severity ranking, validated by 304 tests against fixture data with known expected ranges. The CTD readiness engine implements a principled 4-tier matching strategy against a versioned catalog covering all five ICH modules, produces per-module weighted scores using a documented formula, and generates actionable gap recommendations with severity levels — all deterministic, reproducible, and fully offline.
