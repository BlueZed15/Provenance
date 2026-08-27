from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.app.contracts import ArtifactIngestRecord
from backend.app.domain.enums import Layer
from backend.app.repositories import ArtifactRepository, PersistedVersion


@dataclass(frozen=True)
class IngestionResult:
    versions_ingested: int
    versions_reused: int
    counts_by_layer: dict[Layer, int]
    versions: list[PersistedVersion] = field(default_factory=list)
    hash_conflicts: list[str] = field(default_factory=list)


def ingest_records(
    session: Session,
    records: list[ArtifactIngestRecord],
) -> IngestionResult:
    """Persist a batch atomically, creating immutable versions only on change."""
    repository = ArtifactRepository(session)
    persisted = [repository.upsert_record(record) for record in records]
    session.commit()

    counts = Counter(record.layer for record in records)
    return IngestionResult(
        versions_ingested=sum(item.created for item in persisted),
        versions_reused=sum(not item.created for item in persisted),
        counts_by_layer=dict(counts),
        versions=persisted,
    )
