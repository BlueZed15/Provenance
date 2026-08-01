import asyncio
from collections.abc import Iterable
from typing import Any

from backend.app.services.atlassian import AtlassianConnectorAdapter


def all_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(str(key).lower())
            keys.update(all_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(all_keys(child))
    return keys


def find_first(value: Any, names: Iterable[str]) -> Any | None:
    wanted = {name.lower() for name in names}
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in wanted and child not in (None, "", [], {}):
                return child
        for child in value.values():
            found = find_first(child, wanted)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_first(child, wanted)
            if found is not None:
                return found
    return None


def find_named_value(value: Any, name: str) -> Any | None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() == name.lower():
                return child
        for child in value.values():
            found = find_named_value(child, name)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_named_value(child, name)
            if found is not None:
                return found
    return None


async def probe() -> None:
    adapter = AtlassianConnectorAdapter()
    resources = await adapter.get_accessible_resources()
    if not resources:
        raise RuntimeError("No authenticated Atlassian resources were returned.")

    cloud_id = find_first(resources[0], ("id", "cloudId"))
    if not isinstance(cloud_id, str):
        raise RuntimeError("The Atlassian resource did not include a cloud ID.")

    print("connector_authentication=ok")
    print(f"accessible_resource_count={len(resources)}")
    resource_keys = all_keys(resources)
    print(f"resource_has_id={'id' in resource_keys or 'cloudid' in resource_keys}")
    print(f"resource_has_url={'url' in resource_keys}")

    jira = await adapter.search_jira_issues(
        cloud_id=cloud_id,
        jql="updated >= -365d ORDER BY updated DESC",
        max_results=2,
    )
    jira_keys = all_keys(jira)
    jira_issues = find_named_value(jira, "issues")
    issue_key = find_first(jira, ("key", "issueKey", "id"))
    print(f"jira_search_has_results={issue_key is not None}")
    print(
        "jira_issue_count="
        + str(len(jira_issues) if isinstance(jira_issues, list) else "unknown")
    )
    print(
        "jira_pagination_supported="
        + str(bool({"nextpagetoken", "total", "islast"} & jira_keys))
    )

    if issue_key is not None:
        issue = await adapter.get_jira_issue(
            cloud_id=cloud_id,
            issue_id_or_key=str(issue_key),
        )
        issue_keys = all_keys(issue)
        print(f"jira_raw_identifier={bool({'id', 'key'} & issue_keys)}")
        print(f"jira_raw_description={'description' in issue_keys}")
        print(f"jira_timestamps={bool({'created', 'updated'} <= issue_keys)}")
        print(
            "jira_metadata="
            + str(bool({"project", "issuetype", "status"} <= issue_keys))
        )
        print(
            "jira_links="
            + str(bool({"issuelinks", "remotelinks", "self", "url"} & issue_keys))
        )

    confluence = await adapter.search_confluence_pages(
        cloud_id=cloud_id,
        cql="type = page ORDER BY lastmodified DESC",
        limit=2,
    )
    confluence_keys = all_keys(confluence)
    page_id = find_first(confluence, ("pageId", "contentId", "id"))
    print(f"confluence_search_has_results={page_id is not None}")
    print(
        "confluence_pagination_supported="
        + str(bool({"cursor", "next", "_links"} & confluence_keys))
    )

    if page_id is not None:
        page = await adapter.get_confluence_page(
            cloud_id=cloud_id,
            page_id=str(page_id),
        )
        page_keys = all_keys(page)
        print(f"confluence_raw_identifier={bool({'id', 'pageid'} & page_keys)}")
        print(f"confluence_raw_body={bool({'body', 'content', 'value'} & page_keys)}")
        print(
            "confluence_timestamps="
            + str(bool({"createdat", "updatedat", "created", "lastmodified"} & page_keys))
        )
        print(f"confluence_links={bool({'url', '_links', 'webui'} & page_keys)}")


if __name__ == "__main__":
    asyncio.run(probe())
