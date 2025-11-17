import Link from "next/link";
import { useRouter } from "next/router";
import { useEffect, useMemo, useState } from "react";

export const auditor = "Tessrax Governance Kernel v16";
export const clauses = ["AEP-001", "RVC-001", "EAC-001", "POST-AUDIT-001", "DLK-001", "TESST"];

export default function GalleryEntry() {
  const router = useRouter();
  const { id } = router.query;
  const [graph, setGraph] = useState({ nodes: [], edges: [] });
  const [summary, setSummary] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState(null);
  const [actionMessage, setActionMessage] = useState(null);
  const [crawlTitle, setCrawlTitle] = useState("");
  const [crawlUrl, setCrawlUrl] = useState("");
  const [queueSnapshot, setQueueSnapshot] = useState(null);

  useEffect(() => {
    if (!id) return;
    const load = async () => {
      try {
        setError(null);
        const [graphResponse, summaryResponse] = await Promise.all([
          fetch(`/api/graph/${id}`),
          fetch(`/api/summary/${id}`),
        ]);

        if (!graphResponse.ok) {
          const detail = await graphResponse.text();
          throw new Error(detail || "Graph fetch failed");
        }
        if (!summaryResponse.ok) {
          const detail = await summaryResponse.text();
          throw new Error(detail || "Summary fetch failed");
        }

        const graphPayload = await graphResponse.json();
        const summaryPayload = await summaryResponse.json();
        setGraph(graphPayload);
        setSummary(summaryPayload);
        setCrawlTitle(summaryPayload.title || "");
        setCrawlUrl(summaryPayload.start_url || "");
      } catch (err) {
        setError(err.message);
      }
    };
    load();
    const interval = setInterval(load, 6000);
    return () => clearInterval(interval);
  }, [id]);

  useEffect(() => {
    const loadQueue = async () => {
      try {
        const response = await fetch("/api/queue/status");
        if (!response.ok) {
          const detail = await response.text();
          throw new Error(detail || "Queue status fetch failed");
        }
        const payload = await response.json();
        setQueueSnapshot(payload);
      } catch (err) {
        setError(err.message);
      }
    };
    loadQueue();
    const interval = setInterval(loadQueue, 10000);
    return () => clearInterval(interval);
  }, []);

  const nodeDegrees = useMemo(() => {
    const degrees = {};
    graph.edges.forEach((edge) => {
      const fromId = edge.from_node_id;
      const toId = edge.to_node_id;
      if (fromId) degrees[fromId] = (degrees[fromId] || 0) + 1;
      if (toId) degrees[toId] = (degrees[toId] || 0) + 1;
    });
    return degrees;
  }, [graph.edges]);

  const progressFor = (status, nodes, edges) => {
    const stage = {
      draft: 0.05,
      queued: 0.15,
      running: 0.55,
      published: 1,
      failed: 1,
      archived: 1,
    };
    const base = stage[status] ?? 0;
    const momentum = Math.min(0.35, (nodes + edges) * 0.01);
    return Math.min(1, base + momentum);
  };

  const runAnalysis = async () => {
    if (!id) return;
    try {
      setError(null);
      setActionMessage("Running analysis…");
      const response = await fetch(`/api/analyze/full/${id}`, { method: "POST" });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || "Analysis failed");
      }
      const payload = await response.json();
      setAnalysis(payload);
      setActionMessage("Analysis completed deterministically.");
    } catch (err) {
      setError(err.message);
      setActionMessage(null);
    }
  };

  const triggerCrawl = async (event) => {
    event.preventDefault();
    try {
      setError(null);
      setActionMessage("Starting crawl…");
      const response = await fetch("/api/audit/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: crawlTitle, start_url: crawlUrl }),
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || "Crawl start failed");
      }
      const payload = await response.json();
      if (!payload.id) {
        throw new Error("Backend did not return a crawl id");
      }
      setActionMessage(`Crawl queued with id ${payload.id}.`);
    } catch (err) {
      setError(err.message);
      setActionMessage(null);
    }
  };

  return (
    <main className="container">
      <header className="header">
        <div>
          <p className="eyebrow">Audit Dashboard</p>
          <h1>Audit #{id}</h1>
          {summary && (
            <p className="muted">{summary.title} — {summary.start_url}</p>
          )}
        </div>
        <Link href="/new-audit">Start another crawl</Link>
      </header>

      {error && <p className="error">{error}</p>}
      {actionMessage && <p className="info">{actionMessage}</p>}

      {summary && (
        <section className="panel">
          <div className="panel-header">
            <h2>Summary</h2>
            <span className={`status status-${summary.status}`}>{summary.status}</span>
          </div>
          <div className="progress-row">
            <div className="progress">
              <div
                className="progress-fill"
                style={{ width: `${Math.round(progressFor(summary.status, summary.nodes, summary.edges) * 100)}%` }}
              />
            </div>
            <p className="muted small">Live progress updates while the crawl runs.</p>
          </div>
          <div className="metrics">
            <div>
              <p className="metric-label">Nodes</p>
              <p className="metric-value">{summary.nodes}</p>
            </div>
            <div>
              <p className="metric-label">Edges</p>
              <p className="metric-value">{summary.edges}</p>
            </div>
            <div>
              <p className="metric-label">Contradictions</p>
              <p className="metric-value">{summary.contradictions}</p>
            </div>
            <div>
              <p className="metric-label">Severity</p>
              <p className="metric-value">{summary.severity_score ?? "—"}</p>
            </div>
            <div>
              <p className="metric-label">Entropy</p>
              <p className="metric-value">{summary.entropy_score ?? "—"}</p>
            </div>
            <div>
              <p className="metric-label">Integrity</p>
              <p className="metric-value">{summary.integrity_score ?? "—"}</p>
            </div>
          </div>
          <div className="export-row">
            <a href={`/api/store/download/${id}?format=json`} download>
              Download JSON export
            </a>
            <a href={`/api/store/download/${id}?format=pdf`} download>
              Download PDF export
            </a>
          </div>
        </section>
      )}

      {queueSnapshot && (
        <section className="panel">
          <div className="panel-header">
            <h2>Queue status</h2>
            <p className="muted">Depth: {queueSnapshot.queue_depth}</p>
          </div>
          <div className="status-grid">
            {Object.entries(queueSnapshot.status_totals || {}).map(([status, count]) => (
              <div key={status} className="card-inline">
                <p className="metric-label">{status}</p>
                <p className="metric-value">{count}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="panel">
        <div className="panel-header">
          <h2>Graph</h2>
          <button onClick={() => router.replace(router.asPath)}>Refresh</button>
        </div>
        {graph.nodes.length === 0 ? (
          <p className="muted">Graph not ready yet.</p>
        ) : (
          <div className="grid">
            <div>
              <h3>Nodes</h3>
              <ul className="list">
                {graph.nodes.map((node) => (
                  <li key={node.id} className="card">
                    <div className="card-title">
                      <strong>{node.title || node.url}</strong>
                      {node.contradiction_type && (
                        <span className="badge">{node.contradiction_type}</span>
                      )}
                    </div>
                    <p className="muted">{node.url}</p>
                    <p className="muted">Connections: {nodeDegrees[node.id] || 0}</p>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3>Edges</h3>
              <ul className="list">
                {graph.edges.map((edge) => (
                  <li key={edge.id} className="card">
                    <p>
                      {edge.from_node_id} → {edge.to_node_id || "terminal"}
                    </p>
                    <p className="muted">Action: {edge.action_label}</p>
                    {edge.contradiction_type && (
                      <span className="badge">{edge.contradiction_type}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>Analysis</h2>
          <button onClick={runAnalysis}>Run analysis</button>
        </div>
        {analysis ? (
          <div className="analysis-grid">
            <div className="card">
              <h3>Links</h3>
              <pre>{JSON.stringify(analysis.links, null, 2)}</pre>
            </div>
            <div className="card">
              <h3>Accessibility</h3>
              <pre>{JSON.stringify(analysis.a11y, null, 2)}</pre>
            </div>
            <div className="card">
              <h3>Performance</h3>
              <pre>{JSON.stringify(analysis.perf, null, 2)}</pre>
            </div>
          </div>
        ) : (
          <p className="muted">No analysis has been run for this crawl yet.</p>
        )}
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>Trigger new crawl</h2>
          <p className="muted">Start a new crawl directly from the dashboard.</p>
        </div>
        <form onSubmit={triggerCrawl} className="form">
          <label>
            Title
            <input
              value={crawlTitle}
              onChange={(e) => setCrawlTitle(e.target.value)}
              required
              aria-label="Crawl title"
            />
          </label>
          <label>
            Start URL
            <input
              type="url"
              value={crawlUrl}
              onChange={(e) => setCrawlUrl(e.target.value)}
              required
              placeholder="https://example.com"
              aria-label="Start URL"
            />
          </label>
          <button type="submit">Start crawl</button>
        </form>
      </section>

      <style jsx>{`
        .container { padding: 2rem; font-family: sans-serif; display: grid; gap: 1.5rem; }
        .header { display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; flex-wrap: wrap; }
        .eyebrow { text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.8rem; color: #555; margin: 0; }
        .muted { color: #555; margin: 0.25rem 0; }
        .error { color: #b00020; }
        .info { color: #0a5596; }
        .panel { border: 1px solid #e0e0e0; border-radius: 8px; padding: 1rem; background: #fafafa; }
        .panel-header { display: flex; justify-content: space-between; align-items: center; gap: 1rem; }
        .status { padding: 0.25rem 0.6rem; border-radius: 999px; font-size: 0.85rem; text-transform: capitalize; }
        .status-published { background: #e6f4ea; color: #0f5132; }
        .status-running { background: #fff4e5; color: #7a4f0f; }
        .status-queued { background: #e7f1ff; color: #0a3f8f; }
        .status-draft { background: #f4f4f4; color: #333; }
        .status-failed { background: #fde7e9; color: #a1161a; }
        .status-archived { background: #f4f4f4; color: #333; }
        .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 0.75rem; margin-top: 1rem; }
        .metric-label { color: #666; margin: 0; font-size: 0.9rem; }
        .metric-value { margin: 0.1rem 0 0; font-weight: 700; }
        .progress-row { display: grid; gap: 0.3rem; margin-top: 0.75rem; }
        .progress { height: 10px; background: #eef2f7; border-radius: 999px; overflow: hidden; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #0f6abf, #00a2ff); }
        .small { font-size: 0.9rem; }
        .export-row { display: flex; gap: 1rem; margin-top: 1rem; flex-wrap: wrap; }
        .export-row a { color: #0f6abf; text-decoration: none; font-weight: 600; }
        .export-row a:hover { text-decoration: underline; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; }
        .list { list-style: none; padding: 0; display: grid; gap: 0.75rem; }
        .card { border: 1px solid #e0e0e0; border-radius: 6px; padding: 0.75rem; background: white; }
        .card-title { display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; }
        .badge { margin-left: 0.5rem; padding: 0.1rem 0.4rem; background: #ffe6e6; border: 1px solid #f5b5b5; border-radius: 4px; }
        .card-inline { border: 1px solid #e0e0e0; border-radius: 6px; padding: 0.75rem; background: white; }
        button { padding: 0.5rem 1rem; background: #0f6abf; color: white; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #0a5596; }
        .analysis-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; }
        pre { background: #1d1f21; color: #c9d1d9; padding: 0.75rem; border-radius: 6px; overflow-x: auto; }
        .form { display: grid; gap: 0.75rem; margin-top: 1rem; }
        label { display: grid; gap: 0.25rem; font-weight: 600; }
        input { padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; }
      `}</style>
    </main>
  );
}
