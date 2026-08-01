# Provenance backend

Runtime baseline: **Python 3.13**.

## Local setup

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

The health endpoint is `GET http://127.0.0.1:8000/api/v1/health` and the
OpenAPI interface is available at `http://127.0.0.1:8000/docs`.

## Tier 1 API

The implemented Tier 1 routes are:

```text
GET  /api/v1/health
POST /api/v1/ingest
GET  /api/v1/decisions
POST /api/v1/decisions/{decision_id}/analyses
GET  /api/v1/jobs/{job_id}
GET  /api/v1/reports/{decision_id}
GET  /api/v1/artifact-versions/{version_id}
GET  /api/v1/artifact-versions/{version_id}/claims
POST /api/v1/integrations/atlassian/sync
GET  /api/v1/jira/issues/{issue_key}/provenance
POST /api/v1/reverify/{decision_id}
```

## Endpoint meaning map for the frontend

Base URL during local development: `http://127.0.0.1:8000/api/v1`.

| Method and path | Plain meaning | When the frontend uses it | Important result |
| --- | --- | --- | --- |
| `GET /health` | Is the backend ready? | App startup or diagnostics only. | `200` means ready; `503` means the database or Mistral configuration is unavailable. |
| `POST /ingest` | Store supplied evidence and decisions. | Demo-data/admin screen, not a normal report screen. | Counts of new/reused versions plus any automatically queued reverification job IDs. |
| `GET /decisions` | List all roadmap decisions known to Provenance. | Main decision list/dashboard. | `id` is the internal `decision_id`; `external_id` is the Jira key; `latest_verdict` may be `null`. |
| `POST /decisions/{decision_id}/analyses` | Analyse a decision for the first time. | User selects a decision that has no report. | Returns `202` with a `job_id`; poll the job endpoint. |
| `GET /jobs/{job_id}` | Check analysis progress. | Loading/progress screen. | `status`, `stage`, `progress`, `mode`, and a safe error message. |
| `GET /reports/{decision_id}` | Get the complete provenance trace and verdict. | Main Provenance decision view. | Report status, verdict, graph edges, transformations, source quotes, scores, and comparison with the previous report. |
| `GET /artifact-versions/{version_id}` | Read one immutable source version. | Artifact detail drawer or evidence inspector. | Original normalized text, source identity, timestamps, links, metadata, and content hash. |
| `GET /artifact-versions/{version_id}/claims` | Read the claims extracted from one source version. | Highlighting claims inside an artifact detail view. | Exact source spans and offsets plus structured claim fields. |
| `POST /integrations/atlassian/sync` | Import only labelled demo content from Jira/JSM/Confluence through Mistral Studio. | Admin/demo sync button. | Ingestion counts, stale-report count, and automatic reverification job IDs. |
| `GET /jira/issues/{issue_key}/provenance` | Look up Provenance using a Jira key such as `PRODUCT-12`. | Jira-style page or embedded Jira tab. | Internal decision ID, current report, active job, or `analysis_required=true`. |
| `POST /reverify/{decision_id}` | Manually check a decision against the latest evidence. | “Reverify now” button. | Returns `202` with a current-state `job_id`; poll it, then reload the report. |

### IDs used by the frontend

- `issue_key` / `external_id`: the human-readable Jira key, such as
  `PRODUCT-12`.
- `decision_id`: the internal artifact UUID returned by `/decisions` or the Jira
  provenance lookup. Use this for analysis, report, and reverify routes.
- `version_id`: an immutable artifact-version UUID. Use this for artifact and
  claim detail routes.
- `job_id`: an asynchronous analysis UUID. Use this only with `/jobs/{job_id}`.

### Recommended frontend flows

Decision list to report:

```text
GET /decisions
  -> select decision.id
  -> GET /reports/{decision.id}
  -> if 404, POST /decisions/{decision.id}/analyses
  -> poll GET /jobs/{job_id}
  -> reload GET /reports/{decision.id}
```

Jira issue page:

```text
GET /jira/issues/{issue_key}/provenance
  -> report exists: render it
  -> active_job_id exists: poll the job
  -> analysis_required=true: show "Analyse" action
```

Atlassian refresh:

```text
POST /integrations/atlassian/sync
  -> show ingestion/stale counts
  -> poll every returned reverification job_id
  -> reload the selected decision report
```

Manual reverification:

```text
POST /reverify/{decision_id}
  -> poll GET /jobs/{job_id} until COMPLETED or FAILED
  -> GET /reports/{decision_id}
```

### Report fields and UI meaning

Use `verification_status` separately from `verdict`:

| Field value | Frontend meaning |
| --- | --- |
| `CURRENT` | This report reflects the latest evidence known to the backend. |
| `STALE` | Evidence changed and the previous report should display a stale warning. |
| `VERIFYING` | Display the previous report with a re-analysis-in-progress indicator. |

Suggested verdict presentation:

