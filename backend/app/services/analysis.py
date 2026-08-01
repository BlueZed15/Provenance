from __future__ import annotations

import asyncio
import math
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

import numpy as np
from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.session import SessionLocal
from backend.app.domain.enums import (
    AnalysisMode,
    AnalysisStage,
    Confidence,
    EdgeStatus,
    JobStatus,
    Layer,
    TransformType,
    Verdict,
)
from backend.app.models import (
    AnalysisJob,
    Artifact,
    ArtifactVersion,
    Claim,
    ClaimTransform,
    DecisionReport,
    ProvenanceEdge,
)
from backend.app.schemas.mistral import AuditClaim
from backend.app.services.mistral import get_mistral_gateway


LAYER_ORDER = [Layer.ROADMAP, Layer.PRD, Layer.THEME_SUMMARY, Layer.RAW_TICKET]
DRIFT_TYPES = {
    TransformType.CRITICAL_DETAIL_OMITTED,
    TransformType.SEVERITY_DILUTED,
    TransformType.QUANTITY_CHANGED,
    TransformType.NEGATION_CHANGED,
    TransformType.PROBLEM_TO_SOLUTION_SUBSTITUTION,
    TransformType.CONTRADICTED,
    TransformType.UNSUPPORTED_ADDITION,
}
ALWAYS_CRITICAL = {
    TransformType.NEGATION_CHANGED,
    TransformType.QUANTITY_CHANGED,
    TransformType.CONTRADICTED,
}
_TOKEN = re.compile(r"[\w-]+", re.UNICODE)
_IDENTIFIER = re.compile(r"\b[A-Z][A-Z0-9_]{1,20}-\d+\b")


@dataclass(frozen=True)
class ScoredParent:
    version: ArtifactVersion
    score: float
    evidence_types: list[str]


def create_analysis_job(
    session: Session,
    decision_id: uuid.UUID,
    mode: AnalysisMode = AnalysisMode.HISTORICAL,
) -> AnalysisJob:
    artifact = session.get(Artifact, decision_id)
    if artifact is None or artifact.layer != Layer.ROADMAP:
        raise LookupError("Roadmap decision not found")

    active = session.scalar(
        select(AnalysisJob)
        .join(ArtifactVersion, AnalysisJob.decision_version_id == ArtifactVersion.id)
        .where(
            ArtifactVersion.artifact_id == decision_id,
            AnalysisJob.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
            AnalysisJob.mode == mode,
        )
        .order_by(AnalysisJob.created_at.desc())
        .limit(1)
    )
    if active is not None:
        return active

    decision_version = session.scalar(
        select(ArtifactVersion)
        .where(ArtifactVersion.artifact_id == decision_id)
        .order_by(ArtifactVersion.version_number.desc())
        .limit(1)
    )
    if decision_version is None:
        raise LookupError("Roadmap decision has no ingested version")
    job = AnalysisJob(decision_version_id=decision_version.id, mode=mode)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


async def run_analysis_job(job_id: uuid.UUID) -> None:
    with SessionLocal() as session:
        job = session.get(AnalysisJob, job_id)
        if job is None:
            return
        job.status = JobStatus.RUNNING
        job.stage = AnalysisStage.EXTRACTING_CLAIMS
        job.started_at = datetime.now().astimezone()
        session.commit()

        try:
            await _run_pipeline(session, job)
            job.status = JobStatus.COMPLETED
            job.stage = AnalysisStage.COMPLETED
            job.completed_at = datetime.now().astimezone()
            session.commit()
        except Exception as exc:
            session.rollback()
            job = session.get(AnalysisJob, job_id)
            if job is not None:
                job.status = JobStatus.FAILED
                job.stage = AnalysisStage.FAILED
                job.error_code = type(exc).__name__[:100]
                job.error_message = "Analysis failed; inspect server diagnostics."
                job.completed_at = datetime.now().astimezone()
                session.commit()


