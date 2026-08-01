from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.enums import ClaimType, TransformType


class ClaimQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: str = "unstated"
    segment: str = "unstated"
    polarity: str = "neutral"
    quantity: str = "unstated"
    temporality: str = "unstated"


class ExtractedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_span: str
    claim_type: ClaimType
    subject: str
    predicate: str
    object: str
    qualifiers: ClaimQualifiers


class ClaimExtractionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[ExtractedClaim]


class AuditClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    claim_type: ClaimType
    source_span: str
    qualifiers: dict[str, Any] = Field(default_factory=dict)


class ClaimTransformResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upstream_claim_id: str | None
    downstream_claim_id: str | None
    transform_type: TransformType
    retained_slots: list[str] = Field(default_factory=list)
    lost_slots: list[str] = Field(default_factory=list)
    introduced_slots: list[str] = Field(default_factory=list)
    rationale: str


class TransformClassificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transforms: list[ClaimTransformResult]
