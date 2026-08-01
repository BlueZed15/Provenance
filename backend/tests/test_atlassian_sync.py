import unittest

from backend.app.services.atlassian.sync import (
    AtlassianBoundaries,
    AtlassianSyncService,
)


class FakeAdapter:
    def __init__(self) -> None:
        self.jql: list[str] = []
        self.cql: list[str] = []
        self.fields: list[list[str]] = []

    async def get_accessible_resources(self):
        return [{"id": "cloud-1", "url": "https://example.atlassian.net"}]

    async def search_jira_issues(self, *, jql, fields, **_):
        self.jql.append(jql)
        self.fields.append(fields)
        return {"issues": []}

    async def search_confluence_pages(self, *, cql, **_):
        self.cql.append(cql)
        return {"results": []}

    async def get_confluence_page(self, **_):
        raise AssertionError("No Confluence page should be fetched for empty search")


class AtlassianSyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_sync_uses_only_explicit_demo_boundaries(self) -> None:
        adapter = FakeAdapter()
        result = await AtlassianSyncService(adapter=adapter).sync(
            None,  # no records means persistence is deliberately not reached
            AtlassianBoundaries(
                jsm_project_key="SUPPORT",
                roadmap_project_key="PRODUCT",
                confluence_space_key="PRODUCT",
                roadmap_issue_type="Epic",
            ),
        )
        self.assertEqual(result.ingestion.versions_ingested, 0)
        self.assertTrue(any('labels = "provenance-demo"' in query for query in adapter.jql))
        self.assertTrue(any('labels = "provenance-roadmap"' in query for query in adapter.jql))
        self.assertTrue(any('issuetype = "Epic"' in query for query in adapter.jql))
        self.assertTrue(any('label = "provenance-theme"' in query for query in adapter.cql))
        self.assertTrue(any('label = "provenance-prd"' in query for query in adapter.cql))
        self.assertTrue(all("status = current" in query for query in adapter.cql))
        self.assertTrue(all("comment" not in fields for fields in adapter.fields))


if __name__ == "__main__":
    unittest.main()
