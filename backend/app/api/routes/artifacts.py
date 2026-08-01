import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models import Artifact, ArtifactVersion
from backend.app.repositories import ArtifactRepository
from backend.app.schemas.api import (
    ArtifactVersionResponse,
    ClaimResponse,
    ClaimsResponse,
)


router = APIRouter()


@router.get(
    "/artifact-versions/{version_id}",
    response_model=ArtifactVersionResponse,
)
def get_artifact_version(
    version_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> ArtifactVersionResponse:
    version = session.get(ArtifactVersion, version_id)
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Artifact version not found")
    artifact = session.get(Artifact, version.artifact_id)
    if artifact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Artifact not found")
    return ArtifactVersionResponse(
        id=version.id,
        artifact_id=artifact.id,
        external_id=artifact.external_id,
        source_instance=artifact.source_instance,
        source_tool=artifact.source_tool,
        layer=artifact.layer,
        version_number=version.version_number,
        text=version.text,
        content_hash=version.content_hash,
        author_role=version.author_role,
        source_created_at=version.source_created_at,
        source_updated_at=version.source_updated_at,
        external_url=artifact.external_url,
        external_links=version.external_links,
        metadata=version.artifact_metadata,
    )


@router.get(
    "/artifact-versions/{version_id}/claims",
    response_model=ClaimsResponse,
)
def get_claims(
    version_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> ClaimsResponse:
    if session.get(ArtifactVersion, version_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Artifact version not found")
    claims = ArtifactRepository(session).claims_for_version(version_id)
    return ClaimsResponse(
        claims=[
            ClaimResponse(
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
            )
            for claim in claims
        ]
    )
