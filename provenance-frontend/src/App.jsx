import { useState } from "react";

const VERDICT_CONTENT = {
  drift: {
    badgeText: "DRIFT",
    badgeClass: "danger",
    messageClass: "sm-danger",
    title: "Critical detail omitted",
    rationale:
      'The specific actionable problem of "double-charges" was lost when generalized to "friction" at hop 1.',
    icon: "danger",
  },
  "no-evidence": {
    badgeText: "UNRESOLVED",
    badgeClass: "warning",
    messageClass: "sm-warning",
    title: "No linked evidence found",
    rationale:
      "There are no upstream tickets or PRDs mapping to this feature. Please record your strategic reasoning.",
    icon: "warning",
  },
  aligned: {
    badgeText: "ALIGNED",
    badgeClass: "success",
    messageClass: "sm-success",
    title: "Evidence preserved",
    rationale:
      "Customer intent and actionable details have been safely preserved across 2 hops.",
    icon: "success",
  },
};

function JiraLogoIcon() {
  return (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="#0C66E4"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path d="M12 0L24 12L12 24L0 12L12 0Z" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="#6B778C"
      strokeWidth="2"
      aria-hidden="true"
    >
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

function TimelineIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden="true"
    >
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
      <line x1="3" y1="9" x2="21" y2="9" />
      <line x1="9" y1="21" x2="9" y2="9" />
    </svg>
  );
}

function BacklogIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden="true"
    >
      <line x1="8" y1="6" x2="21" y2="6" />
      <line x1="8" y1="12" x2="21" y2="12" />
      <line x1="8" y1="18" x2="21" y2="18" />
      <line x1="3" y1="6" x2="3.01" y2="6" />
      <line x1="3" y1="12" x2="3.01" y2="12" />
      <line x1="3" y1="18" x2="3.01" y2="18" />
    </svg>
  );
}

function SprintIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden="true"
    >
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  );
}

function ProvenanceIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden="true"
    >
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
      <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
      <line x1="12" y1="22.08" x2="12" y2="12" />
    </svg>
  );
}

function VerdictIcon({ type }) {
  if (type === "danger") {
    return (
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="#BF2600"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <path
          d="M12 2L2 22H22L12 2Z"
          fill="#FFEBE6"
          stroke="#BF2600"
          strokeWidth="2"
          strokeLinejoin="round"
        />
        <circle cx="12" cy="16" r="1.5" fill="#BF2600" />
        <rect x="11" y="9" width="2" height="5" rx="1" fill="#BF2600" />
      </svg>
    );
  }

  if (type === "warning") {
    return (
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="#A05E03"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
    );
  }

  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="#064E3B"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  );
}

function QuoteBlock({ snippet, children, expandable = false }) {
  const [expanded, setExpanded] = useState(false);

  if (!expandable) {
    return (
      <div className="quote-block">
        <p className="quote-text">{children}</p>
      </div>
    );
  }

  return (
    <button
      type="button"
      className={`quote-block quote-button${expanded ? " expanded" : ""}`}
      onClick={() => setExpanded((current) => !current)}
      aria-expanded={expanded}
    >
      {!expanded ? (
        <p className="quote-text claim-snippet">{snippet}</p>
      ) : (
        <p className="quote-text full-text visible">{children}</p>
      )}
    </button>
  );
}

function JiraTopNav() {
  return (
    <header className="jira-top-nav">
      <div className="jira-logo">
        <JiraLogoIcon />
        Jira
      </div>
      <nav className="jira-nav-links" aria-label="Jira navigation">
        <span>Your work</span>
        <span>Projects</span>
        <span>Filters</span>
        <span>Dashboards</span>
        <span>Teams</span>
        <span>Apps</span>
      </nav>
      <div className="jira-nav-right">
        <button type="button" className="atl-create-btn">
          Create
        </button>
        <SearchIcon />
        <div className="profile-avatar">PM</div>
      </div>
    </header>
  );
}

