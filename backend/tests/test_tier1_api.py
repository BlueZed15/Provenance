import unittest

from backend.app.main import app


class Tier1ApiTests(unittest.TestCase):
    def test_all_tier1_paths_are_registered(self) -> None:
        expected = {
            "/api/v1/health",
            "/api/v1/ingest",
            "/api/v1/decisions",
            "/api/v1/decisions/{decision_id}/analyses",
            "/api/v1/reverify/{decision_id}",
            "/api/v1/jobs/{job_id}",
            "/api/v1/reports/{decision_id}",
            "/api/v1/artifact-versions/{version_id}",
            "/api/v1/artifact-versions/{version_id}/claims",
            "/api/v1/integrations/atlassian/sync",
            "/api/v1/jira/issues/{issue_key}/provenance",
        }
        self.assertEqual(set(app.openapi()["paths"]), expected)


if __name__ == "__main__":
    unittest.main()
