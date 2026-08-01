from __future__ import annotations

from collections.abc import Callable
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

from backend.app.contracts import ArtifactIngestRecord
from backend.app.contracts.normalization import normalize_text, parse_timestamp
from backend.app.domain.enums import AgentRole, Layer, SourceTool


_ADF_BLOCKS = {
    "blockquote",
    "bulletList",
    "codeBlock",
    "heading",
    "listItem",
    "orderedList",
    "panel",
    "paragraph",
    "rule",
    "table",
    "tableCell",
    "tableHeader",
    "tableRow",
}


def _walk(value: Any):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _find_dict(value: Any, predicate: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
    for candidate in _walk(value):
        if isinstance(candidate, dict) and predicate(candidate):
            return candidate
    raise ValueError("Atlassian response did not contain the expected source object")


def extract_jira_issue_objects(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict) and isinstance(value.get("issues"), list):
        return [item for item in value["issues"] if isinstance(item, dict)]
    if isinstance(value, list):
        found: list[dict[str, Any]] = []
        for item in value:
            found.extend(extract_jira_issue_objects(item))
        return found
    if isinstance(value, dict) and "key" in value and "fields" in value:
        return [value]
    return []


def extract_confluence_page_ids(value: Any) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for candidate in _walk(value):
        if not isinstance(candidate, dict):
            continue
        page_id = candidate.get("pageId") or candidate.get("contentId")
        if page_id is None and candidate.get("type") == "page":
            page_id = candidate.get("id")
        if page_id is None and "title" in candidate and "spaceId" in candidate:
            page_id = candidate.get("id")
        if page_id is not None and str(page_id) not in seen:
            seen.add(str(page_id))
            ids.append(str(page_id))
    return ids


def adf_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return normalize_text(value)
    output: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, list):
            for child in node:
                visit(child)
            return
        if not isinstance(node, dict):
            return
        node_type = node.get("type")
        if node_type == "text" and isinstance(node.get("text"), str):
            output.append(node["text"])
        elif node_type == "hardBreak":
            output.append("\n")
        elif node_type == "emoji":
            attrs = node.get("attrs") or {}
            output.append(str(attrs.get("text") or attrs.get("shortName") or ""))
        elif node_type == "inlineCard":
            attrs = node.get("attrs") or {}
            output.append(str(attrs.get("url") or ""))
        visit(node.get("content", []))
        if node_type in _ADF_BLOCKS:
            output.append("\n")

    visit(value)
    return normalize_text("".join(output))


def adf_links(value: Any) -> list[str]:
    links: list[str] = []
    for candidate in _walk(value):
        if not isinstance(candidate, dict):
            continue
        attrs = candidate.get("attrs")
        if isinstance(attrs, dict):
            link = attrs.get("href") or attrs.get("url")
            if isinstance(link, str):
                links.append(link)
        marks = candidate.get("marks")
        if isinstance(marks, list):
            for mark in marks:
                if isinstance(mark, dict) and isinstance(mark.get("attrs"), dict):
                    link = mark["attrs"].get("href")
                    if isinstance(link, str):
                        links.append(link)
    return _deduplicate(links)


