import asyncio
import json
import re

from backend.app.services.atlassian import AtlassianConnectorAdapter
from backend.app.services.mistral.connectors import MistralConnectorClient
from backend.scripts.probe_atlassian_reads import find_first


def redact_diagnostic(text: str) -> str:
    text = re.sub(r"https?://\S+", "[URL]", text)
    text = re.sub(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        "[UUID]",
        text,
        flags=re.I,
    )
    text = re.sub(r"\b[A-Z][A-Z0-9_]+-\d+\b", "[ISSUE]", text)
    text = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[EMAIL]", text)
    return text[:800]


async def inspect() -> None:
    adapter = AtlassianConnectorAdapter()
    resources = await adapter.get_accessible_resources()
    cloud_id = find_first(resources[0], ("id", "cloudId"))
    if not isinstance(cloud_id, str):
        raise RuntimeError("No cloud ID")

    result = await MistralConnectorClient().call_tool(
        "searchJiraIssuesUsingJql",
        {
            "cloudId": cloud_id,
            "jql": "updated >= -365d ORDER BY updated DESC",
            "maxResults": 1,
            "fields": ["summary", "description", "created", "updated", "project"],
            "responseContentFormat": "adf",
            "searchResultMode": "issues",
        },
    )
    print(f"content_block_count={len(result.content)}")
    print(f"metadata_present={result.metadata is not None}")
    print(
        "metadata_keys="
        + ",".join(sorted(result.metadata.keys() if result.metadata else []))
    )
    for index, block in enumerate(result.content):
        text = block.get("text")
        print(f"block_{index}_keys={','.join(sorted(block))}")
        print(f"block_{index}_type={block.get('type', 'missing')}")
        print(f"block_{index}_text_is_string={isinstance(text, str)}")
        if isinstance(text, str):
            stripped = text.strip()
            print(f"block_{index}_text_length={len(stripped)}")
            print(f"block_{index}_starts_json={stripped[:1] in ('{', '[')}")
            print(f"block_{index}_starts_fence={stripped.startswith('```')}")
            try:
                json.loads(stripped)
                valid_json = True
            except json.JSONDecodeError:
                valid_json = False
            print(f"block_{index}_valid_json={valid_json}")

            issue_match = re.search(r"\b[A-Z][A-Z0-9_]+-\d+\b", stripped)
            print(f"block_{index}_contains_issue_key={issue_match is not None}")
            lowered_search = stripped.lower()
            print(
                f"block_{index}_signals_no_results="
                + str(
                    any(
                        marker in lowered_search
                        for marker in ("no issue", "no result", "0 issue", "zero issue")
                    )
                )
            )
            print(
                f"block_{index}_signals_error="
                + str(
                    any(
                        marker in lowered_search
                        for marker in ("error", "unauthorized", "forbidden", "permission")
                    )
                )
            )
            if "error" in lowered_search:
                print(f"block_{index}_redacted_error={redact_diagnostic(stripped)}")
            if issue_match is not None:
                issue = await MistralConnectorClient().call_tool(
                    "getJiraIssue",
                    {
                        "cloudId": cloud_id,
                        "issueIdOrKey": issue_match.group(0),
                        "fields": [
                            "summary",
                            "description",
                            "status",
                            "issuetype",
                            "priority",
                            "labels",
                            "components",
                            "created",
                            "updated",
                            "project",
                            "comment",
                        ],
                        "responseContentFormat": "adf",
                        "updateHistory": False,
                    },
                )
                issue_texts = issue.text_blocks()
                combined = "\n".join(issue_texts)
                lowered = combined.lower()
                print(f"issue_block_count={len(issue.content)}")
                print(f"issue_text_length={len(combined)}")
                print(f"issue_contains_identifier={issue_match.group(0) in combined}")
                print(f"issue_has_summary_label={'summary' in lowered}")
                print(f"issue_has_description_label={'description' in lowered}")
                print(f"issue_has_created_label={'created' in lowered}")
                print(f"issue_has_updated_label={'updated' in lowered}")
                print(f"issue_has_project_label={'project' in lowered}")
                print(
                    "issue_has_iso_timestamp="
                    + str(
                        re.search(
                            r"\d{4}-\d{2}-\d{2}[T ][0-9:]+",
                            combined,
                        )
                        is not None
                    )
                )
                print(
                    "issue_has_url="
                    + str(re.search(r"https?://", combined) is not None)
                )
                print(
                    "issue_has_adf_structure="
                    + str(
                        '"type"' in combined
                        and ('"doc"' in combined or '"paragraph"' in combined)
                    )
                )

    confluence = await MistralConnectorClient().call_tool(
        "searchConfluenceUsingCql",
        {
            "cloudId": cloud_id,
            "cql": "type = page ORDER BY lastmodified DESC",
            "limit": 1,
            "next": True,
        },
    )
    confluence_text = "\n".join(confluence.text_blocks())
    confluence_lowered = confluence_text.lower()
    print(f"confluence_content_block_count={len(confluence.content)}")
    print(f"confluence_text_length={len(confluence_text)}")
    print(
        "confluence_signals_no_results="
        + str(
            any(
                marker in confluence_lowered
                for marker in ("no page", "no result", "0 page", "zero page")
            )
        )
    )
    print(
        "confluence_signals_error="
        + str(
            any(
                marker in confluence_lowered
                for marker in ("error", "unauthorized", "forbidden", "permission")
            )
        )
    )
    if "error" in confluence_lowered:
        print("confluence_redacted_error=" + redact_diagnostic(confluence_text))
    print(
        "confluence_contains_page_identifier="
        + str(
            re.search(r"(?:page[_ -]?id|content[_ -]?id)[^0-9]{0,5}\d+", confluence_text, re.I)
            is not None
        )
    )


if __name__ == "__main__":
    asyncio.run(inspect())
