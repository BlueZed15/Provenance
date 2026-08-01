from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from backend.app.contracts.normalization import (
    assert_strict_json,
    content_hash,
    json_safe,
    normalize_identifier,
    normalize_text,
    parse_timestamp,
)
from backend.app.domain.enums import AgentRole, Layer, SourceTool


class ArtifactIngestRecord(BaseModel):
    """Canonical boundary object shared by connector, Mistral, and persistence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_instance: str
    source_tool: SourceTool
    external_id: str
    layer: Layer
    text: str
    author_role: AgentRole
    source_created_at: datetime
    source_updated_at: datetime | None = None
    external_url: str | None = None
    external_links: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_instance", "external_id", mode="before")
    @classmethod
    def normalize_ids(cls, value: Any, info: ValidationInfo) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{info.field_name} must be a string")
        return normalize_identifier(value, field=info.field_name)

    @field_validator("text", mode="before")
    @classmethod
    def normalize_body(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise TypeError("text must be a string")
        normalized = normalize_text(value)
        if not normalized:
            raise ValueError("text must not be blank")
        return normalized

    @field_validator("source_created_at", "source_updated_at", mode="before")
    @classmethod
    def normalize_timestamps(cls, value: Any) -> datetime | None:
        return None if value is None else parse_timestamp(value)

    @field_validator("external_links", mode="before")
    @classmethod
    def normalize_links(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, (list, tuple)):
            raise TypeError("external_links must be a list")
        unique: list[str] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, str):
                raise TypeError("each external link must be a string")
            link = normalize_identifier(item, field="external_link", max_length=2048)
            if link not in seen:
                seen.add(link)
                unique.append(link)
        return unique

    @field_validator("external_url", mode="before")
    @classmethod
    def normalize_url(cls, value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError("external_url must be a string")
        return normalize_identifier(value, field="external_url", max_length=2048)

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_metadata(cls, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        normalized = json_safe(value)
        if not isinstance(normalized, dict):
            raise TypeError("metadata must be an object")
        assert_strict_json(normalized)
        return normalized

    @property
    def sha256(self) -> str:
        return content_hash(self.text)