class _VisibleHTMLParser(HTMLParser):
    BLOCK_TAGS = {
        "blockquote", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6",
        "li", "ol", "p", "pre", "table", "td", "th", "tr", "ul",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.links: list[str] = []
        self._hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style"}:
            self._hidden_depth += 1
        if not self._hidden_depth and tag == "br":
            self.parts.append("\n")
        if not self._hidden_depth and tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style"} and self._hidden_depth:
            self._hidden_depth -= 1
        elif not self._hidden_depth and tag in self.BLOCK_TAGS and tag != "br":
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._hidden_depth:
            self.parts.append(data)


def html_to_text_and_links(value: str) -> tuple[str, list[str]]:
    parser = _VisibleHTMLParser()
    parser.feed(value)
    parser.close()
    return normalize_text("".join(parser.parts)), _deduplicate(parser.links)


def _deduplicate(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def _name(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("name", "value", "key", "id"):
            if value.get(key) is not None:
                return str(value[key])
    return None


def jira_issue_to_record(
    payload: Any,
    *,
    cloud_id: str,
    site_url: str,
    layer: Layer,
) -> ArtifactIngestRecord | None:
    issue = _find_dict(
        payload,
        lambda item: isinstance(item.get("fields"), dict) and item.get("key") is not None,
    )
    fields = issue["fields"]
    description = fields.get("description")
    text = adf_to_text(description)
    if not text and layer == Layer.ROADMAP:
        text = normalize_text(str(fields.get("summary") or ""))
    if not text:
        return None

    key = str(issue["key"])
    created = fields.get("created") or issue.get("created")
    if created is None:
        raise ValueError(f"Jira issue {key} has no creation timestamp")

    links = adf_links(description)
    for relationship in fields.get("issuelinks") or []:
        if not isinstance(relationship, dict):
            continue
        for direction in ("inwardIssue", "outwardIssue"):
            linked = relationship.get(direction)
            if isinstance(linked, dict) and linked.get("key"):
                links.append(str(linked["key"]))

    components = [
        name for value in fields.get("components") or [] if (name := _name(value))
    ]
    source_tool = SourceTool.JSM if layer == Layer.RAW_TICKET else SourceTool.JIRA
    return ArtifactIngestRecord(
        source_instance=cloud_id,
        source_tool=source_tool,
        external_id=key,
        layer=layer,
        text=text,
        author_role=AgentRole.CUSTOMER if layer == Layer.RAW_TICKET else AgentRole.PM,
        source_created_at=parse_timestamp(created),
        source_updated_at=(
            parse_timestamp(fields["updated"]) if fields.get("updated") else None
        ),
        external_url=urljoin(site_url.rstrip("/") + "/", f"browse/{key}"),
        external_links=_deduplicate(links),
        metadata={
            "summary": fields.get("summary"),
            "project_key": _name(fields.get("project")),
            "issue_type": _name(fields.get("issuetype")),
            "status": _name(fields.get("status")),
            "priority": _name(fields.get("priority")),
            "resolution": _name(fields.get("resolution")),
            "labels": fields.get("labels") or [],
            "components": components,
        },
    )


def _confluence_body(page: dict[str, Any]) -> str:
    body = page.get("body") or page.get("content")
    if isinstance(body, str):
        return body
    if isinstance(body, dict):
        for key in ("storage", "view", "export_view", "styled_view"):
            candidate = body.get(key)
            if isinstance(candidate, str):
                return candidate
            if isinstance(candidate, dict) and isinstance(candidate.get("value"), str):
                return candidate["value"]
        if isinstance(body.get("value"), str):
            return body["value"]
    return ""


def confluence_page_to_record(
    payload: Any,
    *,
    cloud_id: str,
    site_url: str,
    space_key: str,
    layer: Layer,
    boundary_label: str,
) -> ArtifactIngestRecord | None:
    page = _find_dict(
        payload,
        lambda item: (item.get("id") is not None or item.get("pageId") is not None)
        and bool(_confluence_body(item)),
    )
    page_id = str(page.get("id") or page.get("pageId"))
    html = _confluence_body(page)
    text, links = html_to_text_and_links(html)
    if not text:
        return None

    version = page.get("version") if isinstance(page.get("version"), dict) else {}
    created = page.get("createdAt") or page.get("created") or version.get("createdAt")
    if created is None:
        raise ValueError(f"Confluence page {page_id} has no creation timestamp")
    updated = version.get("createdAt") or page.get("updatedAt") or page.get("lastModified")

    web_path: str | None = None
    page_links = page.get("_links")
    if isinstance(page_links, dict):
        web_path = page_links.get("webui") or page_links.get("webUi")
    external_url = (
        urljoin(site_url.rstrip("/") + "/", str(web_path).lstrip("/"))
        if web_path
        else urljoin(
            site_url.rstrip("/") + "/",
            f"wiki/spaces/{space_key}/pages/{page_id}",
        )
    )
    return ArtifactIngestRecord(
        source_instance=cloud_id,
        source_tool=SourceTool.CONFLUENCE,
        external_id=page_id,
        layer=layer,
        text=text,
        author_role=(
            AgentRole.SUPPORT_LEAD if layer == Layer.THEME_SUMMARY else AgentRole.PM
        ),
        source_created_at=parse_timestamp(created),
        source_updated_at=parse_timestamp(updated) if updated else None,
        external_url=external_url,
        external_links=_deduplicate(links),
        metadata={
            "title": page.get("title"),
            "space_key": space_key,
            "boundary_label": boundary_label,
            "status": page.get("status"),
        },
    )
