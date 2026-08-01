import unittest
import uuid

from backend.app.domain.enums import Confidence, EdgeStatus, TransformType, Verdict
from backend.app.models import ClaimTransform, ProvenanceEdge
from backend.app.services.analysis import _verdict


def edge(confidence: Confidence, evidence: list[str]) -> ProvenanceEdge:
    return ProvenanceEdge(
        analysis_job_id=uuid.uuid4(),
        from_version_id=uuid.uuid4(),
        to_version_id=uuid.uuid4(),
        status=EdgeStatus.INFERRED,
        confidence=confidence,
        evidence_types=evidence,
        internal_score=0.0,
        alternatives=[],
    )


def transform(kind: TransformType, critical: bool) -> ClaimTransform:
    return ClaimTransform(
        analysis_job_id=uuid.uuid4(),
        edge_id=uuid.uuid4(),
        transform_type=kind,
        retained_slots=[],
        lost_slots=[],
        introduced_slots=[],
        rationale="test",
        is_critical=critical,
    )


class VerdictTests(unittest.TestCase):
    def test_no_substantive_evidence_is_amber(self) -> None:
        self.assertEqual(
            _verdict([edge(Confidence.UNRESOLVED, ["temporal_ok"])], []),
            Verdict.NO_EVIDENCE,
        )

    def test_ambiguous_semantic_evidence_is_unresolved(self) -> None:
        self.assertEqual(
            _verdict(
                [edge(Confidence.UNRESOLVED, ["embedding", "temporal_ok"])],
                [],
            ),
            Verdict.UNRESOLVED,
        )

    def test_critical_drift_is_red(self) -> None:
        self.assertEqual(
            _verdict(
                [edge(Confidence.OBSERVED, ["explicit_link", "temporal_ok"])],
                [transform(TransformType.QUANTITY_CHANGED, True)],
            ),
            Verdict.DRIFT,
        )

    def test_preserved_observed_chain_is_aligned(self) -> None:
        self.assertEqual(
            _verdict(
                [edge(Confidence.OBSERVED, ["explicit_link", "temporal_ok"])],
                [transform(TransformType.PRESERVED, False)],
            ),
            Verdict.ALIGNED,
        )


if __name__ == "__main__":
    unittest.main()
