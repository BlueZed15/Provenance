from fastapi import APIRouter

from backend.app.api.routes import artifacts, health, ingest, integrations, jobs, reports
from backend.app.api.routes import (
    decisions,
)


api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
api_router.include_router(ingest.router, tags=["ingestion"])
api_router.include_router(decisions.router, tags=["decisions"])
api_router.include_router(jobs.router, tags=["analysis"])
api_router.include_router(reports.router, tags=["reports"])
api_router.include_router(artifacts.router, tags=["artifacts"])
api_router.include_router(integrations.router, tags=["integrations"])
