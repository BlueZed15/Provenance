from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.api import IngestRequest, IngestResponse
from backend.app.services.analysis import run_analysis_job
from backend.app.services.ingestion import ingest_records
from backend.app.services.reverification import invalidate_changed_versions


router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
def ingest(
    payload: IngestRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
) -> IngestResponse:
    result = ingest_records(session, [item.to_record() for item in payload.items])
    plan = invalidate_changed_versions(session, result.versions)
    for job in plan.jobs_to_schedule:
        background_tasks.add_task(run_analysis_job, job.id)
    return IngestResponse(
        versions_ingested=result.versions_ingested,
        versions_reused=result.versions_reused,
        counts_by_layer=result.counts_by_layer,
        hash_conflicts=result.hash_conflicts,
        stale_reports=len(plan.stale_report_ids),
        reverification_jobs=[job.id for job in plan.jobs],
    )
