# Provenance — integrated stack (backend + React frontend)

Semantic integrity layer for product decisions. Mistral × Atlassian hackathon.

## What's wired together

- `backend/` — FastAPI Tier-1 API (from the `backend` branch): Postgres + pgvector,
  Mistral claim extraction / embeddings / transform classification, async analysis jobs.
- `provenance-frontend/` — React (Vite) Jira-style UI (from `vedant-react-frontend`),
  now fully API-driven: decision list, report + evidence chain with highlighted claim
  spans, analysis progress polling. Vite dev server proxies `/api` → `127.0.0.1:8000`.
- `ui/index.html` — zero-build fallback UI hitting the same API (serve any static way).
- `data/artifacts.json` — seed corpus (incl. real JRA-9 public data), POST to `/ingest`.

## Run it

```bash
# 1. Postgres + pgvector (Docker)
docker run -d --name provenance-pg -e POSTGRES_USER=provenance \
  -e POSTGRES_PASSWORD=provenance -e POSTGRES_DB=provenance \
  -p 5544:5432 pgvector/pgvector:pg16
docker exec provenance-pg psql -U provenance -d provenance \
  -c "CREATE SCHEMA IF NOT EXISTS extensions;" \
  -c "ALTER DATABASE provenance SET search_path TO public, extensions;"

# 2. Env — .env at repo root needs:
#    MISTRAL_API_KEY=...
#    DATABASE_URL=postgresql://provenance:provenance@127.0.0.1:5544/provenance?sslmode=disable
#    FRONTEND_ORIGIN=http://localhost:5173

# 3. Backend
python3 -m pip install -r backend/requirements.txt
python3 -m alembic -c backend/alembic.ini upgrade head
python3 -m uvicorn backend.app.main:app --port 8000

# 4. Seed demo data
curl -X POST http://127.0.0.1:8000/api/v1/ingest -H "Content-Type: application/json" \
  -d "$(python3 -c "import json;print(json.dumps({'items': json.load(open('data/artifacts.json'))['artifacts']}))")"

# 5. Frontend
npm --prefix provenance-frontend install
npm --prefix provenance-frontend run dev   # http://localhost:5173
```

First click on a decision triggers a live Mistral analysis (~30–60 s, progress shown);
results are cached in Postgres after that. Run analyses one at a time — the API's DB
pool is small.

## API surface the frontend uses

`GET /api/v1/decisions` → `GET /reports/{id}` (404 → `POST /decisions/{id}/analyses`
→ poll `GET /jobs/{job_id}`) → `GET /artifact-versions/{id}` + `/claims` for the chain.
