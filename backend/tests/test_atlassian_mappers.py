import unittest

from backend.app.domain.enums import Layer, SourceTool
from backend.app.services.atlassian.mappers import (
    adf_to_text,
    confluence_page_to_record,
    extract_confluence_page_ids,
    html_to_text_and_links,
    jira_issue_to_record,
)
from backend.app.services.atlassian.sync import AtlassianBoundaries


class AtlassianMapperTests(unittest.TestCase):
    def test_adf_text_preserves_visible_claim_text(self) -> None:
        adf = {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Charged twice"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Cannot dispute it"}]},
            ],
        }
        self.assertEqual(adf_to_text(adf), "Charged twice\nCannot dispute it")

    def test_ticket_mapper_uses_description_not_summary_or_comments(self) -> None:
        payload = {
            "key": "SUPPORT-1",
            "fields": {
                "summary": "Summary must not become source text",
                "description": {
                    "type": "doc",
                    "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": "I was charged twice"}]}
                    ],
                },
                "comment": {"comments": [{"body": "private comment"}]},
                "created": "2026-08-01T00:00:00Z",
                "updated": "2026-08-01T01:00:00Z",
                "project": {"key": "SUPPORT"},
                "issuetype": {"name": "Service Request"},
                "labels": ["provenance-demo"],
            },
        }
        record = jira_issue_to_record(
            payload,
            cloud_id="cloud-1",
            site_url="https://example.atlassian.net",
            layer=Layer.RAW_TICKET,
        )
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.text, "I was charged twice")
        self.assertNotIn("private comment", record.text)
        self.assertEqual(record.source_tool, SourceTool.JSM)

    def test_html_mapper_keeps_visible_text_and_links(self) -> None:
        text, links = html_to_text_and_links(
            '<p>Billing <strong>friction</strong></p><script>secret</script>'
            '<p><a href="https://example.test/SUPPORT-1">Evidence</a></p>'
        )
        self.assertEqual(text, "Billing friction\nEvidence")
        self.assertEqual(links, ["https://example.test/SUPPORT-1"])

    def test_confluence_mapper_uses_explicit_layer(self) -> None:
        page = {
            "id": "123",
            "title": "Theme",
            "status": "current",
            "spaceId": "space-1",
            "createdAt": "2026-08-01T00:00:00Z",
            "version": {"createdAt": "2026-08-01T01:00:00Z"},
            "body": {"storage": {"value": "<p>Billing friction</p>"}},
        }
        record = confluence_page_to_record(
            page,
            cloud_id="cloud-1",
            site_url="https://example.atlassian.net",
            space_key="PRODUCT",
            layer=Layer.THEME_SUMMARY,
            boundary_label="provenance-theme",
        )
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.layer, Layer.THEME_SUMMARY)
        self.assertEqual(record.metadata["boundary_label"], "provenance-theme")
        self.assertEqual(extract_confluence_page_ids({"results": [page]}), ["123"])

    def test_boundaries_reject_query_injection(self) -> None:
        with self.assertRaises(ValueError):
            AtlassianBoundaries(
                jsm_project_key='SUPPORT" OR project is not EMPTY',
                roadmap_project_key="PRODUCT",
                confluence_space_key="PRODUCT",
                roadmap_issue_type="Epic",
            )


if __name__ == "__main__":
    unittest.main()