async def _run_pipeline(session: Session, job: AnalysisJob) -> None:
    decision = session.get(ArtifactVersion, job.decision_version_id)
    if decision is None:
        raise LookupError("Decision version no longer exists")

    versions, artifacts = _eligible_versions(session, decision, job.mode)
    await _ensure_claims(session, versions, artifacts)

    job.stage = AnalysisStage.GENERATING_EMBEDDINGS
    session.commit()
    await _ensure_embeddings(session, versions)

    job.stage = AnalysisStage.RETRIEVING_EVIDENCE
    session.commit()
    edges = _build_chain(decision, versions, artifacts, mode=job.mode)

    job.stage = AnalysisStage.CLASSIFYING_EDGES
    session.commit()
    persisted_edges: list[ProvenanceEdge] = []
    for scored in edges:
        edge = ProvenanceEdge(
            analysis_job_id=job.id,
            from_version_id=scored[0].id,
            to_version_id=scored[1].version.id,
            status=scored[2],
            confidence=scored[3],
            evidence_types=scored[1].evidence_types,
            internal_score=scored[1].score,
            alternatives=scored[4],
        )
        session.add(edge)
        persisted_edges.append(edge)
    session.flush()

    job.stage = AnalysisStage.CLASSIFYING_TRANSFORMS
    session.commit()
    transforms = await _classify_and_persist_transforms(session, job, persisted_edges)

    job.stage = AnalysisStage.ASSEMBLING_REPORT
    session.commit()
    scores = _integrity_scores(transforms, session)
    verdict = _verdict(persisted_edges, transforms)
    critical_drifts = [
        transform
        for transform in transforms
        if transform.is_critical and transform.transform_type in DRIFT_TYPES
    ]
    report = DecisionReport(
        analysis_job_id=job.id,
        decision_version_id=decision.id,
        verdict=verdict,
        scores=scores,
        max_drift_transform_id=critical_drifts[0].id if critical_drifts else None,
    )
    session.add(report)
    session.commit()


def _eligible_versions(
    session: Session,
    decision: ArtifactVersion,
    mode: AnalysisMode = AnalysisMode.HISTORICAL,
) -> tuple[list[ArtifactVersion], dict[uuid.UUID, Artifact]]:
    rows = session.execute(
        select(ArtifactVersion, Artifact).join(
            Artifact, ArtifactVersion.artifact_id == Artifact.id
        )
    ).all()
    artifacts = {artifact.id: artifact for _, artifact in rows}
    by_artifact: dict[uuid.UUID, list[ArtifactVersion]] = defaultdict(list)
    decision_time = _effective_time(decision)
    for version, artifact in rows:
        if artifact.layer == Layer.ROADMAP and version.id != decision.id:
            continue
        if (
            mode == AnalysisMode.CURRENT
            or version.id == decision.id
            or _effective_time(version) <= decision_time
        ):
            by_artifact[artifact.id].append(version)

    selected: list[ArtifactVersion] = []
    for candidates in by_artifact.values():
        selected.append(max(candidates, key=lambda item: item.version_number))
    if all(version.id != decision.id for version in selected):
        selected.append(decision)
    return selected, artifacts


def _effective_time(version: ArtifactVersion) -> datetime:
    return version.source_updated_at or version.source_created_at


