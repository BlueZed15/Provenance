from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from backend.app.contracts import ArtifactIngestRecord
from backend.app.domain.enums import Layer
from backend.app.services.atlassian.connector import AtlassianConnectorAdapter
from backend.app.services.atlassian.mappers import (
    confluence_page_to_record,
    extract_confluence_page_ids,
    extract_jira_issue_objects,
    jira_issue_to_record,
)
from backend.app.services.ingestion import IngestionResult, ingest_records


TICKET_LABEL = "provenance-demo"
THEME_LABEL = "provenance-theme"
PRD_LABEL = "provenance-prd"
ROADMAP_LABEL = "provenance-roadmap"

INGESTION_JIRA_FIELDS = [
    "summary",
    "description",
    "status",
    "issuetype",
    "priority",
    "labels",
    "components",
    "created",
    "updated",
    "resolution",
    "project",
    "issuelinks",
    "parent",
]

_BOUNDARY_VALUE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,99}$")


@dataclass(frozen=True)
class AtlassianBoundaries:
    jsm_project_key: str
    roadmap_project_key: str
    confluence_space_key: str
    roadmap_issue_type: str

    def __post_init__(self) -> None:
        for field_name in (
            "jsm_project_key",
            "roadmap_project_key",
            "confluence_space_key",
        ):
            value = getattr(self, field_name)
            if not _BOUNDARY_VALUE.fullmatch(value):
                raise ValueError(f"{field_name} is not a valid Atlassian key")
        if self.roadmap_issue_type not in {"Epic", "Idea"}:
            raise ValueError("roadmap_issue_type must be Epic or Idea")


@dataclass(frozen=True)
class AtlassianSyncResult:
    ingestion: IngestionResult
    accessible_resource_count: int
    source_instance: str
    skipped_blank_items: int


class AtlassianSyncService:
    """Fetch only explicitly labelled demo artifacts through Mistral Studio."""

    def __init__(self, adapter: AtlassianConnectorAdapter | None = None) -> None:
        self.adapter = adapter or AtlassianConnectorAdapter()

    async def sync(
        self,
        session: Session,
        boundaries: AtlassianBoundaries,
    ) -> AtlassianSyncResult:
        resources = await self.adapter.get_accessible_resources()
        if not resources:
            raise RuntimeError("The Mistral Studio connector returned no Atlassian resource")
        resource = resources[0]
        cloud_id = _resource_value(resource, "id", "cloudId")
        site_url = _resource_value(resource, "url")
        if not cloud_id or not site_url:
            raise RuntimeError("The selected Atlassian resource has no ID or URL")

        records: list[ArtifactIngestRecord] = []
        skipped = 0

        ticket_jql = (
            f'project = "{boundaries.jsm_project_key}" '
            f'AND labels = "{TICKET_LABEL}" ORDER BY updated ASC'
        )
        ticket_payload = await self.adapter.search_jira_issues(
            cloud_id=cloud_id,
            jql=ticket_jql,
            max_results=100,
            fields=INGESTION_JIRA_FIELDS,
        )
        ticket_records, ticket_skipped = await self._jira_records(
            cloud_id=cloud_id,
            site_url=site_url,
            payload=ticket_payload,
            layer=Layer.RAW_TICKET,
        )
        records.extend(ticket_records)
        skipped += ticket_skipped

        roadmap_jql = (
            f'project = "{boundaries.roadmap_project_key}" '
            f'AND labels = "{ROADMAP_LABEL}" '
            f'AND issuetype = "{boundaries.roadmap_issue_type}" ORDER BY updated ASC'
        )
        roadmap_payload = await self.adapter.search_jira_issues(
            cloud_id=cloud_id,
            jql=roadmap_jql,
            max_results=100,
            fields=INGESTION_JIRA_FIELDS,
        )
        roadmap_records, roadmap_skipped = await self._jira_records(
            cloud_id=cloud_id,
            site_url=site_url,
            payload=roadmap_payload,
            layer=Layer.ROADMAP,
        )
        records.extend(roadmap_records)
        skipped += roadmap_skipped

        for layer, label in (
            (Layer.THEME_SUMMARY, THEME_LABEL),
            (Layer.PRD, PRD_LABEL),
        ):
            cql = (
                f'type = page AND space = "{boundaries.confluence_space_key}" '
                f'AND label = "{label}" AND status = current '
                "ORDER BY lastmodified ASC"
            )
            search_payload = await self.adapter.search_confluence_pages(
                cloud_id=cloud_id,
                cql=cql,
                limit=250,
            )
            for page_id in extract_confluence_page_ids(search_payload):
                page = await self.adapter.get_confluence_page(
                    cloud_id=cloud_id,
                    page_id=page_id,
                )
                record = confluence_page_to_record(
                    page,
                    cloud_id=cloud_id,
                    site_url=site_url,
                    space_key=boundaries.confluence_space_key,
                    layer=layer,
                    boundary_label=label,
                )
                if record is None:
                    skipped += 1
                else:
                    records.append(record)

        ingestion = ingest_records(session, records) if records else IngestionResult(
            versions_ingested=0,
            versions_reused=0,
            counts_by_layer={},
        )
        return AtlassianSyncResult(
            ingestion=ingestion,
            accessible_resource_count=len(resources),
            source_instance=cloud_id,
            skipped_blank_items=skipped,
        )

    async def _jira_records(
        self,
        *,
        cloud_id: str,
        site_url: str,
        payload: Any,
        layer: Layer,
    ) -> tuple[list[ArtifactIngestRecord], int]:
        records: list[ArtifactIngestRecord] = []
        skipped = 0
        for issue_summary in extract_jira_issue_objects(payload):
            issue_payload: Any = issue_summary
            if not isinstance(issue_summary.get("fields"), dict):
                issue_payload = await self.adapter.get_jira_issue(
                    cloud_id=cloud_id,
                    issue_id_or_key=str(issue_summary.get("key") or issue_summary.get("id")),
                    fields=INGESTION_JIRA_FIELDS,
                )
            record = jira_issue_to_record(
                issue_payload,
                cloud_id=cloud_id,
                site_url=site_url,
                layer=layer,
            )
            if record is None:
                skipped += 1
            else:
                records.append(record)
        return records, skipped


def _resource_value(resource: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = resource.get(key)
        if value is not None:
            return str(value)
    return None