function ProjectSidebar() {
  return (
    <aside className="project-sidebar">
      <div className="project-header">
        <div className="project-icon" />
        <div className="project-title">
          <h3>Frontend Platform</h3>
          <p>Software project</p>
        </div>
      </div>
      <div className="sidebar-menu-item">
        <TimelineIcon />
        Timeline
      </div>
      <div className="sidebar-menu-item">
        <BacklogIcon />
        Backlog
      </div>
      <div className="sidebar-menu-item active">
        <SprintIcon />
        Active sprints
      </div>
      <div className="sidebar-section-label">Development</div>
      <div className="sidebar-menu-item">Code</div>
      <div className="sidebar-menu-item">Releases</div>
    </aside>
  );
}

function IssueWorkspace() {
  return (
    <main className="issue-workspace">
      <div className="breadcrumbs">
        <a href="#projects">Projects</a> <span>/</span>{" "}
        <a href="#frontend-platform">Frontend Platform</a> <span>/</span>{" "}
        <span>PROJ-882</span>
      </div>

      <h1 className="issue-title">Redesign Checkout Page</h1>

      <div className="issue-action-bar">
        <button type="button" className="atl-button-secondary">
          📎 Attach
        </button>
        <button type="button" className="atl-button-secondary">
          🔗 Link issue
        </button>
        <button type="button" className="atl-button-secondary">
          ✓ Add child issue
        </button>
        <button type="button" className="atl-button-secondary">
          Apps ▾
        </button>
      </div>

      <div className="issue-grid">
        <div>
          <div className="field-group">
            <h4>Description</h4>
            <p className="field-value">
              We are prioritizing a massive overhaul of the checkout flow for Q3. As
              part of this redesign, the core objective is to reduce enterprise billing
              friction.
              <br />
              <br />
              <strong>Requirements:</strong>
              <br />- Implement a new responsive billing matrix.
              <br />- Add a <strong>bulk export button</strong> for enterprise invoices.
              <br />- Simplify the credit card entry form.
            </p>
          </div>

          <div className="field-group activity-section">
            <h4>Activity</h4>
            <div className="activity-tabs">
              <span className="activity-tab-active">Comments</span>
              <span>History</span>
              <span>Work log</span>
            </div>
            <div className="comment-row">
              <div className="comment-avatar" />
              <div className="comment-input-wrapper">
                <input type="text" placeholder="Add a comment..." />
              </div>
            </div>
          </div>
        </div>

        <div>
          <div className="field-group">
            <h4>Status</h4>
            <p>
              <span className="lozenge inprogress">IN PROGRESS</span>
            </p>
          </div>
          <div className="field-group">
            <h4>Assignee</h4>
            <p className="person-row">
              <span className="person-avatar neutral" />
              Unassigned
            </p>
          </div>
          <div className="field-group">
            <h4>Reporter</h4>
            <p className="person-row">
              <span className="person-avatar reporter" />
              Product Manager
            </p>
          </div>
          <div className="field-group">
            <h4>Labels</h4>
            <p className="labels-empty">None</p>
          </div>
        </div>
      </div>
    </main>
  );
}

function DriftState() {
  return (
    <div className="state-view active">
      <div className="timeline">
        <div className="node jira">
          <div className="node-meta">
            <span className="app-label jira">Jira</span>
            <span>Today</span>
          </div>
          <h4 className="node-title">Redesign Checkout Page</h4>
          <QuoteBlock snippet='"bulk export button..."' expandable>
            We need to prioritize a <mark>bulk export button</mark> for the enterprise
            segment.
          </QuoteBlock>
        </div>

        <div className="node conf">
          <div className="edge-badge-container">
            <span className="lozenge default">STRONG INFERENCE</span>
          </div>
          <div className="node-meta">
            <span className="app-label conf">Confluence PRD</span>
            <span>2 days ago</span>
          </div>
          <h4 className="node-title">Enterprise Billing Friction</h4>
          <div className="local-drift">
            <strong>CRITICAL_DETAIL_OMITTED</strong>
            The proposed solution ignores the upstream double-charge bug.
          </div>
        </div>

        <div className="node jsm">
          <div className="edge-badge-container">
            <span className="lozenge default">OBSERVED</span>
          </div>
          <div className="node-meta">
            <span className="app-label jsm">JSM Ticket</span>
            <span>1 week ago</span>
          </div>
          <h4 className="node-title">ACC-4471: Account Issue</h4>
          <QuoteBlock snippet='"charged twice..."' expandable>
            I was <mark>charged twice</mark> this month and I cannot find the dispute
            page anywhere.
          </QuoteBlock>
        </div>
      </div>
    </div>
  );
}

