"""Exercise the core endpoint and reverification flow, then remove isolated data."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from backend.app.db.session import SessionLocal
from backend.app.main import app
from backend.app.models import Artifact, DecisionReport


def main() -> None:
    source_instance = f"endpoint-check-{uuid.uuid4()}"
    external_ids = {"CHECK-RAW-1", "CHECK-THEME-1", "CHECK-ROADMAP-1"}
    payload = {
        "items": [
            {
                "id": "CHECK-RAW-1",
                "source_instance": source_instance,
                "layer": "RAW_TICKET",
                "tool": "JSM",
                "text": "Enterprise refunds above $10,000 require finance approval.",
                "author_role": "CUSTOMER",
                "created_at": "2026-07-01T00:00:00Z",
                "links": [],
                "metadata": {"severity": "high", "segment": "enterprise"},
            },
            {
                "id": "CHECK-THEME-1",
                "source_instance": source_instance,
                "layer": "THEME_SUMMARY",
                "tool": "CONFLUENCE",
                "text": "Enterprise refunds above $10,000 require finance approval.",
                "author_role": "SUPPORT_LEAD",
                "created_at": "2026-07-02T00:00:00Z",
                "links": ["CHECK-RAW-1"],
                "metadata": {"title": "Billing operations theme"},
            },
            {
                "id": "CHECK-ROADMAP-1",
                "source_instance": source_instance,
                "layer": "ROADMAP",
                "tool": "JIRA",
                "text": "Enterprise refunds above $10,000 require finance approval.",
                "author_role": "PM",
                "created_at": "2026-07-03T00:00:00Z",
                "links": ["CHECK-THEME-1"],
                "metadata": {"summary": "Enterprise refund approval"},
            },
        ]
    }

    try:
        with TestClient(app) as client:
            health = client.get("/api/v1/health")
            health.raise_for_status()

            ingested = client.post("/api/v1/ingest", json=payload)
            ingested.raise_for_status()
            ingest_body = ingested.json()
            if ingest_body["versions_ingested"] != 3:
                raise RuntimeError("Tier 1 ingest did not create three versions")

            repeated = client.post("/api/v1/ingest", json=payload)
            repeated.raise_for_status()
            if repeated.json()["versions_reused"] != 3:
                raise RuntimeError("Tier 1 ingest was not idempotent")

            decisions = client.get("/api/v1/decisions")
            decisions.raise_for_status()
            decision = next(
                item
                for item in decisions.json()["decisions"]
                if item["external_id"] == "CHECK-ROADMAP-1"
            )
            decision_id = decision["id"]

            started = client.post(f"/api/v1/decisions/{decision_id}/analyses")
            started.raise_for_status()
            job_id = started.json()["job_id"]
            job = client.get(f"/api/v1/jobs/{job_id}")
            job.raise_for_status()
            if job.json()["status"] != "COMPLETED":
                raise RuntimeError(
                    f"Tier 1 analysis did not complete: {job.json()['status']} "
                    f"({job.json().get('error')})"
                )

            report = client.get(f"/api/v1/reports/{decision_id}")
            report.raise_for_status()
            report_body = report.json()
            if not report_body["edges"]:
                raise RuntimeError("Tier 1 report contained no provenance edges")
            if report_body["verification_status"] != "CURRENT":
                raise RuntimeError("Initial report was not current")
            initial_report_id = report_body["report_id"]

            changed = client.post(
                "/api/v1/ingest",
                json={
                    "items": [
                        {
                            **payload["items"][0],
                            "text": "Enterprise refunds above $5,000 require finance approval.",
                            "updated_at": "2026-07-04T00:00:00Z",
                        }
                    ]
                },
            )
            changed.raise_for_status()
            changed_body = changed.json()
            if changed_body["stale_reports"] != 1:
                raise RuntimeError("Changed evidence did not stale the affected report")
            if len(changed_body["reverification_jobs"]) != 1:
                raise RuntimeError("Changed evidence did not enqueue one reverification")
            auto_job = client.get(
                f"/api/v1/jobs/{changed_body['reverification_jobs'][0]}"
            )
            auto_job.raise_for_status()
            if auto_job.json()["status"] != "COMPLETED":
                raise RuntimeError("Automatic reverification did not complete")
            if auto_job.json()["mode"] != "CURRENT":
                raise RuntimeError("Automatic reverification did not use current evidence")

            refreshed = client.get(f"/api/v1/reports/{decision_id}")
            refreshed.raise_for_status()
            refreshed_body = refreshed.json()
            if refreshed_body["report_id"] == initial_report_id:
                raise RuntimeError("Reverification did not create a new immutable report")
            if refreshed_body["verification_status"] != "CURRENT":
                raise RuntimeError("Reverified report was not current")
            if refreshed_body["analysis_mode"] != "CURRENT":
                raise RuntimeError("Reverified report did not expose current analysis mode")
            if refreshed_body["verdict"] != "DRIFT":
                raise RuntimeError(
                    "Changed approval threshold was not classified as drift"
                )
            comparison = refreshed_body.get("comparison")
            if comparison is None or comparison["previous_report_id"] != initial_report_id:
                raise RuntimeError("Reverified report did not compare with the prior report")
            if not comparison["verdict_changed"]:
                raise RuntimeError("Report comparison did not expose the verdict change")
            if not any(
                "post_decision_update" in edge["evidence_types"]
                for edge in refreshed_body["edges"]
            ):
                raise RuntimeError("Current analysis did not identify post-decision evidence")

            with SessionLocal() as verification_session:
                prior = verification_session.get(
                    DecisionReport,
                    uuid.UUID(initial_report_id),
                )
                if prior is None or not prior.is_stale:
                    raise RuntimeError("Prior report was not retained in stale state")

            manual = client.post(f"/api/v1/reverify/{decision_id}")
            manual.raise_for_status()
            manual_job = client.get(f"/api/v1/jobs/{manual.json()['job_id']}")
            manual_job.raise_for_status()
            if manual_job.json()["status"] != "COMPLETED":
                raise RuntimeError("Manual reverification did not complete")

            ticket = next(
                item
                for item in client.get("/api/v1/decisions").json()["decisions"]
                if item["external_id"] == "CHECK-ROADMAP-1"
            )
            version = client.get(
                f"/api/v1/artifact-versions/{ticket['version_id']}"
            )
            version.raise_for_status()
            claims = client.get(
                f"/api/v1/artifact-versions/{ticket['version_id']}/claims"
            )
            claims.raise_for_status()
            if not claims.json()["claims"]:
                raise RuntimeError("Artifact claims endpoint returned no analyzed claims")

            provenance = client.get(
                "/api/v1/jira/issues/CHECK-ROADMAP-1/provenance"
            )
            provenance.raise_for_status()
            if provenance.json()["report"] is None:
                raise RuntimeError("Jira provenance lookup returned no report")

            print("tier1_health=ok")
            print("tier1_ingest_idempotency=ok")
            print("tier1_analysis_job=ok")
            print(f"tier1_report_verdict={report_body['verdict']}")
            print(f"tier1_report_edges={len(report_body['edges'])}")
            print(f"tier1_report_transforms={len(report_body['transforms'])}")
            print("tier1_artifact_and_claim_reads=ok")
            print("tier1_jira_lookup=ok")
            print("automatic_affected_decision_detection=ok")
            print("stale_report_history=ok")
            print("automatic_current_reanalysis=ok")
            print(f"reverified_report_verdict={refreshed_body['verdict']}")
            print("report_comparison=ok")
            print("manual_reverify_endpoint=ok")
    finally:
        with SessionLocal() as session:
            artifacts = list(
                session.scalars(
                    select(Artifact).where(Artifact.source_instance == source_instance)
                )
            )
            found_ids = {artifact.external_id for artifact in artifacts}
            if not found_ids.issubset(external_ids):
                raise RuntimeError("Refusing to clean up unexpected endpoint-check data")
            session.execute(
                delete(Artifact).where(Artifact.source_instance == source_instance)
            )
            session.commit()
        print("tier1_endpoint_check_cleanup=ok")


if __name__ == "__main__":
    main()