async def _ensure_claims(
    session: Session,
    versions: list[ArtifactVersion],
    artifacts: dict[uuid.UUID, Artifact],
) -> None:
    gateway = get_mistral_gateway()
    missing: list[ArtifactVersion] = []
    for version in versions:
        has_claim = session.scalar(
            select(Claim.id).where(Claim.version_id == version.id).limit(1)
        )
        if has_claim is None:
            missing.append(version)
    if not missing:
        return

    extracted_sets = await asyncio.gather(
        *(gateway.extract_claims(version.text) for version in missing)
    )
    for version, extracted in zip(missing, extracted_sets, strict=True):
        artifact = artifacts[version.artifact_id]
        span_cursors: dict[str, int] = defaultdict(int)
        claim_index = 0
        for item in extracted:
            subject = item.subject.strip()
            predicate = item.predicate.strip()
            object_value = item.object.strip()
            if not subject or not predicate or not object_value:
                continue
            start = version.text.find(item.source_span, span_cursors[item.source_span])
            if start < 0:
                start = version.text.find(item.source_span)
            if start < 0:
                continue
            span_cursors[item.source_span] = start + len(item.source_span)
            qualifiers = item.qualifiers.model_dump()
            for qualifier_name in ("severity", "segment"):
                extracted_value = str(qualifiers.get(qualifier_name, "unstated")).lower()
                metadata_value = version.artifact_metadata.get(qualifier_name)
                if extracted_value == "unstated" and metadata_value not in (None, ""):
                    qualifiers[qualifier_name] = metadata_value
            display_id = (
                f"{artifact.source_instance}:{artifact.external_id}:"
                f"v{version.version_number}#C{claim_index}"
            )
            session.add(
                Claim(
                    display_id=display_id[:400],
                    version_id=version.id,
                    claim_index=claim_index,
                    source_span=item.source_span,
                    span_start=start,
                    span_end=start + len(item.source_span),
                    claim_type=item.claim_type,
                    subject=subject,
                    predicate=predicate,
                    object=object_value,
                    qualifiers=qualifiers,
                )
            )
            claim_index += 1
    session.commit()


async def _ensure_embeddings(
    session: Session,
    versions: list[ArtifactVersion],
) -> None:
    missing = [
        version
        for version in versions
        if version.embedding is None or version.embedded_with != settings.mistral_embed_model
    ]
    if not missing:
        return
    embeddings = await get_mistral_gateway().embed_texts(
        [version.text for version in missing]
    )
    for version, embedding in zip(missing, embeddings, strict=True):
        version.embedding = embedding
        version.embedded_with = settings.mistral_embed_model
    session.commit()


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN.findall(text)]


def _cosine(left: list[float], right: list[float]) -> float:
    left_array = np.asarray(left, dtype=float)
    right_array = np.asarray(right, dtype=float)
    denominator = float(np.linalg.norm(left_array) * np.linalg.norm(right_array))
    return float(np.dot(left_array, right_array) / denominator) if denominator else 0.0


def _normalized(values: list[float]) -> list[float]:
    if not values:
        return []
    low, high = min(values), max(values)
    if math.isclose(low, high):
        return [1.0 if value > 0 else 0.0 for value in values]
    return [(value - low) / (high - low) for value in values]


def _shared_identifiers(left: str, right: str) -> set[str]:
    return set(_IDENTIFIER.findall(left.upper())) & set(_IDENTIFIER.findall(right.upper()))


def _explicitly_links(child: ArtifactVersion, parent: ArtifactVersion, artifact: Artifact) -> bool:
    parent_id = artifact.external_id.lower()
    parent_url = (artifact.external_url or "").lower()
    for raw_link in child.external_links:
        link = raw_link.lower()
        if link == parent_id or (parent_url and link == parent_url):
            return True
        if re.search(rf"(?<![a-z0-9_-]){re.escape(parent_id)}(?![a-z0-9_-])", link):
            return True
    return False


