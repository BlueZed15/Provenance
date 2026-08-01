import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text as sql_text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.domain.enums import (
    AnalysisMode,
    AnalysisStage,
    Confidence,
    EdgeStatus,
    JobStatus,
    TransformType,
)


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    __table_args__ = (Index("ix_analysis_jobs_decision_created", "decision_version_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    decision_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifact_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", native_enum=False),
        nullable=False,
        default=JobStatus.QUEUED,
    )
    stage: Mapped[AnalysisStage] = mapped_column(
        Enum(AnalysisStage, name="analysis_stage", native_enum=False),
        nullable=False,
        default=AnalysisStage.QUEUED,
    )
    mode: Mapped[AnalysisMode] = mapped_column(
        Enum(AnalysisMode, name="analysis_mode", native_enum=False),
        nullable=False,
        default=AnalysisMode.HISTORICAL,
        server_default=sql_text("'HISTORICAL'"),
    )
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProvenanceEdge(Base):
    __tablename__ = "provenance_edges"
    __table_args__ = (
        UniqueConstraint(
            "analysis_job_id",
            "from_version_id",
            "to_version_id",
            name="analysis_edge",
        ),
        CheckConstraint("from_version_id <> to_version_id", name="different_versions"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    analysis_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifact_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    to_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifact_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[EdgeStatus] = mapped_column(
        Enum(EdgeStatus, name="edge_status", native_enum=False), nullable=False
    )
    confidence: Mapped[Confidence] = mapped_column(
        Enum(Confidence, name="edge_confidence", native_enum=False), nullable=False
    )
    evidence_types: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=sql_text("'[]'::jsonb")
    )
    internal_score: Mapped[float] = mapped_column(Float, nullable=False)
    alternatives: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=sql_text("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ClaimTransform(Base):
    __tablename__ = "claim_transforms"
    __table_args__ = (
        CheckConstraint(
            "upstream_claim_id is not null or downstream_claim_id is not null",
            name="at_least_one_claim",
        ),
        Index("ix_claim_transforms_analysis_type", "analysis_job_id", "transform_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    analysis_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    edge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("provenance_edges.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    upstream_claim_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE")
    )
    downstream_claim_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE")
    )
    transform_type: Mapped[TransformType] = mapped_column(
        Enum(TransformType, name="transform_type", native_enum=False), nullable=False
    )
    retained_slots: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=sql_text("'[]'::jsonb")
    )
    lost_slots: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=sql_text("'[]'::jsonb")
    )
    introduced_slots: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=sql_text("'[]'::jsonb")
    )
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    is_critical: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sql_text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
