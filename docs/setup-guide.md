# SafetyReady — Setup Guide

> This file is the authoritative installation and run reference.
> All commands are tested on Python 3.13 / Node 22 on Windows, macOS, and Linux.

---

## Prerequisites

| Requirement | Minimum version | Notes |
|---|---|---|
| Python | 3.11+ | 3.13.x used in development |
| Node.js | 18+ | 22.x used in development |
| npm | 9+ | Bundled with Node |

No Docker, no external services, no IBM Cloud account required.  
Both workflows run entirely **without an LLM/AI key**.

---

## Environment Variables

**Backend** — copy and adjust if needed (all defaults work out of the box):

```bash
# src/backend/.env  (optional — defaults work without it)
DATABASE_URL=sqlite:///./safetyready.db   # default
APP_PORT=8000                              # default
APP_ENV=development                        # default
```

**Frontend** — copy `.env.example`:

```bash
cp src/frontend/.env.example src/frontend/.env
# Default: VITE_API_URL=http://localhost:8000
```

No API keys or secrets are required. The application runs fully offline.

---

## Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd bob-ai-hackathon-parallaxa

# 2. Install backend dependencies
cd src/backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt

# 3. Install frontend dependencies
cd ../frontend
npm install
```

---

## Running the Application

Open **two terminals** from the repository root:

**Terminal 1 — Backend:**

```bash
cd src/backend
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

uvicorn app.main:app --reload --port 8000
```

Backend available at: `http://localhost:8000`  
API docs (Swagger UI): `http://localhost:8000/api/docs`  
Health check: `http://localhost:8000/api/health`

**Terminal 2 — Frontend:**

```bash
cd src/frontend
npm run dev
```

Frontend available at: `http://localhost:5173`

---

## Running Tests

**Backend (304 tests):**

```bash
cd src/backend
# activate .venv first
pytest tests/ -v
```

**Frontend (51 tests):**

```bash
cd src/frontend
npm test
```

**Frontend type-check:**

```bash
cd src/frontend
npx tsc --noEmit
```

**Frontend production build:**

```bash
cd src/frontend
npm run build
```

---

## Database Reset

The SQLite database is created automatically on first startup. To reset to a clean state:

```bash
# Stop the backend server, then:
cd src/backend
# Windows:
Remove-Item safetyready.db -ErrorAction SilentlyContinue
# macOS/Linux:
rm -f safetyready.db
# Restart uvicorn — tables are recreated automatically on startup.
```

Test runs always use an isolated in-memory SQLite database and do not touch `safetyready.db`.

---

## Manual End-to-End Validation

A manual flow script exercises both core workflows against an in-memory DB:

```bash
cd src/backend
# activate .venv first
python tests/_manual_flow.py
```

Expected last line: `=== All manual flows completed successfully ===`

---

## Troubleshooting

| Issue | Solution |
|---|---|
| `ModuleNotFoundError: app` | Run pytest from `src/backend/`, not the repo root. `pytest.ini` sets `pythonpath = .` |
| `OperationalError: no column named mapping_method` | Run `ALTER TABLE requirement_mappings ADD COLUMN mapping_method VARCHAR(64); ALTER TABLE requirement_mappings ADD COLUMN confidence REAL;` against `safetyready.db`, or delete and restart the server. |
| Frontend shows `Failed to fetch` | Ensure the backend is running on port 8000 and CORS is not blocked. Check `VITE_API_URL` in `src/frontend/.env`. |
| `npm run build` fails | Run `npm install` in `src/frontend/` first. |
| `rapidfuzz` not found | Run `pip install -r requirements.txt` inside the activated `.venv`. |
