from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.domain.enums import JobStatus, Layer, Verdict
from backend.app.models import (
    AnalysisJob,
    Artifact,
    ArtifactVersion,
    Claim,
    ClaimTransform,
    DecisionReport,
    ProvenanceEdge,
)
from backend.app.schemas.api import (
    ClaimResponse,
    DecisionReportResponse,
    ReportComparisonResponse,
    ReportEdgeResponse,
    ReportTransformResponse,
    SourceQuoteResponse,
)


HEADLINES = {
    Verdict.ALIGNED: "Evidence preserved",
    Verdict.DRIFT: "Important evidence changed across the decision chain",
    Verdict.NO_EVIDENCE: "No linked evidence found",
    Verdict.UNRESOLVED: "Multiple plausible evidence chains remain",
}

ACTIONS = {
    Verdict.ALIGNED: [],
    Verdict.DRIFT: ["ADD_DETAIL", "STRATEGIC_OVERRIDE"],
    Verdict.NO_EVIDENCE: ["LINK_EVIDENCE", "STRATEGIC_OVERRIDE", "CONFIRM_INTENTIONAL"],
    Verdict.UNRESOLVED: ["CONFIRM_EDGE", "REJECT_EDGE"],
}


def get_decision_report(
    session: Session,
    decision_id: uuid.UUID,
) -> DecisionReportResponse | None:
    report = session.scalar(
        select(DecisionReport)
        .join(ArtifactVersion, DecisionReport.decision_version_id == ArtifactVersion.id)
        .where(ArtifactVersion.artifact_id == decision_id)
        .order_by(DecisionReport.generated_at.desc())
        .limit(1)
    )
    if report is None:
        return None

    report_job = session.get(AnalysisJob, report.analysis_job_id)
    if report_job is None:
        raise LookupError("Report analysis job no longer exists")

    active_job = session.scalar(
        select(AnalysisJob)
        .join(ArtifactVersion, AnalysisJob.decision_version_id == ArtifactVersion.id)
        .where(
            ArtifactVersion.artifact_id == decision_id,
            AnalysisJob.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
        )
        .order_by(AnalysisJob.created_at.desc())
        .limit(1)
    )

    edges = list(
        session.scalars(
            select(ProvenanceEdge)
            .where(ProvenanceEdge.analysis_job_id == report.analysis_job_id)
            .order_by(ProvenanceEdge.created_at)
        )
    )
    transforms = list(
        session.scalars(
            select(ClaimTransform)
            .where(ClaimTransform.analysis_job_id == report.analysis_job_id)
            .order_by(ClaimTransform.created_at)
        )
    )

    previous_report = session.scalar(
        select(DecisionReport)
        .join(ArtifactVersion, DecisionReport.decision_version_id == ArtifactVersion.id)
        .where(
            ArtifactVersion.artifact_id == decision_id,
            DecisionReport.id != report.id,
        )
        .order_by(DecisionReport.generated_at.desc())
        .limit(1)
    )
    comparison = None
    if previous_report is not None:
        previous_edges = list(
            session.scalars(
                select(ProvenanceEdge).where(
                    ProvenanceEdge.analysis_job_id == previous_report.analysis_job_id
                )
            )
        )
        previous_transforms = list(
            session.scalars(
                select(ClaimTransform).where(
                    ClaimTransform.analysis_job_id == previous_report.analysis_job_id
                )
            )
        )
        current_edge_signatures = {
            (edge.from_version_id, edge.to_version_id, edge.status, edge.confidence)
            for edge in edges
        }
        previous_edge_signatures = {
            (edge.from_version_id, edge.to_version_id, edge.status, edge.confidence)
            for edge in previous_edges
        }
        current_types = {transform.transform_type for transform in transforms}
        previous_types = {
            transform.transform_type for transform in previous_transforms
        }
        comparison = ReportComparisonResponse(
            previous_report_id=previous_report.id,
            previous_verdict=previous_report.verdict,
            verdict_changed=previous_report.verdict != report.verdict,
            changed_edges=len(current_edge_signatures ^ previous_edge_signatures),
            added_transform_types=sorted(
                current_types - previous_types,
                key=lambda item: item.value,
            ),
            removed_transform_types=sorted(
                previous_types - current_types,
                key=lambda item: item.value,
            ),
        )

    if report.is_stale:
        verification_status = "VERIFYING" if active_job is not None else "STALE"
    else:
        verification_status = "CURRENT"

    upstream_version_ids = {edge.to_version_id for edge in edges}
    quote_rows = []
    if upstream_version_ids:
        quote_rows = session.execute(
            select(Claim, Artifact)
            .join(ArtifactVersion, Claim.version_id == ArtifactVersion.id)
            .join(Artifact, ArtifactVersion.artifact_id == Artifact.id)
            .where(
                Claim.version_id.in_(upstream_version_ids),
                Artifact.layer == Layer.RAW_TICKET,
            )
            .order_by(Artifact.external_id, Claim.claim_index)
        ).all()

    return DecisionReportResponse(
        decision_id=decision_id,
        decision_version_id=report.decision_version_id,
        report_id=report.id,
        analysis_mode=report_job.mode,
        verdict=report.verdict,
        verification_status=verification_status,
        is_stale=report.is_stale,
        stale_at=report.stale_at,
        stale_reason=report.stale_reason,
        changed_version_id=report.changed_version_id,
        active_job_id=active_job.id if active_job else None,
        comparison=comparison,
        headline=HEADLINES[report.verdict],
        edges=[
            ReportEdgeResponse(
                id=edge.id,
                from_version_id=edge.from_version_id,
                to_version_id=edge.to_version_id,
                status=edge.status,
                confidence=edge.confidence,
                evidence_types=edge.evidence_types,
                alternatives=edge.alternatives,
            )
            for edge in edges
        ],
        transforms=[
            ReportTransformResponse(
                id=transform.id,
                edge_id=transform.edge_id,
                upstream_claim_id=transform.upstream_claim_id,
                downstream_claim_id=transform.downstream_claim_id,
                transform_type=transform.transform_type,
                retained_slots=transform.retained_slots,
                lost_slots=transform.lost_slots,
                introduced_slots=transform.introduced_slots,
                rationale=transform.rationale,
                is_critical=transform.is_critical,
            )
            for transform in transforms
        ],
        scores=report.scores,
        max_drift_transform_id=report.max_drift_transform_id,
        source_quotes=[
            SourceQuoteResponse(
                **_claim_fields(claim),
                artifact_external_id=artifact.external_id,
                external_url=artifact.external_url,
            )
            for claim, artifact in quote_rows
        ],
        allowed_actions=ACTIONS[report.verdict],
        generated_at=report.generated_at,
    )


def _claim_fields(claim: Claim) -> dict[str, object]:
    return ClaimResponse(
        id=claim.id,
        display_id=claim.display_id,
        version_id=claim.version_id,
        source_span=claim.source_span,
        span_start=claim.span_start,
        span_end=claim.span_end,
        claim_type=claim.claim_type,
        subject=claim.subject,
        predicate=claim.predicate,
        object=claim.object,
        qualifiers=claim.qualifiers,
    ).model_dump()
