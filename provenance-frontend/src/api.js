const DEFAULT_API_BASE_URL = "/api/v1";

export class ApiError extends Error {
  constructor(message, { status = 0, body = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

async function readResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  const text = await response.text();
  return text || null;
}

function messageFromBody(body, fallback) {
  if (typeof body === "string" && body.trim()) {
    return body;
  }
  if (body && typeof body.detail === "string") {
    return body.detail;
  }
  return fallback;
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

export function createProvenanceApi({
  baseUrl = import.meta.env?.VITE_API_BASE_URL || DEFAULT_API_BASE_URL,
  fetchImpl = globalThis.fetch,
  pollIntervalMs = 1_000,
  maxPolls = 180,
} = {}) {
  if (typeof fetchImpl !== "function") {
    throw new TypeError("A fetch implementation is required.");
  }

  const normalizedBaseUrl = baseUrl.replace(/\/+$/, "");

  async function request(path, options = {}) {
    let response;
    try {
      response = await fetchImpl(`${normalizedBaseUrl}${path}`, {
        headers: {
          Accept: "application/json",
          ...(options.body ? { "Content-Type": "application/json" } : {}),
          ...options.headers,
        },
        ...options,
      });
    } catch (error) {
      throw new ApiError(
        "Cannot reach the Provenance API. Start the backend and try again.",
        { body: error },
      );
    }

    const body = await readResponse(response);
    if (!response.ok) {
      throw new ApiError(
        messageFromBody(body, `Provenance API request failed (${response.status}).`),
        { status: response.status, body },
      );
    }
    return body;
  }

  const listDecisions = () => request("/decisions");
  const getArtifactVersion = (versionId) =>
    request(`/artifact-versions/${encodeURIComponent(versionId)}`);
  const getJiraProvenance = (issueKey) =>
    request(`/jira/issues/${encodeURIComponent(issueKey)}/provenance`);
  const getJob = (jobId) => request(`/jobs/${encodeURIComponent(jobId)}`);

  async function waitForJob(jobId, onProgress) {
    for (let attempt = 0; attempt < maxPolls; attempt += 1) {
      const job = await getJob(jobId);
      onProgress?.(job);
      if (job.status === "COMPLETED") {
        return job;
      }
      if (job.status === "FAILED") {
        throw new ApiError(job.error || "Provenance analysis failed.", {
          body: job,
        });
      }
      if (attempt < maxPolls - 1) {
        await delay(pollIntervalMs);
      }
    }
    throw new ApiError("Provenance analysis timed out before completion.");
  }

  async function loadDashboard(preferredIssueKey) {
    const decisionPayload = await listDecisions();
    const decisions = decisionPayload.decisions || [];
    if (decisions.length === 0) {
      throw new ApiError(
        "The backend is connected, but no Jira roadmap decisions have been ingested yet.",
        { status: 404 },
      );
    }

    const preferred = preferredIssueKey?.trim().toUpperCase();
    const decision =
      decisions.find((item) => item.external_id.toUpperCase() === preferred) ||
      decisions[0];

    const [artifact, provenance] = await Promise.all([
      getArtifactVersion(decision.version_id),
      getJiraProvenance(decision.external_id),
    ]);

    const versionIds = new Set([decision.version_id]);
    for (const edge of provenance.report?.edges || []) {
      versionIds.add(edge.from_version_id);
      versionIds.add(edge.to_version_id);
    }

    const artifactEntries = await Promise.all(
      [...versionIds].map(async (versionId) => [
        versionId,
        versionId === artifact.id ? artifact : await getArtifactVersion(versionId),
      ]),
    );

    return {
      decision,
      artifact,
      artifacts: Object.fromEntries(artifactEntries),
      provenance,
      report: provenance.report,
    };
  }

  async function analyzeDecision(decisionId, onProgress) {
    const started = await request(
      `/decisions/${encodeURIComponent(decisionId)}/analyses`,
      { method: "POST" },
    );
    return waitForJob(started.job_id, onProgress);
  }

  async function reverifyDecision(decisionId, onProgress) {
    const started = await request(`/reverify/${encodeURIComponent(decisionId)}`, {
      method: "POST",
    });
    return waitForJob(started.job_id, onProgress);
  }

  return {
    analyzeDecision,
    getArtifactVersion,
    getJiraProvenance,
    getJob,
    listDecisions,
    loadDashboard,
    reverifyDecision,
    waitForJob,
  };
}