| Verdict | Meaning | Suggested treatment |
| --- | --- | --- |
| `ALIGNED` | Important evidence was preserved. | Green |
| `DRIFT` | A critical meaning change was detected. | Red |
| `NO_EVIDENCE` | No defensible evidence chain was found. | Amber, never accusatory |
| `UNRESOLVED` | Multiple plausible chains remain. | Amber |

Additional report mappings:

- `edges` form the trace graph. `from_version_id` is downstream and
  `to_version_id` is its proposed upstream source.
- `transforms` explain what changed across each edge. Join them through
  `transform.edge_id == edge.id`.
- `source_quotes` contain exact spans suitable for evidence cards and quoted-text
  highlighting.
- `max_drift_transform_id` identifies the transformation the UI should emphasize.
- `allowed_actions` tells the UI which follow-up controls are valid.
- `comparison` is `null` for the first report; after reverification it summarizes
  the previous verdict, changed edges, and added/removed transform types.
- Internal numeric retrieval scores are intentionally not exposed.

### Polling guidance

After receiving a `202`, poll `/jobs/{job_id}` about once per second for the
hackathon. Stop when `status` becomes `COMPLETED` or `FAILED`. On completion,
reload the report rather than trying to construct one from the job response.

`POST /api/v1/integrations/atlassian/sync` uses the configured Mistral Studio
Atlassian connector. It accepts only the explicit demo boundaries:

```json
{
  "jsm_project_key": "SUPPORT",
  "roadmap_project_key": "PRODUCT",
  "confluence_space_key": "PRODUCT",
  "roadmap_issue_type": "Epic"
}
```

The sync uses fixed labels: `provenance-demo`, `provenance-theme`,
`provenance-prd`, and `provenance-roadmap`. It does not infer layers, does not
ingest comments, includes closed tickets, and excludes archived Confluence
pages. JSON ingestion remains available through `/api/v1/ingest`.

Analysis jobs run as in-process FastAPI background tasks for the hackathon.
This deliberately avoids adding a queue or another service.

## Reverification

When `/api/v1/ingest` or `/api/v1/integrations/atlassian/sync` creates a new
content-hashed version, the backend automatically:

1. finds decisions whose latest provenance chain used that artifact;
2. marks each affected latest report stale;
3. queues one `CURRENT` analysis per affected decision; and
4. keeps the prior report as immutable history.

`GET /api/v1/reports/{decision_id}` exposes `CURRENT`, `STALE`, or `VERIFYING`,
the analysis mode, and a comparison with the previous report. `CURRENT`
analysis may use evidence edited after the decision and labels those edges with
`post_decision_update`. `POST /api/v1/reverify/{decision_id}` triggers the same
current-state check manually.

The Mistral Studio connector has no push webhook in this backend. Atlassian
changes are therefore detected on the next call to the sync endpoint; once the
changed version is ingested, staleness detection and re-analysis are automatic.

Run the safe database diagnostic without displaying credentials:

```powershell
.\.venv\Scripts\python.exe -m backend.scripts.check_database
```

Run a small live Mistral diagnostic covering claim extraction, embeddings, and
transform classification:

```powershell
.\.venv\Scripts\python.exe -m backend.scripts.check_mistral
```

Run the isolated live endpoint diagnostic. It creates uniquely namespaced
records, exercises ingestion, analysis, staleness, automatic and manual
reverification, and report comparison, then removes only those records:

```powershell
.\.venv\Scripts\python.exe -m backend.scripts.check_tier1_endpoints
```

Discover the configured Mistral Atlassian Connector's tools without printing
Jira or Confluence content:

```powershell
.\.venv\Scripts\python.exe -m backend.scripts.check_atlassian_connector
```

Probe read-only Jira and Confluence fidelity without printing source content:

```powershell
.\.venv\Scripts\python.exe -m backend.scripts.probe_atlassian_reads
```

Use one canonical `DATABASE_URL` in `.env`. For compatibility with the current
local environment, configuration can also assemble it from `user`, `password`,
`host`, `port`, and `dbname`; the canonical URL takes precedence when valid.

The health endpoint returns `503 degraded` until both PostgreSQL is reachable
and `MISTRAL_API_KEY` contains a non-placeholder value.

## Migrations

Run migrations from the repository root so imports remain consistent:

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini revision --autogenerate -m "describe change"
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
```

Verify the complete Tier 1 schema without inserting or printing application data:

```powershell
.\.venv\Scripts\python.exe -m backend.scripts.check_tier1_schema
```

Exercise Unicode, strict JSONB, UTC timestamp, claim-span, and 1,024-dimension
vector compatibility against PostgreSQL. The diagnostic always rolls its test
transaction back:

```powershell
.\.venv\Scripts\python.exe -m backend.scripts.check_data_contracts
```

Database credentials are loaded from the repository-level `.env`; never place
them in `alembic.ini`.
