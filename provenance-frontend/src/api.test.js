import assert from "node:assert/strict";
import test from "node:test";

import { ApiError, createProvenanceApi } from "./api.js";

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

test("loadDashboard selects the requested decision and hydrates its trace", async () => {
  const requests = [];
  const responses = new Map([
    [
      "/api/v1/decisions",
      json({
        decisions: [
          { id: "decision-1", version_id: "version-1", external_id: "ROAD-1" },
          { id: "decision-2", version_id: "version-2", external_id: "ROAD-2" },
        ],
      }),
    ],
    [
      "/api/v1/artifact-versions/version-2",
      json({ id: "version-2", external_id: "ROAD-2", layer: "ROADMAP" }),
    ],
    [
      "/api/v1/jira/issues/ROAD-2/provenance",
      json({
        decision_id: "decision-2",
        report: {
          decision_version_id: "version-2",
          edges: [
            {
              id: "edge-1",
              from_version_id: "version-2",
              to_version_id: "version-upstream",
            },
          ],
        },
      }),
    ],
    [
      "/api/v1/artifact-versions/version-upstream",
      json({
        id: "version-upstream",
        external_id: "SUPPORT-7",
        layer: "RAW_TICKET",
      }),
    ],
  ]);

  const api = createProvenanceApi({
    fetchImpl: async (url) => {
      requests.push(url);
      const response = responses.get(url);
      assert.ok(response, `Unexpected request: ${url}`);
      return response.clone();
    },
  });

  const dashboard = await api.loadDashboard("road-2");

  assert.equal(dashboard.decision.external_id, "ROAD-2");
  assert.equal(dashboard.artifact.external_id, "ROAD-2");
  assert.equal(dashboard.artifacts["version-upstream"].external_id, "SUPPORT-7");
  assert.equal(
    requests.filter((url) => url.endsWith("/artifact-versions/version-2")).length,
    1,
  );
});

test("analysis jobs are polled until completion", async () => {
  const progress = [];
  let jobPolls = 0;
  const api = createProvenanceApi({
    pollIntervalMs: 0,
    fetchImpl: async (url, options = {}) => {
      if (url === "/api/v1/decisions/decision-1/analyses") {
        assert.equal(options.method, "POST");
        return json({ job_id: "job-1", status: "QUEUED" }, 202);
      }
      if (url === "/api/v1/jobs/job-1") {
        jobPolls += 1;
        return json({
          job_id: "job-1",
          status: jobPolls === 1 ? "RUNNING" : "COMPLETED",
          progress: jobPolls === 1 ? 50 : 100,
        });
      }
      assert.fail(`Unexpected request: ${url}`);
    },
  });

  const completed = await api.analyzeDecision("decision-1", (job) =>
    progress.push(job.progress),
  );

  assert.equal(completed.status, "COMPLETED");
  assert.deepEqual(progress, [50, 100]);
});

test("an empty backend produces a useful integration error", async () => {
  const api = createProvenanceApi({
    fetchImpl: async () => json({ decisions: [] }),
  });

  await assert.rejects(
    () => api.loadDashboard("ROAD-42"),
    (error) =>
      error instanceof ApiError &&
      error.status === 404 &&
      error.message.includes("no Jira roadmap decisions"),
  );
});
