from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.contracts import ArtifactIngestRecord
from backend.app.domain.enums import Layer
from backend.app.models import Artifact, ArtifactVersion, Claim


@dataclass(frozen=True)
class PersistedVersion:
    artifact_id: uuid.UUID
    version_id: uuid.UUID
    layer: Layer
    created: bool


class ArtifactRepository:
    """Small transaction-scoped repository for artifact ingestion and reads."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_record(self, record: ArtifactIngestRecord) -> PersistedVersion:
        artifact = self.session.scalar(
            select(Artifact).where(
                Artifact.source_instance == record.source_instance,
                Artifact.source_tool == record.source_tool,
                Artifact.external_id == record.external_id,
            )
        )
        if artifact is None:
            artifact = Artifact(
                source_instance=record.source_instance,
                source_tool=record.source_tool,
                external_id=record.external_id,
                layer=record.layer,
                external_url=record.external_url,
            )
            self.session.add(artifact)
            self.session.flush()
        else:
            artifact.layer = record.layer
            if record.external_url:
                artifact.external_url = record.external_url

        existing = self.session.scalar(
            select(ArtifactVersion).where(
                ArtifactVersion.artifact_id == artifact.id,
                ArtifactVersion.content_hash == record.sha256,
            )
        )
        if existing is not None:
            return PersistedVersion(
                artifact_id=artifact.id,
                version_id=existing.id,
                layer=artifact.layer,
                created=False,
            )

        latest_number = self.session.scalar(
            select(func.coalesce(func.max(ArtifactVersion.version_number), 0)).where(
                ArtifactVersion.artifact_id == artifact.id
            )
        )
        version = ArtifactVersion(
            artifact_id=artifact.id,
            version_number=int(latest_number or 0) + 1,
            text=record.text,
            content_hash=record.sha256,
            author_role=record.author_role,
            source_created_at=record.source_created_at,
            source_updated_at=record.source_updated_at,
            external_links=record.external_links,
            artifact_metadata=record.metadata,
        )
        self.session.add(version)
        self.session.flush()
        return PersistedVersion(
            artifact_id=artifact.id,
            version_id=version.id,
            layer=artifact.layer,
            created=True,
        )

    def latest_version(self, artifact_id: uuid.UUID) -> ArtifactVersion | None:
        return self.session.scalar(
            select(ArtifactVersion)
            .where(ArtifactVersion.artifact_id == artifact_id)
            .order_by(ArtifactVersion.version_number.desc())
            .limit(1)
        )

    def claims_for_version(self, version_id: uuid.UUID) -> list[Claim]:
        return list(
            self.session.scalars(
                select(Claim)
                .where(Claim.version_id == version_id)
                .order_by(Claim.claim_index)
            )
        )
