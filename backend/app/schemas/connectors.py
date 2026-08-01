from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ConnectorTool(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("inputSchema", "input_schema"),
    )
    annotations: dict[str, Any] = Field(default_factory=dict)


class ConnectorToolResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    content: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] | None = None

    def text_blocks(self) -> list[str]:
        return [
            str(block["text"])
            for block in self.content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        ]
