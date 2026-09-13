# SafetyReady — Technical Reference

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ |
| Node.js | 18+ |
| npm | 9+ |

---

## Installation

### Backend

```bash
cd src/backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### Frontend

```bash
cd src/frontend
npm install
```

---

## Configuration

```bash
# Copy the example and adjust if needed (defaults work for local dev)
cp src/.env.example src/backend/.env
cp src/frontend/.env.example src/frontend/.env
```

---

## Start (development)

Open two terminals:

**Terminal 1 — backend**
```bash
cd src/backend
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — frontend**
```bash
cd src/frontend
npm run dev
```

- API docs: http://localhost:8000/docs
- Frontend: http://localhost:5173

---

## Test

### Backend

```bash
cd src/backend
.venv\Scripts\activate   # or: source .venv/bin/activate

pytest
```

### Frontend

```bash
cd src/frontend
npm test          # Vitest (interactive)
npm run build     # Type-check + production build
```

---

## Directory structure

```
src/
├── backend/
│   ├── app/
│   │   ├── db/           # Engine, session, dependency
│   │   ├── models/       # SQLModel ORM models
│   │   ├── routers/      # Thin FastAPI route handlers
│   │   ├── services/     # Domain logic (signal_service, readiness_service go here)
│   │   ├── config.py     # Pydantic-settings
│   │   ├── main.py       # App factory
│   │   └── schemas.py    # Shared Pydantic request/response types
│   ├── tests/
│   ├── pytest.ini
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── lib/          # apiClient.ts
│   │   └── types/        # api.ts  (mirrors backend schemas.py)
│   ├── .env.example
│   └── package.json
└── .env.example          # Canonical env-var reference
```
