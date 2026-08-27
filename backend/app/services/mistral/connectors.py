from typing import Any
from urllib.parse import quote

import httpx

from backend.app.core.config import settings
from backend.app.schemas.connectors import ConnectorTool, ConnectorToolResult


class ConnectorError(RuntimeError):
    """A sanitized Mistral Connector API error."""


class MistralConnectorClient:
    """Direct Connector API client used until the Python SDK exposes Connectors."""

    def __init__(self, connector_id_or_name: str | None = None) -> None:
        connector_id = connector_id_or_name or settings.mistral_atlassian_connector_id
        if not connector_id or not connector_id.strip():
            raise ConnectorError("MISTRAL_ATLASSIAN_CONNECTOR_ID is not configured.")
        if not settings.has_mistral_key:
            raise ConnectorError("MISTRAL_API_KEY is not configured.")

        self.connector_id = connector_id.strip()
        self._base_url = settings.mistral_api_base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {settings.mistral_api_key}",
            "Accept": "application/json",
        }

    async def list_tools(
        self,
        *,
        refresh: bool = False,
        pretty: bool = False,
    ) -> list[ConnectorTool]:
        connector = quote(self.connector_id, safe="")
        response = await self._request(
            "GET",
            f"/v1/connectors/{connector}/tools",
            params={
                "page": 1,
                "page_size": 100,
                "refresh": str(refresh).lower(),
                "pretty": str(pretty).lower(),
            },
        )
        payload = response.json()
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            items = next(
                (
                    payload[key]
                    for key in ("items", "tools", "data", "results")
                    if isinstance(payload.get(key), list)
                ),
                [],
            )
        else:
            items = []

        return [ConnectorTool.model_validate(item) for item in items]

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        credentials_name: str | None = None,
    ) -> ConnectorToolResult:
        connector = quote(self.connector_id, safe="")
        tool = quote(tool_name, safe="")
        params = {"credentials_name": credentials_name} if credentials_name else None

        # The selected tool is fixed in the path and inputs are wrapped under
        # `arguments`, matching the Connector SDK's direct-call contract. This
        # avoids giving a model control over tool choice.
        response = await self._request(
            "POST",
            f"/v1/connectors/{connector}/tools/{tool}/call",
            params=params,
            json={"arguments": arguments},
        )
        return ConnectorToolResult.model_validate(response.json())

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                headers=self._headers,
                timeout=httpx.Timeout(60.0),
            ) as client:
                response = await client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise ConnectorError("Mistral Connector API is unavailable.") from exc

        if response.is_error:
            raise ConnectorError(
                f"Mistral Connector API returned HTTP {response.status_code}."
            )
        return response
