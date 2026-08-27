import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.domain.enums import JobStatus, Layer, SourceTool
from backend.app.models import AnalysisJob, Artifact, ArtifactVersion, DecisionReport
from backend.app.schemas.api import (
    AnalysisStartResponse,
    DecisionListResponse,
    DecisionSummary,
    JiraProvenanceResponse,
    ReverifyResponse,
)
from backend.app.services.analysis import create_analysis_job, run_analysis_job
from backend.app.services.reports import get_decision_report
from backend.app.services.reverification import force_reverification


router = APIRouter()


@router.get("/decisions", response_model=DecisionListResponse)
def list_decisions(session: Session = Depends(get_db)) -> DecisionListResponse:
    artifacts = list(
        session.scalars(
            select(Artifact)
            .where(Artifact.layer == Layer.ROADMAP)
            .order_by(Artifact.updated_at.desc())
        )
    )
    decisions: list[DecisionSummary] = []
    for artifact in artifacts:
        version = session.scalar(
            select(ArtifactVersion)
            .where(ArtifactVersion.artifact_id == artifact.id)
            .order_by(ArtifactVersion.version_number.desc())
            .limit(1)
        )
        if version is None:
            continue
        report = session.scalar(
            select(DecisionReport)
            .join(ArtifactVersion, DecisionReport.decision_version_id == ArtifactVersion.id)
            .where(ArtifactVersion.artifact_id == artifact.id)
            .order_by(DecisionReport.generated_at.desc())
            .limit(1)
        )
        title = str(version.artifact_metadata.get("summary") or "").strip()
        if not title:
            title = version.text.splitlines()[0][:120]
        decisions.append(
            DecisionSummary(
                id=artifact.id,
                version_id=version.id,
                external_id=artifact.external_id,
                title=title,
                source_tool=artifact.source_tool,
                source_instance=artifact.source_instance,
                external_url=artifact.external_url,
                updated_at=version.source_updated_at or version.source_created_at,
                latest_verdict=report.verdict if report else None,
            )
        )
    return DecisionListResponse(decisions=decisions)


@router.post(
    "/decisions/{decision_id}/analyses",
    response_model=AnalysisStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_analysis(
    decision_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
) -> AnalysisStartResponse:
    try:
        job = create_analysis_job(session, decision_id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    if job.status == JobStatus.QUEUED:
        background_tasks.add_task(run_analysis_job, job.id)
    return AnalysisStartResponse(job_id=job.id, status=job.status)


@router.post(
    "/reverify/{decision_id}",
    response_model=ReverifyResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def reverify_decision(
    decision_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
) -> ReverifyResponse:
    try:
        previous_report, job, should_schedule = force_reverification(
            session,
            decision_id,
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    if should_schedule and job.status == JobStatus.QUEUED:
        background_tasks.add_task(run_analysis_job, job.id)
    return ReverifyResponse(
        decision_id=decision_id,
        previous_report_id=previous_report.id,
        previous_verdict=previous_report.verdict,
        job_id=job.id,
        status=job.status,
    )


@router.get(
    "/jira/issues/{issue_key}/provenance",
    response_model=JiraProvenanceResponse,
)
def jira_provenance(
    issue_key: str,
    session: Session = Depends(get_db),
) -> JiraProvenanceResponse:
    artifact = session.scalar(
        select(Artifact).where(
            Artifact.external_id == issue_key,
            Artifact.source_tool == SourceTool.JIRA,
            Artifact.layer == Layer.ROADMAP,
        )
    )
    if artifact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ingested Jira decision not found")

    report = get_decision_report(session, artifact.id)
    active_job = session.scalar(
        select(AnalysisJob)
        .join(ArtifactVersion, AnalysisJob.decision_version_id == ArtifactVersion.id)
        .where(
            ArtifactVersion.artifact_id == artifact.id,
            AnalysisJob.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
        )
        .order_by(AnalysisJob.created_at.desc())
        .limit(1)
    )
    return JiraProvenanceResponse(
        issue_key=artifact.external_id,
        decision_id=artifact.id,
        analysis_required=(report is None or report.is_stale) and active_job is None,
        active_job_id=active_job.id if active_job else None,
        report=report,
    )
