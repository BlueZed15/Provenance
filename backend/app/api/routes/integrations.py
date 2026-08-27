from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.api import AtlassianSyncRequest, AtlassianSyncResponse
from backend.app.services.analysis import run_analysis_job
from backend.app.services.atlassian import AtlassianBoundaries, AtlassianSyncService
from backend.app.services.mistral.connectors import ConnectorError
from backend.app.services.reverification import invalidate_changed_versions


router = APIRouter()


@router.post(
    "/integrations/atlassian/sync",
    response_model=AtlassianSyncResponse,
)
async def sync_atlassian(
    payload: AtlassianSyncRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
) -> AtlassianSyncResponse:
    try:
        result = await AtlassianSyncService().sync(
            session,
            AtlassianBoundaries(
                jsm_project_key=payload.jsm_project_key,
                roadmap_project_key=payload.roadmap_project_key,
                confluence_space_key=payload.confluence_space_key,
                roadmap_issue_type=payload.roadmap_issue_type,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except (ConnectorError, RuntimeError) as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "The configured Mistral Studio Atlassian connector could not complete the sync.",
        ) from exc
    plan = invalidate_changed_versions(session, result.ingestion.versions)
    for job in plan.jobs_to_schedule:
        background_tasks.add_task(run_analysis_job, job.id)
    return AtlassianSyncResponse(
        versions_ingested=result.ingestion.versions_ingested,
        versions_reused=result.ingestion.versions_reused,
        counts_by_layer=result.ingestion.counts_by_layer,
        hash_conflicts=result.ingestion.hash_conflicts,
        accessible_resource_count=result.accessible_resource_count,
        source_instance=result.source_instance,
        skipped_blank_items=result.skipped_blank_items,
        stale_reports=len(plan.stale_report_ids),
        reverification_jobs=[job.id for job in plan.jobs],
    )