def _candidate_parents(
    child: ArtifactVersion,
    pool: list[ArtifactVersion],
    artifacts: dict[uuid.UUID, Artifact],
    k: int = 5,
    enforce_temporal: bool = True,
) -> list[ScoredParent]:
    if enforce_temporal:
        pool = [item for item in pool if _effective_time(item) <= _effective_time(child)]
    if not pool:
        return []
    bm25 = BM25Okapi([_tokenize(item.text) for item in pool])
    lexical = _normalized([float(value) for value in bm25.get_scores(_tokenize(child.text))])
    semantic = [
        _cosine(list(child.embedding), list(parent.embedding))
        if child.embedding is not None and parent.embedding is not None
        else 0.0
        for parent in pool
    ]

    scored: list[ScoredParent] = []
    child_reference_text = child.text + " " + " ".join(child.external_links)
    for index, parent in enumerate(pool):
        evidence: list[str] = []
        score = 0.0
        if _explicitly_links(child, parent, artifacts[parent.artifact_id]):
            evidence.append("explicit_link")
            score += 10.0
        identifiers = _shared_identifiers(child_reference_text, parent.text)
        if identifiers:
            evidence.append("id_overlap")
            score += 2.0 * len(identifiers)
        if lexical[index] > 0:
            evidence.append("bm25")
            score += 0.5 * lexical[index]
        if semantic[index] > 0.5:
            evidence.append("embedding")
            score += semantic[index]
        evidence.append(
            "temporal_ok"
            if _effective_time(parent) <= _effective_time(child)
            else "post_decision_update"
        )
        scored.append(ScoredParent(parent, score, evidence))
    return sorted(scored, key=lambda item: item.score, reverse=True)[:k]


def _edge_type(candidates: list[ScoredParent]) -> tuple[EdgeStatus, Confidence]:
    best = candidates[0]
    runner_up = candidates[1].score if len(candidates) > 1 else 0.0
    margin = best.score - runner_up
    if "explicit_link" in best.evidence_types:
        return EdgeStatus.OBSERVED, Confidence.OBSERVED
    if "id_overlap" in best.evidence_types and margin > 1.0:
        return EdgeStatus.INFERRED, Confidence.STRONG_INFERENCE
    if margin > 0.8:
        return EdgeStatus.INFERRED, Confidence.STRONG_INFERENCE
    if margin > 0.25:
        return EdgeStatus.INFERRED, Confidence.WEAK_INFERENCE
    return EdgeStatus.INFERRED, Confidence.UNRESOLVED


def _build_chain(
    decision: ArtifactVersion,
    versions: list[ArtifactVersion],
    artifacts: dict[uuid.UUID, Artifact],
    max_hops: int = 4,
    mode: AnalysisMode = AnalysisMode.HISTORICAL,
) -> list[tuple[ArtifactVersion, ScoredParent, EdgeStatus, Confidence, list[str]]]:
    results = []
    current = decision
    start = LAYER_ORDER.index(artifacts[current.artifact_id].layer)
    for target_layer in LAYER_ORDER[start + 1 :]:
        if len(results) >= max_hops:
            break
        pool = [
            version
            for version in versions
            if artifacts[version.artifact_id].layer == target_layer
        ]
        if not pool:
            continue
        candidates = _candidate_parents(
            current,
            pool,
            artifacts,
            enforce_temporal=mode == AnalysisMode.HISTORICAL,
        )
        if not candidates:
            break
        status, confidence = _edge_type(candidates)
        results.append(
            (
                current,
                candidates[0],
                status,
                confidence,
                [str(candidate.version.id) for candidate in candidates[1:3]],
            )
        )
        if confidence == Confidence.UNRESOLVED:
            break
        current = candidates[0].version
    return results


async def _classify_and_persist_transforms(
    session: Session,
    job: AnalysisJob,
    edges: list[ProvenanceEdge],
) -> list[ClaimTransform]:
    gateway = get_mistral_gateway()
    persisted: list[ClaimTransform] = []
    for edge in edges:
        upstream = list(
            session.scalars(
                select(Claim).where(Claim.version_id == edge.to_version_id).order_by(Claim.claim_index)
            )
        )
        downstream = list(
            session.scalars(
                select(Claim).where(Claim.version_id == edge.from_version_id).order_by(Claim.claim_index)
            )
        )
        classified = await gateway.classify_transforms(
            [_audit_claim(claim) for claim in upstream],
            [_audit_claim(claim) for claim in downstream],
        )
        claims_by_display = {claim.display_id: claim for claim in upstream + downstream}
        for result in classified.transforms:
            upstream_claim = claims_by_display.get(result.upstream_claim_id or "")
            downstream_claim = claims_by_display.get(result.downstream_claim_id or "")
            transform = ClaimTransform(
                analysis_job_id=job.id,
                edge_id=edge.id,
                upstream_claim_id=upstream_claim.id if upstream_claim else None,
                downstream_claim_id=downstream_claim.id if downstream_claim else None,
                transform_type=result.transform_type,
                retained_slots=result.retained_slots,
                lost_slots=result.lost_slots,
                introduced_slots=result.introduced_slots,
                rationale=result.rationale.strip(),
                is_critical=_is_critical(result.transform_type, upstream_claim),
            )
            session.add(transform)
            persisted.append(transform)
        session.flush()
    session.commit()
    return persisted


