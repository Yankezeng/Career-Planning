# Career Planning Source Edition

This repository contains the source-only version of the Career Agent project.
Large local artifacts such as HuggingFace model weights, virtual environments,
databases, uploaded files, frontend builds, and packaged archives are excluded
from Git so the repository can be cloned and maintained normally.

## Project Layout

```text
career-agent/
  backend/   FastAPI, SQLAlchemy, Alembic, AI agent services
  frontend/  Vue 3, Vite, Element Plus, ECharts
  models/    README only; model binaries are downloaded locally
  sql/       database initialization and seed SQL
```

## Backend

```bash
cd career-agent/backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Fill real API keys only in `.env`. Do not commit `.env`.

## Frontend

```bash
cd career-agent/frontend
npm install
npm run dev
```

Default local URLs:

- Frontend: `http://127.0.0.1:5173`
- Backend API: `http://127.0.0.1:8000`

## Model Assets

The model binaries are not stored in this repository. Keep
`HF_MODEL_AUTO_DOWNLOAD=true` for first-use download, or pre-download from the
backend:

```bash
cd career-agent/backend
python scripts/init_models.py
```

See `career-agent/models/README.md` for the local model layout.
