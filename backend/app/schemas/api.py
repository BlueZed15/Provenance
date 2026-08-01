from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from backend.app.contracts import ArtifactIngestRecord
from backend.app.domain.enums import (
    AgentRole,
    AnalysisMode,
    AnalysisStage,
    ClaimType,
    Confidence,
    EdgeStatus,
    JobStatus,
    Layer,
    SourceTool,
    TransformType,
    Verdict,
)


class IngestItem(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(validation_alias=AliasChoices("id", "external_id"))
    source_instance: str = "local"
    layer: Layer
    tool: SourceTool = Field(validation_alias=AliasChoices("tool", "source_tool"))
    text: str
    author_role: AgentRole
    created_at: datetime = Field(
        validation_alias=AliasChoices("created_at", "source_created_at")
    )
    updated_at: datetime | None = Field(
        default=None,
        validation_alias=AliasChoices("updated_at", "source_updated_at"),
    )
    external_url: str | None = None
    links: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("links", "external_links"),
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_record(self) -> ArtifactIngestRecord:
        return ArtifactIngestRecord(
            source_instance=self.source_instance,
            source_tool=self.tool,
            external_id=self.id,
            layer=self.layer,
            text=self.text,
            author_role=self.author_role,
            source_created_at=self.created_at,
            source_updated_at=self.updated_at,
            external_url=self.external_url,
            external_links=self.links,
            metadata=self.metadata,
        )


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[IngestItem] = Field(min_length=1, max_length=500)


class IngestResponse(BaseModel):
    versions_ingested: int
    versions_reused: int
    counts_by_layer: dict[Layer, int]
    hash_conflicts: list[str] = Field(default_factory=list)
    stale_reports: int = 0
    reverification_jobs: list[uuid.UUID] = Field(default_factory=list)


class AtlassianSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jsm_project_key: str
    roadmap_project_key: str
    confluence_space_key: str
    roadmap_issue_type: Literal["Epic", "Idea"] = "Epic"


class AtlassianSyncResponse(IngestResponse):
    accessible_resource_count: int
    source_instance: str
    skipped_blank_items: int = 0


class DecisionSummary(BaseModel):
    id: uuid.UUID
    version_id: uuid.UUID
    external_id: str
    title: str
    source_tool: SourceTool
    source_instance: str
    external_url: str | None
    updated_at: datetime
    latest_verdict: Verdict | None = None


class DecisionListResponse(BaseModel):
    decisions: list[DecisionSummary]


class AnalysisStartResponse(BaseModel):
    job_id: uuid.UUID
    status: JobStatus


class JobResponse(BaseModel):
    job_id: uuid.UUID
    decision_version_id: uuid.UUID
    status: JobStatus
    mode: AnalysisMode
    stage: AnalysisStage
    progress: int
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ArtifactVersionResponse(BaseModel):
    id: uuid.UUID
    artifact_id: uuid.UUID
    external_id: str
    source_instance: str
    source_tool: SourceTool
    layer: Layer
    version_number: int
    text: str
    content_hash: str
    author_role: AgentRole
    source_created_at: datetime
    source_updated_at: datetime | None
    external_url: str | None
    external_links: list[str]
    metadata: dict[str, Any]


class ClaimResponse(BaseModel):
    id: uuid.UUID
    display_id: str
    version_id: uuid.UUID
    source_span: str
    span_start: int
    span_end: int
    claim_type: ClaimType
    subject: str
    predicate: str
    object: str
    qualifiers: dict[str, Any]


class ClaimsResponse(BaseModel):
    claims: list[ClaimResponse]


class ReportEdgeResponse(BaseModel):
    id: uuid.UUID
    from_version_id: uuid.UUID
    to_version_id: uuid.UUID
    status: EdgeStatus
    confidence: Confidence
    evidence_types: list[str]
    alternatives: list[str]


class ReportTransformResponse(BaseModel):
    id: uuid.UUID
    edge_id: uuid.UUID
    upstream_claim_id: uuid.UUID | None
    downstream_claim_id: uuid.UUID | None
    transform_type: TransformType
    retained_slots: list[str]
    lost_slots: list[str]
    introduced_slots: list[str]
    rationale: str
    is_critical: bool


class SourceQuoteResponse(ClaimResponse):
    artifact_external_id: str
    external_url: str | None


class ReportComparisonResponse(BaseModel):
    previous_report_id: uuid.UUID
    previous_verdict: Verdict
    verdict_changed: bool
    changed_edges: int
    added_transform_types: list[TransformType]
    removed_transform_types: list[TransformType]


class ReverifyResponse(BaseModel):
    decision_id: uuid.UUID
    previous_report_id: uuid.UUID
    previous_verdict: Verdict
    job_id: uuid.UUID
    status: JobStatus


class DecisionReportResponse(BaseModel):
    decision_id: uuid.UUID
    decision_version_id: uuid.UUID
    report_id: uuid.UUID
    analysis_mode: AnalysisMode
    verdict: Verdict
    verification_status: Literal["CURRENT", "STALE", "VERIFYING"]
    is_stale: bool
    stale_at: datetime | None
    stale_reason: str | None
    changed_version_id: uuid.UUID | None
    active_job_id: uuid.UUID | None
    comparison: ReportComparisonResponse | None
    headline: str
    edges: list[ReportEdgeResponse]
    transforms: list[ReportTransformResponse]
    scores: dict[str, Any]
    max_drift_transform_id: uuid.UUID | None
    source_quotes: list[SourceQuoteResponse]
    allowed_actions: list[str]
    generated_at: datetime


class JiraProvenanceResponse(BaseModel):
    issue_key: str
    decision_id: uuid.UUID
    analysis_required: bool
    active_job_id: uuid.UUID | None = None
    report: DecisionReportResponse | None = None
