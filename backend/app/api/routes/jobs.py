import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.domain.enums import AnalysisStage
from backend.app.models import AnalysisJob
from backend.app.schemas.api import JobResponse


router = APIRouter()

STAGE_PROGRESS = {
    AnalysisStage.QUEUED: 0,
    AnalysisStage.EXTRACTING_CLAIMS: 15,
    AnalysisStage.GENERATING_EMBEDDINGS: 30,
    AnalysisStage.RETRIEVING_EVIDENCE: 50,
    AnalysisStage.CLASSIFYING_EDGES: 60,
    AnalysisStage.CLASSIFYING_TRANSFORMS: 75,
    AnalysisStage.ASSEMBLING_REPORT: 90,
    AnalysisStage.COMPLETED: 100,
    AnalysisStage.FAILED: 100,
}


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: uuid.UUID, session: Session = Depends(get_db)) -> JobResponse:
    job = session.get(AnalysisJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis job not found")
    return JobResponse(
        job_id=job.id,
        decision_version_id=job.decision_version_id,
        status=job.status,
        mode=job.mode,
        stage=job.stage,
        progress=STAGE_PROGRESS[job.stage],
        error=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )
