# Provenance frontend

The React interface renders the FastAPI Decision Integrity Report inside a
Jira-style issue view. During development, Vite proxies `/api` to
`http://127.0.0.1:8000`.

```bash
npm ci
npm run dev
```

Configuration lives in `.env`:

```text
VITE_API_BASE_URL=/api/v1
VITE_DEFAULT_ISSUE_KEY=ROAD-42
```

The live path discovers decisions, loads the selected issue and referenced
artifacts, renders report transforms, polls analysis/reverification jobs, and
shows staleness. The Hackathon Console also provides a clearly labelled local
fallback for the three verdict states if credentials or network access fail
during the presentation.

Run all frontend checks with:

```bash
npm run lint
npm test
npm run build
```