def _audit_claim(claim: Claim) -> AuditClaim:
    return AuditClaim(
        id=claim.display_id,
        claim_type=claim.claim_type,
        source_span=claim.source_span,
        qualifiers=claim.qualifiers,
    )


def _is_critical(transform_type: TransformType, upstream: Claim | None) -> bool:
    if transform_type in ALWAYS_CRITICAL:
        return True
    if transform_type not in DRIFT_TYPES:
        return False
    if upstream is None:
        return transform_type == TransformType.UNSUPPORTED_ADDITION
    severity = str(upstream.qualifiers.get("severity", "unstated")).lower()
    segment = str(upstream.qualifiers.get("segment", "unstated")).lower()
    return severity == "high" or segment == "enterprise"


def _integrity_scores(transforms: list[ClaimTransform], session: Session) -> dict[str, object]:
    downstream = [item for item in transforms if item.downstream_claim_id]
    preserved_types = {
        TransformType.PRESERVED,
        TransformType.LEGITIMATE_GENERALIZATION,
    }
    grounded = [item for item in downstream if item.transform_type in preserved_types]
    groundedness = len(grounded) / max(len(downstream), 1)

    upstream_ids = {item.upstream_claim_id for item in transforms if item.upstream_claim_id}
    upstream_claims = list(
        session.scalars(select(Claim).where(Claim.id.in_(upstream_ids)))
    ) if upstream_ids else []
    survived = {
        item.upstream_claim_id
        for item in transforms
        if item.transform_type in preserved_types and item.upstream_claim_id
    }

    def weight(claim: Claim) -> float:
        severity_weights = {"high": 3.0, "medium": 1.5, "low": 0.5, "unstated": 1.0}
        severity = severity_weights.get(
            str(claim.qualifiers.get("severity", "unstated")).lower(), 1.0
        )
        segment = 2.0 if str(claim.qualifiers.get("segment", "")).lower() == "enterprise" else 1.0
        return severity * segment

    numerator = sum(weight(claim) for claim in upstream_claims if claim.id in survived)
    denominator = sum(weight(claim) for claim in upstream_claims)
    preservation = numerator / max(denominator, 1e-9)
    return {
        "groundedness": round(groundedness, 2),
        "critical_claim_preservation": round(preservation, 2),
        "action_alignment": not any(
            item.transform_type == TransformType.PROBLEM_TO_SOLUTION_SUBSTITUTION
            for item in transforms
        ),
        "weighting_policy": "High severity 3x; medium 1.5x; low 0.5x; enterprise segment 2x.",
    }


def _verdict(edges: list[ProvenanceEdge], transforms: list[ClaimTransform]) -> Verdict:
    substantive = {"explicit_link", "id_overlap", "bm25", "embedding"}
    if not edges or all(
        edge.confidence == Confidence.UNRESOLVED
        and not (set(edge.evidence_types) & substantive)
        for edge in edges
    ):
        return Verdict.NO_EVIDENCE
    if any(
        transform.is_critical and transform.transform_type in DRIFT_TYPES
        for transform in transforms
    ):
        return Verdict.DRIFT
    if any(edge.confidence == Confidence.UNRESOLVED for edge in edges) or not transforms:
        return Verdict.UNRESOLVED
    return Verdict.ALIGNED
