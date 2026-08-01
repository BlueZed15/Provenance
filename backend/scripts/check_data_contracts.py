"""Exercise source -> Mistral contract -> Postgres types without retaining rows."""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select

from backend.app.contracts import ArtifactIngestRecord, validate_embedding
from backend.app.db.session import SessionLocal
from backend.app.domain.enums import AgentRole, ClaimType, Layer, SourceTool
from backend.app.models.artifacts import Artifact, ArtifactVersion, Claim


def main() -> None:
    raw_text = (
        "Cafe\u0301 customer \U0001f469\u200d\U0001f4bb says: “login fails”\x00\r\n"
        "Severity:\tcritical\x07 — account №42."
    )
    record = ArtifactIngestRecord(
        source_instance=" compatibility-check ",
        source_tool=SourceTool.JSM,
        external_id=" TEST-\u212a-42 ",
        layer=Layer.RAW_TICKET,
        text=raw_text,
        author_role=AgentRole.CUSTOMER,
        source_created_at="2026-08-01T01:02:03Z",
        source_updated_at=datetime(2026, 8, 1, 1, 3, 4),
        external_links=[
            "https://example.test/browse/TEST-42",
            "https://example.test/browse/TEST-42",
        ],
        metadata={
            "unicode": "naïve / 東京 / \U0001f680",
            "number": Decimal("12.50"),
            "not_a_number": math.nan,
            "binary": b"valid utf8 \xf0\x9f\x98\x80 invalid \xff",
            "identifier": uuid.uuid4(),
            "nested": [True, None, {"at": datetime(2026, 8, 1, 2, 0)}],
        },
    )
    embedding = validate_embedding([0.0] * 1024)

    try:
        validate_embedding([0.0] * 1023)
    except ValueError:
        pass
    else:
        raise AssertionError("a vector with the wrong dimension was accepted")
    try:
        validate_embedding([0.0] * 1023 + [math.inf])
    except ValueError:
        pass
    else:
        raise AssertionError("a vector containing infinity was accepted")

    assert "\x00" not in record.text
    assert "\x07" not in record.text
    assert "Café" in record.text
    assert "\U0001f469\u200d\U0001f4bb" in record.text
    assert record.source_created_at.utcoffset().total_seconds() == 0
    assert len(record.external_links) == 1
    assert len(record.sha256) == 64
    json.dumps(record.metadata, ensure_ascii=False, allow_nan=False)

    with SessionLocal() as session:
        before = session.scalar(select(func.count()).select_from(Artifact))
        try:
            artifact = Artifact(
                source_instance=record.source_instance,
                source_tool=record.source_tool,
                external_id=f"{record.external_id}-{uuid.uuid4()}",
                layer=record.layer,
                external_url=record.external_links[0],
            )
            session.add(artifact)
            session.flush()

            version = ArtifactVersion(
                artifact_id=artifact.id,
                version_number=1,
                text=record.text,
                content_hash=record.sha256,
                author_role=record.author_role,
                source_created_at=record.source_created_at,
                source_updated_at=record.source_updated_at,
                external_links=record.external_links,
                artifact_metadata=record.metadata,
                embedding=embedding,
                embedded_with="mistral-embed",
            )
            session.add(version)
            session.flush()

            source_span = "login fails"
            span_start = record.text.index(source_span)
            claim = Claim(
                display_id=f"contract-check-{uuid.uuid4()}",
                version_id=version.id,
                claim_index=0,
                source_span=source_span,
                span_start=span_start,
                span_end=span_start + len(source_span),
                claim_type=ClaimType.PROBLEM,
                subject="customer \U0001f469\u200d\U0001f4bb",
                predicate="cannot authenticate",
                object="account №42",
                qualifiers={"severity": "critical", "locale": "東京"},
            )
            session.add(claim)
            session.flush()

            assert session.get(ArtifactVersion, version.id) is not None
            print("source_contract=ok")
            print("strict_jsonb=ok")
            print("unicode_and_emoji=ok")
            print("timestamp_utc=ok")
            print("embedding_vector_1024=ok")
            print("invalid_embeddings_rejected=ok")
            print("postgres_round_trip=ok")
        finally:
            # The compatibility row is deliberately never committed.
            session.rollback()

    with SessionLocal() as session:
        after = session.scalar(select(func.count()).select_from(Artifact))
    if after != before:
        raise RuntimeError("compatibility diagnostic unexpectedly changed stored data")
    print("rollback_no_persistence=ok")


if __name__ == "__main__":
    main()
