# Provenance

Provenance is a semantic integrity layer for product decisions. It traces exact
claims from Jira Service Management and Confluence into a Jira roadmap decision,
then uses Mistral-only analysis to show what was preserved, changed, omitted, or
left unresolved.

This branch contains the integrated FastAPI backend and React frontend.

## Run the integrated app

Prerequisites: Python 3.11+, Node.js 22+, PostgreSQL with the `vector` extension,
and a Mistral API key.

From the repository root:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
npm --prefix provenance-frontend ci
cp .env.example .env
```

Fill in `DATABASE_URL` and `MISTRAL_API_KEY` in `.env`, then initialise the
database and launch both applications:

```bash
.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
./run.sh
```

Open `http://127.0.0.1:5173`. The frontend development server proxies `/api`
to FastAPI at `http://127.0.0.1:8000`, so the two branches work as one app.

`VITE_DEFAULT_ISSUE_KEY` in `provenance-frontend/.env` selects the preferred Jira
decision. If that key is not present, the UI safely loads the most recently
updated ingested decision. Live API failures automatically reveal the local
presentation fallback without making any non-Mistral model call.

## Verify before the demo

```bash
npm --prefix provenance-frontend run lint
npm --prefix provenance-frontend test
npm --prefix provenance-frontend run build
DATABASE_URL=postgresql://test:test@127.0.0.1:5432/test \
  .venv/bin/python -m unittest \
  backend.tests.test_atlassian_mappers \
  backend.tests.test_atlassian_sync \
  backend.tests.test_verdicts \
  backend.tests.test_analysis_modes
```

For live database/Mistral verification, use the safe diagnostics documented in
`backend/README.md`.

## Integrated frontend flow

1. Load `GET /api/v1/decisions` and select the configured Jira key.
2. Load the immutable decision version and Jira provenance lookup together.
3. Hydrate every artifact version referenced by the report edges.
4. Render backend verdicts, confidence labels, claim transforms, source quotes,
   freshness status, and links to their original Atlassian artifacts.
5. If a report does not exist, start a Mistral analysis and poll its job to
   completion. Existing jobs can be resumed rather than duplicated.
6. Reverification uses the backend job flow and reloads the immutable report.

All inference routes use the Mistral SDK and the configured Mistral extraction,
embedding, and transform-classification models. No other model provider is used.
