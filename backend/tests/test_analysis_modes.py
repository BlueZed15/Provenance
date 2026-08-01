import unittest
import uuid
from datetime import datetime, timezone

from backend.app.domain.enums import AgentRole, Layer, SourceTool
from backend.app.models import Artifact, ArtifactVersion
from backend.app.services.analysis import _candidate_parents


class AnalysisModeTests(unittest.TestCase):
    def test_current_mode_can_follow_post_decision_update(self) -> None:
        artifact_id = uuid.uuid4()
        artifact = Artifact(
            id=artifact_id,
            source_instance="test",
            source_tool=SourceTool.JSM,
            external_id="SUP-1",
            layer=Layer.RAW_TICKET,
        )
        parent = ArtifactVersion(
            id=uuid.uuid4(),
            artifact_id=artifact_id,
            version_number=2,
            text="Approval is required above $5,000.",
            content_hash="a" * 64,
            author_role=AgentRole.CUSTOMER,
            source_created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
            source_updated_at=datetime(2026, 7, 4, tzinfo=timezone.utc),
            external_links=[],
            artifact_metadata={},
        )
        child = ArtifactVersion(
            id=uuid.uuid4(),
            artifact_id=uuid.uuid4(),
            version_number=1,
            text="Approval is required above $10,000.",
            content_hash="b" * 64,
            author_role=AgentRole.PM,
            source_created_at=datetime(2026, 7, 3, tzinfo=timezone.utc),
            external_links=["SUP-1"],
            artifact_metadata={},
        )

        historical = _candidate_parents(
            child,
            [parent],
            {artifact_id: artifact},
            enforce_temporal=True,
        )
        current = _candidate_parents(
            child,
            [parent],
            {artifact_id: artifact},
            enforce_temporal=False,
        )

        self.assertEqual(historical, [])
        self.assertEqual(len(current), 1)
        self.assertIn("post_decision_update", current[0].evidence_types)
        self.assertNotIn("temporal_ok", current[0].evidence_types)


if __name__ == "__main__":
    unittest.main()