function NoEvidenceState() {
  return (
    <div className="state-view active">
      <div className="timeline">
        <div className="node jira">
          <div className="node-meta">
            <span className="app-label jira">Jira</span>
            <span>Today</span>
          </div>
          <h4 className="node-title">Redesign Checkout Page</h4>
          <QuoteBlock>"Build a generative AI support bot."</QuoteBlock>
          <div className="no-evidence-actions">
            <button type="button" className="atl-button-secondary">
              Record override
            </button>
            <button type="button" className="atl-button-secondary">
              Link evidence
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function AlignedState() {
  return (
    <div className="state-view active">
      <div className="timeline">
        <div className="node jira">
          <div className="node-meta">
            <span className="app-label jira">Jira</span>
            <span>Today</span>
          </div>
          <h4 className="node-title">Redesign Checkout Page</h4>
        </div>

        <div className="node conf">
          <div className="edge-badge-container">
            <span className="lozenge default">STRONG INFERENCE</span>
          </div>
          <div className="node-meta">
            <span className="app-label conf">Confluence PRD</span>
            <span>Yesterday</span>
          </div>
          <h4 className="node-title">Billing Error Report</h4>
          <QuoteBlock>"Multiple users reported double charges..."</QuoteBlock>
          <div className="local-success">
            <strong>LEGITIMATE_GENERALIZATION</strong>
            12 billing tickets safely abstracted.
          </div>
        </div>

        <div className="node jsm">
          <div className="edge-badge-container">
            <span className="lozenge default">OBSERVED</span>
          </div>
          <div className="node-meta">
            <span className="app-label jsm">JSM Ticket</span>
            <span>1 week ago</span>
          </div>
          <h4 className="node-title">ACC-4471: Account Issue</h4>
          <QuoteBlock>"I was charged twice."</QuoteBlock>
        </div>
      </div>
    </div>
  );
}

function ProvenanceSidebar({ verdict }) {
  const content = VERDICT_CONTENT[verdict];

  return (
    <aside className="prov-sidebar">
      <div className="prov-header">
        <h2>
          <ProvenanceIcon />
          Provenance
        </h2>
        <span className={`lozenge ${content.badgeClass}`}>{content.badgeText}</span>
      </div>

      <div className="prov-body">
        <div className={`section-message ${content.messageClass}`}>
          <div className="sm-title">
            <VerdictIcon type={content.icon} />
            {content.title}
          </div>
          <p className="hero-rationale">{content.rationale}</p>
        </div>

        {verdict === "drift" && <DriftState />}
        {verdict === "no-evidence" && <NoEvidenceState />}
        {verdict === "aligned" && <AlignedState />}
      </div>
    </aside>
  );
}

function HackathonConsole({ setVerdict }) {
  return (
    <div className="demo-console">
      <h4>Hackathon Console</h4>
      <button
        type="button"
        className="demo-btn"
        onClick={() => setVerdict("aligned")}
      >
        🟢 Simulate Aligned
      </button>
      <button
        type="button"
        className="demo-btn"
        onClick={() => setVerdict("drift")}
      >
        🔴 Simulate Drift
      </button>
      <button
        type="button"
        className="demo-btn"
        onClick={() => setVerdict("no-evidence")}
      >
        🟡 Simulate No Evidence
      </button>
    </div>
  );
}

export default function App() {
  const [verdict, setVerdict] = useState("drift");

  return (
    <div className="provenance-page">
      <style>{styles}</style>
      <JiraTopNav />
      <div className="app-container">
        <ProjectSidebar />
        <IssueWorkspace />
        <ProvenanceSidebar verdict={verdict} />
      </div>
      <HackathonConsole setVerdict={setVerdict} />
    </div>
  );
}

const styles = `
  :root {
    --color-text: #172B4D;
    --color-text-subtle: #6B778C;
    --color-text-subtlest: #505F79;
    --color-link: #0C66E4;
    --color-bg-page: #FFFFFF;
    --color-bg-surface: #FFFFFF;
    --color-bg-sunken: #F4F5F7;
    --color-bg-sidebar: #FAFBFC;
    --color-border: #DFE1E6;
    --jira-blue: #0C66E4;
    --conf-purple: #6554C0;
    --jsm-green: #1F845A;
    --loz-success-bg: #E3FCEF;
    --loz-success-text: #064E3B;
    --loz-danger-bg: #FFEBE6;
    --loz-danger-text: #BF2600;
    --loz-warning-bg: #FFFAE6;
    --loz-warning-text: #A05E03;
    --loz-default-bg: #DFE1E6;
    --loz-default-text: #42526E;
    --loz-inprogress-bg: #DEEBFF;
    --loz-inprogress-text: #0747A6;
    --elevation-1: 0 1px 1px rgba(9, 30, 66, 0.25), 0 0 1px rgba(9, 30, 66, 0.31);
    --elevation-shadow-side: -2px 0 8px rgba(9, 30, 66, 0.08);
  }

  html,
  body,
  #root {
    min-height: 100%;
    margin: 0;
  }

  * {
    box-sizing: border-box;
  }

  .provenance-page {
    min-height: 100vh;
    height: 100vh;
    overflow: hidden;
    background-color: var(--color-bg-page);
    color: var(--color-text);
    display: flex;
    flex-direction: column;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 14px;
  }

  button,
  input {
    font: inherit;
  }

  .jira-top-nav {
    height: 56px;
    background-color: var(--color-bg-surface);
    border-bottom: 1px solid var(--color-border);
    display: flex;
    align-items: center;
    padding: 0 16px;
    gap: 24px;
    flex-shrink: 0;
    z-index: 100;
  }

  .jira-logo {
    font-size: 20px;
    font-weight: bold;
    color: var(--jira-blue);
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .jira-nav-links {
    display: flex;
    gap: 16px;
    font-weight: 500;
    color: var(--color-text-subtlest);
  }

  .jira-nav-links span {
    cursor: pointer;
    padding: 6px 8px;
    border-radius: 3px;
  }

  .jira-nav-links span:hover {
    background-color: rgba(9, 30, 66, 0.08);
  }

  .jira-nav-right {
    margin-left: auto;
    display: flex;
    gap: 16px;
    align-items: center;
  }

  .atl-create-btn {
    background-color: var(--jira-blue);
    color: white;
    border: none;
    padding: 0 12px;
    height: 32px;
    border-radius: 3px;
    font-weight: 500;
    cursor: pointer;
  }

  .atl-create-btn:hover {
    background-color: #0052CC;
  }

  .profile-avatar {
    width: 28px;
    height: 28px;
    background: #DFE1E6;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: bold;
  }

  .app-container {
    display: flex;
    flex-grow: 1;
    overflow: hidden;
  }

  .project-sidebar {
    width: 240px;
    background-color: var(--color-bg-sidebar);
    border-right: 1px solid var(--color-border);
    padding: 24px 16px;
    flex-shrink: 0;
  }

  .project-header {
    display: flex;
    gap: 12px;
    align-items: center;
    margin-bottom: 24px;
  }

  .project-icon {
    width: 32px;
    height: 32px;
    background: #FFAB00;
    border-radius: 3px;
  }

  .project-title h3 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
  }

  .project-title p {
    margin: 0;
    font-size: 12px;
    color: var(--color-text-subtle);
  }

  .sidebar-menu-item {
    padding: 8px 12px;
    color: var(--color-text-subtlest);
    border-radius: 3px;
    cursor: pointer;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .sidebar-menu-item:hover {
    background-color: rgba(9, 30, 66, 0.04);
  }

  .sidebar-menu-item.active {
    background-color: #E9F2FF;
    color: var(--jira-blue);
    font-weight: 500;
  }

  .sidebar-section-label {
    margin: 24px 0 8px 12px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    color: var(--color-text-subtlest);
  }

  .issue-workspace {
    flex-grow: 1;
    padding: 32px 440px 32px 40px;
    overflow-y: auto;
  }

  .breadcrumbs {
    font-size: 14px;
    color: var(--color-text-subtle);
    margin-bottom: 16px;
  }

  .breadcrumbs span {
    color: var(--color-text-subtlest);
  }

  .breadcrumbs a {
    color: var(--color-text-subtle);
    text-decoration: none;
  }

  .breadcrumbs a:hover {
    text-decoration: underline;
  }

  .issue-title {
    font-size: 24px;
    font-weight: 500;
    margin: 0 0 24px;
    color: var(--color-text);
  }

  .issue-action-bar {
    display: flex;
    gap: 8px;
    margin-bottom: 32px;
  }

  .atl-button-secondary {
    background: rgba(9, 30, 66, 0.04);
    border: none;
    padding: 6px 12px;
    border-radius: 3px;
    color: #42526E;
    font-weight: 500;
    cursor: pointer;
  }

  .atl-button-secondary:hover {
    background: rgba(9, 30, 66, 0.08);
  }

  .issue-grid {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 40px;
  }

  .field-group h4 {
    font-size: 14px;
    color: var(--color-text-subtlest);
    margin: 0 0 8px;
    font-weight: 600;
  }

  .field-group p {
    margin: 0 0 24px;
    line-height: 1.6;
  }

  .field-value {
    color: var(--color-text);
  }

  .activity-section {
    margin-top: 40px;
    border-top: 1px solid var(--color-border);
    padding-top: 24px;
  }

  .activity-tabs {
    display: flex;
    gap: 16px;
    border-bottom: 1px solid var(--color-border);
    margin-bottom: 16px;
    padding-bottom: 8px;
    color: var(--color-text-subtlest);
    font-weight: 500;
  }

  .activity-tab-active {
    color: var(--jira-blue);
    border-bottom: 2px solid var(--jira-blue);
  }

  .comment-row {
    display: flex;
    gap: 12px;
    align-items: flex-start;
  }

  .comment-avatar {
    width: 32px;
    height: 32px;
    background: #DFE1E6;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .comment-input-wrapper input {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--color-border);
    border-radius: 3px;
    outline: none;
  }

  .person-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .person-avatar {
    width: 24px;
    height: 24px;
    border-radius: 50%;
  }

  .person-avatar.neutral {
    background: #DFE1E6;
  }

  .person-avatar.reporter {
    background: #36B37E;
  }

  .labels-empty {
    color: var(--color-text-subtlest);
  }

  .prov-sidebar {
    width: 400px;
    height: calc(100vh - 56px);
    background-color: var(--color-bg-surface);
    box-shadow: var(--elevation-shadow-side);
    display: flex;
    flex-direction: column;
    position: fixed;
    right: 0;
    top: 56px;
    z-index: 50;
    border-left: 1px solid var(--color-border);
  }

  .prov-header {
    padding: 20px 24px;
    border-bottom: 2px solid var(--color-bg-sunken);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .prov-header h2 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .lozenge {
    border-radius: 3px;
    padding: 2px 4px 3px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    line-height: 1;
  }

  .lozenge.danger {
    background: var(--loz-danger-bg);
    color: var(--loz-danger-text);
  }

  .lozenge.success {
    background: var(--loz-success-bg);
    color: var(--loz-success-text);
  }

  .lozenge.warning {
    background: var(--loz-warning-bg);
    color: var(--loz-warning-text);
  }

  .lozenge.default {
    background: var(--loz-default-bg);
    color: var(--loz-default-text);
  }

  .lozenge.inprogress {
    background: var(--loz-inprogress-bg);
    color: var(--loz-inprogress-text);
  }

  .prov-body {
    padding: 24px;
    overflow-y: auto;
    flex-grow: 1;
  }

  .section-message {
    border-radius: 3px;
    padding: 16px;
    margin-bottom: 24px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .sm-danger {
    background-color: var(--loz-danger-bg);
  }

  .sm-warning {
    background-color: var(--loz-warning-bg);
  }

  .sm-success {
    background-color: var(--loz-success-bg);
  }

  .sm-title {
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .hero-rationale {
    margin: 0;
    font-size: 13px;
  }

  .timeline {
    position: relative;
    padding-left: 20px;
    margin-left: 4px;
  }

  .timeline::before {
    content: "";
    position: absolute;
    top: 24px;
    bottom: 0;
    left: 5px;
    width: 2px;
    background-color: var(--color-border);
    z-index: 0;
  }

  .node {
    position: relative;
    margin-bottom: 32px;
    background: var(--color-bg-surface);
    border-radius: 3px;
    padding: 16px;
    box-shadow: var(--elevation-1);
    z-index: 1;
  }

  .node::before {
    content: "";
    position: absolute;
    left: -19.5px;
    top: 20px;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: white;
    border: 2px solid;
    z-index: 2;
  }

  .node.jsm::before {
    border-color: var(--jsm-green);
  }

  .node.conf::before {
    border-color: var(--conf-purple);
  }

  .node.jira::before {
    border-color: var(--jira-blue);
  }

  .node-meta {
    font-size: 12px;
    color: var(--color-text-subtlest);
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .app-label {
    font-weight: 600;
  }

  .app-label.jsm {
    color: var(--jsm-green);
  }

  .app-label.conf {
    color: var(--conf-purple);
  }

  .app-label.jira {
    color: var(--jira-blue);
  }

  .node-title {
    font-size: 14px;
    font-weight: 500;
    margin: 0 0 12px;
  }

  .quote-block {
    width: 100%;
    background-color: var(--color-bg-page);
    border-radius: 3px;
    padding: 10px 12px;
    cursor: pointer;
    border: 1px solid var(--color-border);
    text-align: left;
  }

  .quote-block:hover {
    background-color: var(--color-bg-sunken);
  }

  .quote-button {
    display: block;
    color: inherit;
  }

  .quote-text {
    margin: 0;
    font-size: 13px;
    color: var(--color-text-subtle);
    font-style: italic;
  }

  .quote-text mark {
    background-color: #FFE380;
    color: var(--color-text);
    padding: 2px 4px;
    border-radius: 3px;
    font-style: normal;
  }

  .full-text {
    display: none;
    margin-top: 8px;
    font-style: normal;
    color: var(--color-text);
  }

  .full-text.visible {
    display: block;
    margin-top: 0;
  }

  .edge-badge-container {
    position: absolute;
    left: -46px;
    top: -24px;
    background: var(--color-bg-surface);
    padding: 4px 0;
  }

  .local-drift {
    margin-top: 16px;
    padding-left: 12px;
    border-left: 2px solid var(--loz-danger-text);
    font-size: 13px;
    color: var(--color-text-subtle);
  }

  .local-drift strong {
    color: var(--color-text);
    display: block;
    margin-bottom: 4px;
  }

  .local-success {
    margin-top: 16px;
    padding-left: 12px;
    border-left: 2px solid var(--loz-success-text);
    font-size: 13px;
    color: var(--color-text-subtle);
  }

  .local-success strong {
    color: var(--loz-success-text);
    display: block;
    margin-bottom: 4px;
  }

  .state-view {
    display: none;
  }

  .state-view.active {
    display: block;
  }

  .no-evidence-actions {
    margin-top: 16px;
    display: flex;
    gap: 8px;
  }

  /* Floating Hackathon Demo Console — kept visually unchanged. */
  .demo-console {
    position: fixed;
    bottom: 24px;
    left: 24px;
    background: #172B4D;
    color: white;
    padding: 16px;
    border-radius: 6px;
    box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2);
    z-index: 1000;
    width: 220px;
  }

  .demo-console h4 {
    margin: 0 0 12px 0;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #8993A4;
  }

  .demo-btn {
    display: block;
    width: 100%;
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
    color: white;
    padding: 8px;
    border-radius: 3px;
    margin-bottom: 8px;
    cursor: pointer;
    text-align: left;
    font-size: 13px;
  }

  .demo-btn:hover {
    background: rgba(255, 255, 255, 0.2);
  }

  @media (max-width: 1100px) {
    .jira-nav-links {
      display: none;
    }

    .project-sidebar {
      width: 200px;
    }

    .issue-workspace {
      padding-left: 24px;
    }
  }
`;
