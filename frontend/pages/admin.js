import { useEffect, useMemo, useState } from "react";

export const auditor = "Tessrax Governance Kernel v16";
export const clauses = ["AEP-001", "RVC-001", "EAC-001", "POST-AUDIT-001", "DLK-001", "TESST"];

function ProgressBar({ progress }) {
  const pct = Math.min(100, Math.max(0, Math.round(progress * 100)));
  return (
    <div className="progress">
      <div className="progress-fill" style={{ width: `${pct}%` }} />
      <span className="progress-label">{pct}%</span>
      <style jsx>{`
        .progress {
          position: relative;
          height: 12px;
          background: #eef2f7;
          border-radius: 999px;
          overflow: hidden;
        }
        .progress-fill {
          position: absolute;
          top: 0;
          left: 0;
          bottom: 0;
          background: linear-gradient(90deg, #0f6abf, #00a2ff);
          border-radius: 999px;
        }
        .progress-label {
          position: absolute;
          top: -18px;
          right: 0;
          font-size: 0.8rem;
          color: #333;
        }
      `}</style>
    </div>
  );
}

function StatusPill({ status }) {
  return <span className={`pill pill-${status}`}>{status}</span>;
}

export default function AdminPanel() {
  const [queueStatus, setQueueStatus] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [renameDrafts, setRenameDrafts] = useState({});
  const [actionMessage, setActionMessage] = useState(null);

  const loadQueue = async () => {
    try {
      setError(null);
      const response = await fetch("/api/queue/status");
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || "Failed to load queue status");
      }
      const payload = await response.json();
      setQueueStatus(payload);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadQueue();
    const interval = setInterval(loadQueue, 8000);
    return () => clearInterval(interval);
  }, []);

  const statusTotals = useMemo(() => queueStatus?.status_totals || {}, [queueStatus]);

  const updateStatus = async (mapId, status) => {
    try {
      setError(null);
      setActionMessage(`Updating status to ${status}…`);
      const response = await fetch(`/api/maps/${mapId}/status?status=${status}`, {
        method: "PATCH",
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || "Status update failed");
      }
      await loadQueue();
      setActionMessage(`Status updated to ${status}.`);
    } catch (err) {
      setError(err.message);
      setActionMessage(null);
    }
  };

  const rename = async (mapId) => {
    try {
      const title = renameDrafts[mapId];
      if (!title) {
        throw new Error("Title is required to rename");
      }
      setActionMessage("Renaming map…");
      const response = await fetch(`/api/maps/${mapId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || "Rename failed");
      }
      await loadQueue();
      setActionMessage("Map renamed.");
    } catch (err) {
      setError(err.message);
      setActionMessage(null);
    }
  };

  const deleteMap = async (mapId) => {
    if (!confirm("Delete this map? This cannot be undone.")) {
      return;
    }
    try {
      setActionMessage("Deleting map…");
      const response = await fetch(`/api/maps/${mapId}`, { method: "DELETE" });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || "Delete failed");
      }
      await loadQueue();
      setActionMessage("Map deleted.");
    } catch (err) {
      setError(err.message);
      setActionMessage(null);
    }
  };

  const rerunAnalysis = async (mapId) => {
    try {
      setActionMessage("Re-running analysis…");
      const response = await fetch(`/api/analyze/full/${mapId}`, { method: "POST" });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || "Analysis rerun failed");
      }
      await loadQueue();
      setActionMessage("Analysis completed.");
    } catch (err) {
      setError(err.message);
      setActionMessage(null);
    }
  };

  const maps = queueStatus?.recent_maps || [];

  return (
    <main className="container">
      <header className="header">
        <div>
          <p className="eyebrow">Admin Controls</p>
          <h1>Operational Settings</h1>
          <p className="muted">Publish, archive, delete, rename, or re-run analyses.</p>
        </div>
      </header>

      {error && <p className="error">{error}</p>}
      {actionMessage && <p className="info">{actionMessage}</p>}

      <section className="panel">
        <div className="panel-header">
          <h2>Queue Snapshot</h2>
          <button onClick={loadQueue} disabled={loading}>Refresh</button>
        </div>
        {loading ? (
          <p className="muted">Loading queue status…</p>
        ) : queueStatus ? (
          <div className="status-grid">
            <div className="card">
              <p className="metric-label">Queue Depth</p>
              <p className="metric-value">{queueStatus.queue_depth}</p>
            </div>
            {Object.entries(statusTotals).map(([status, count]) => (
              <div key={status} className="card">
                <p className="metric-label">{status}</p>
                <p className="metric-value">{count}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="muted">No queue data available.</p>
        )}
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>Manage Maps</h2>
          <p className="muted">Publish/unpublish, archive, delete, rename, or re-run analysis.</p>
        </div>
        {maps.length === 0 ? (
          <p className="muted">No maps available.</p>
        ) : (
          <ul className="grid">
            {maps.map((map) => (
              <li key={map.id} className="card">
                <div className="card-header">
                  <div>
                    <h3>{map.title}</h3>
                    <p className="muted">{map.start_url}</p>
                  </div>
                  <StatusPill status={map.status} />
                </div>
                <ProgressBar progress={map.progress} />
                <p className="muted small">Nodes: {map.nodes} · Edges: {map.edges} · Contradictions: {map.contradictions}</p>
                <div className="actions">
                  <button onClick={() => updateStatus(map.id, "published")}>Publish</button>
                  <button onClick={() => updateStatus(map.id, "draft")}>Unpublish</button>
                  <button onClick={() => updateStatus(map.id, "archived")}>Archive</button>
                  <button onClick={() => rerunAnalysis(map.id)}>Re-run analysis</button>
                </div>
                <div className="actions">
                  <input
                    placeholder="Rename title"
                    value={renameDrafts[map.id] ?? ""}
                    onChange={(e) => setRenameDrafts({ ...renameDrafts, [map.id]: e.target.value })}
                  />
                  <button onClick={() => rename(map.id)}>Rename</button>
                  <button className="danger" onClick={() => deleteMap(map.id)}>Delete</button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <style jsx>{`
        .container { padding: 2rem; font-family: sans-serif; display: grid; gap: 1.5rem; }
        .header { display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; flex-wrap: wrap; }
        .eyebrow { text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.8rem; color: #555; margin: 0; }
        .muted { color: #555; margin: 0.25rem 0; }
        .small { font-size: 0.85rem; }
        .panel { border: 1px solid #e0e0e0; border-radius: 8px; padding: 1rem; background: #fafafa; }
        .panel-header { display: flex; justify-content: space-between; align-items: center; gap: 1rem; }
        .status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 0.75rem; }
        .card { border: 1px solid #e0e0e0; border-radius: 8px; padding: 0.75rem; background: white; display: grid; gap: 0.5rem; }
        .grid { list-style: none; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1rem; }
        .card-header { display: flex; justify-content: space-between; gap: 0.75rem; align-items: center; }
        .metric-label { color: #666; margin: 0; font-size: 0.9rem; }
        .metric-value { margin: 0.1rem 0 0; font-weight: 700; font-size: 1.4rem; }
        .actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 0.5rem; align-items: center; }
        button { padding: 0.5rem 0.75rem; background: #0f6abf; color: white; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #0a5596; }
        button:disabled { opacity: 0.5; cursor: not-allowed; }
        input { padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; width: 100%; }
        .danger { background: #a1161a; }
        .danger:hover { background: #7c0f14; }
        .pill { padding: 0.25rem 0.6rem; border-radius: 999px; font-size: 0.85rem; text-transform: capitalize; color: #0f6abf; background: #e7f1ff; }
        .pill-queued { background: #e7f1ff; color: #0a3f8f; }
        .pill-running { background: #fff4e5; color: #7a4f0f; }
        .pill-published { background: #e6f4ea; color: #0f5132; }
        .pill-draft { background: #f4f4f4; color: #333; }
        .pill-archived { background: #f4f4f4; color: #333; }
        .pill-failed { background: #fde7e9; color: #a1161a; }
        .error { color: #b00020; }
        .info { color: #0a5596; }
      `}</style>
    </main>
  );
}
