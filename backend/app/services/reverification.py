from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.app.domain.enums import AnalysisMode, JobStatus, Layer, Verdict
from backend.app.models import (
    AnalysisJob,
    Artifact,
    ArtifactVersion,
    DecisionReport,
    ProvenanceEdge,
)
from backend.app.repositories import PersistedVersion
from backend.app.services.analysis import create_analysis_job


@dataclass(frozen=True)
class ReverificationPlan:
    stale_report_ids: list[uuid.UUID]
    jobs: list[AnalysisJob]
    jobs_to_schedule: list[AnalysisJob]


def invalidate_changed_versions(
    session: Session,
    persisted_versions: list[PersistedVersion],
) -> ReverificationPlan:
    """Mark affected latest reports stale and queue one current-state analysis each."""
    changed = [version for version in persisted_versions if version.created]
    if not changed:
        return ReverificationPlan(
            stale_report_ids=[],
            jobs=[],
            jobs_to_schedule=[],
        )

    changed_artifact_ids = {version.artifact_id for version in changed}
    changed_version_ids = {version.version_id for version in changed}
    changed_version_by_artifact = {
        version.artifact_id: version.version_id for version in changed
    }
    artifacts = {
        artifact.id: artifact
        for artifact in session.scalars(
            select(Artifact).where(Artifact.id.in_(changed_artifact_ids))
        )
    }
    changed_sources = {artifact.source_instance for artifact in artifacts.values()}

    all_changed_artifact_version_ids = set(
        session.scalars(
            select(ArtifactVersion.id).where(
                ArtifactVersion.artifact_id.in_(changed_artifact_ids)
            )
        )
    )
    all_changed_artifact_version_ids.update(changed_version_ids)

    affected_decision_ids = {
        version.artifact_id
        for version in session.scalars(
            select(ArtifactVersion).where(
                ArtifactVersion.id.in_(
                    select(AnalysisJob.decision_version_id)
                    .join(
                        ProvenanceEdge,
                        ProvenanceEdge.analysis_job_id == AnalysisJob.id,
                    )
                    .where(
                        or_(
                            ProvenanceEdge.from_version_id.in_(
                                all_changed_artifact_version_ids
                            ),
                            ProvenanceEdge.to_version_id.in_(
                                all_changed_artifact_version_ids
                            ),
                        )
                    )
                )
            )
        )
    }
    affected_decision_ids.update(
        artifact_id
        for artifact_id in changed_artifact_ids
        if artifacts[artifact_id].layer == Layer.ROADMAP
    )

    latest_reports = _latest_reports_by_decision(session)
    for decision_id, report in latest_reports.items():
        decision = session.get(Artifact, decision_id)
        if (
            decision is not None
            and decision.source_instance in changed_sources
            and report.verdict in {Verdict.NO_EVIDENCE, Verdict.UNRESOLVED}
        ):
            affected_decision_ids.add(decision_id)

    now = datetime.now().astimezone()
    stale_reports: list[DecisionReport] = []
    for decision_id in affected_decision_ids:
        report = latest_reports.get(decision_id)
        if report is None:
            continue
        report.is_stale = True
        report.stale_at = now
        report.stale_reason = "An ingested artifact used by this decision changed."
        report.changed_version_id = changed_version_by_artifact.get(
            decision_id,
            changed[0].version_id,
        )
        stale_reports.append(report)
    session.commit()

    jobs: list[AnalysisJob] = []
    jobs_to_schedule: list[AnalysisJob] = []
    decision_ids = sorted(
        (report_decision_id(session, report) for report in stale_reports),
        key=str,
    )
    for decision_id in decision_ids:
        active = _active_current_job(session, decision_id)
        if active is not None:
            jobs.append(active)
            continue
        job = create_analysis_job(session, decision_id, mode=AnalysisMode.CURRENT)
        jobs.append(job)
        jobs_to_schedule.append(job)
    return ReverificationPlan(
        stale_report_ids=[report.id for report in stale_reports],
        jobs=jobs,
        jobs_to_schedule=jobs_to_schedule,
    )


def force_reverification(
    session: Session,
    decision_id: uuid.UUID,
) -> tuple[DecisionReport, AnalysisJob, bool]:
    latest_report = _latest_reports_by_decision(session).get(decision_id)
    if latest_report is None:
        raise LookupError("Decision has no report to reverify")

    if not latest_report.is_stale:
        latest_report.is_stale = True
        latest_report.stale_at = datetime.now().astimezone()
        latest_report.stale_reason = "Manual reverification requested."
        latest_report.changed_version_id = None
        session.commit()

    active = _active_current_job(session, decision_id)
    if active is not None:
        return latest_report, active, False
    job = create_analysis_job(session, decision_id, mode=AnalysisMode.CURRENT)
    return latest_report, job, True


def _latest_reports_by_decision(session: Session) -> dict[uuid.UUID, DecisionReport]:
    rows = session.execute(
        select(DecisionReport, ArtifactVersion.artifact_id)
        .join(
            ArtifactVersion,
            DecisionReport.decision_version_id == ArtifactVersion.id,
        )
        .order_by(DecisionReport.generated_at.desc())
    ).all()
    latest: dict[uuid.UUID, DecisionReport] = {}
    for report, decision_id in rows:
        latest.setdefault(decision_id, report)
    return latest


def report_decision_id(session: Session, report: DecisionReport) -> uuid.UUID:
    decision_version = session.get(ArtifactVersion, report.decision_version_id)
    if decision_version is None:
        raise LookupError("Report decision version no longer exists")
    return decision_version.artifact_id


def _active_current_job(
    session: Session,
    decision_id: uuid.UUID,
) -> AnalysisJob | None:
    return session.scalar(
        select(AnalysisJob)
        .join(ArtifactVersion, AnalysisJob.decision_version_id == ArtifactVersion.id)
        .where(
            ArtifactVersion.artifact_id == decision_id,
            AnalysisJob.mode == AnalysisMode.CURRENT,
            AnalysisJob.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
        )
        .order_by(AnalysisJob.created_at.desc())
        .limit(1)
    )
