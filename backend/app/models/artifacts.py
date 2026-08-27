import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text as sql_text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.domain.enums import AgentRole, ClaimType, Layer, SourceTool


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        UniqueConstraint(
            "source_instance",
            "source_tool",
            "external_id",
            name="source_identity",
        ),
        Index("ix_artifacts_layer", "layer"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_instance: Mapped[str] = mapped_column(
        String(255), nullable=False, default="local"
    )
    source_tool: Mapped[SourceTool] = mapped_column(
        Enum(SourceTool, name="source_tool", native_enum=False), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    layer: Mapped[Layer] = mapped_column(
        Enum(Layer, name="artifact_layer", native_enum=False), nullable=False
    )
    external_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ArtifactVersion(Base):
    __tablename__ = "artifact_versions"
    __table_args__ = (
        UniqueConstraint("artifact_id", "version_number", name="artifact_version"),
        UniqueConstraint("artifact_id", "content_hash", name="artifact_hash"),
        CheckConstraint("version_number > 0", name="positive_version_number"),
        CheckConstraint("char_length(content_hash) = 64", name="sha256_hash_length"),
        Index("ix_artifact_versions_source_updated_at", "source_updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    author_role: Mapped[AgentRole] = mapped_column(
        Enum(AgentRole, name="agent_role", native_enum=False), nullable=False
    )
    source_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_links: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=sql_text("'[]'::jsonb")
    )
    artifact_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=sql_text("'{}'::jsonb"),
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))
    embedded_with: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = (
        UniqueConstraint("version_id", "claim_index", name="version_claim_index"),
        UniqueConstraint("display_id", name="display_id"),
        CheckConstraint("claim_index >= 0", name="nonnegative_claim_index"),
        CheckConstraint("span_start >= 0", name="nonnegative_span_start"),
        CheckConstraint("span_end > span_start", name="valid_span_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    display_id: Mapped[str] = mapped_column(String(400), nullable=False)
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifact_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    claim_index: Mapped[int] = mapped_column(Integer, nullable=False)
    source_span: Mapped[str] = mapped_column(Text, nullable=False)
    span_start: Mapped[int] = mapped_column(Integer, nullable=False)
    span_end: Mapped[int] = mapped_column(Integer, nullable=False)
    claim_type: Mapped[ClaimType] = mapped_column(
        Enum(ClaimType, name="claim_type", native_enum=False), nullable=False
    )
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    predicate: Mapped[str] = mapped_column(Text, nullable=False)
    object: Mapped[str] = mapped_column(Text, nullable=False)
    qualifiers: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=sql_text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
