import json
from typing import Any

from backend.app.services.mistral.connectors import (
    ConnectorError,
    ConnectorToolResult,
    MistralConnectorClient,
)


class AtlassianConnectorAdapter:
    """Read-only Atlassian operations used by the provenance ingestion layer."""

    DEFAULT_JIRA_FIELDS = [
        "summary",
        "description",
        "status",
        "issuetype",
        "priority",
        "labels",
        "components",
        "assignee",
        "reporter",
        "created",
        "updated",
        "resolution",
        "project",
        "comment",
    ]

    def __init__(self, client: MistralConnectorClient | None = None) -> None:
        self._client = client or MistralConnectorClient()

    async def get_accessible_resources(self) -> list[dict[str, Any]]:
        payload = await self._call_json("getAccessibleAtlassianResources", {})
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("resources", "items", "data", "results"):
                items = payload.get(key)
                if isinstance(items, list):
                    return [item for item in items if isinstance(item, dict)]
        return []

    async def search_jira_issues(
        self,
        *,
        cloud_id: str,
        jql: str,
        max_results: int = 50,
        next_page_token: str | None = None,
        fields: list[str] | None = None,
    ) -> dict[str, Any] | list[Any]:
        arguments: dict[str, Any] = {
            "cloudId": cloud_id,
            "jql": jql,
            "maxResults": min(max(max_results, 1), 100),
            "fields": fields or self.DEFAULT_JIRA_FIELDS,
            "responseContentFormat": "adf",
            "searchResultMode": "issues",
        }
        if next_page_token:
            arguments["nextPageToken"] = next_page_token
        return await self._call_json("searchJiraIssuesUsingJql", arguments)

    async def get_jira_issue(
        self,
        *,
        cloud_id: str,
        issue_id_or_key: str,
        fields: list[str] | None = None,
    ) -> dict[str, Any] | list[Any]:
        return await self._call_json(
            "getJiraIssue",
            {
                "cloudId": cloud_id,
                "issueIdOrKey": issue_id_or_key,
                "fields": fields or self.DEFAULT_JIRA_FIELDS,
                "responseContentFormat": "adf",
                "updateHistory": False,
            },
        )

    async def search_confluence_pages(
        self,
        *,
        cloud_id: str,
        cql: str,
        limit: int = 25,
        cursor: str | None = None,
    ) -> dict[str, Any] | list[Any]:
        arguments: dict[str, Any] = {
            "cloudId": cloud_id,
            "cql": cql,
            "limit": min(max(limit, 1), 250),
            "next": True,
        }
        if cursor:
            arguments["cursor"] = cursor
        return await self._call_json("searchConfluenceUsingCql", arguments)

    async def get_confluence_page(
        self,
        *,
        cloud_id: str,
        page_id: str,
    ) -> dict[str, Any] | list[Any]:
        return await self._call_json(
            "getConfluencePage",
            {
                "cloudId": cloud_id,
                "pageId": page_id,
                "contentFormat": "html",
                "contentType": "page",
            },
        )

    async def _call_json(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any] | list[Any]:
        result = await self._client.call_tool(tool_name, arguments)
        documents = self._decode_documents(result)
        if not documents:
            raise ConnectorError(
                f"Atlassian tool {tool_name} returned no JSON document."
            )
        if any(
            isinstance(document, dict) and document.get("error") is True
            for document in documents
        ):
            raise ConnectorError(f"Atlassian tool {tool_name} reported an error.")
        if len(documents) == 1:
            return documents[0]
        return documents

    @staticmethod
    def _decode_documents(result: ConnectorToolResult) -> list[Any]:
        documents: list[Any] = []
        for block in result.content:
            candidate: Any = None
            if isinstance(block.get("text"), str):
                candidate = block["text"]
            elif isinstance(block.get("resource"), dict):
                resource = block["resource"]
                candidate = resource.get("text")

            if not isinstance(candidate, str):
                continue
            stripped = candidate.strip()
            if stripped.startswith("```json") and stripped.endswith("```"):
                stripped = stripped[7:-3].strip()
            try:
                documents.append(json.loads(stripped))
            except json.JSONDecodeError:
                # Exact raw data is required for ingestion; prose summaries are
                # deliberately rejected instead of being treated as source truth.
                continue
        return documents
