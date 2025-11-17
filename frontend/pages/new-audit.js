import { useRouter } from "next/router";
import { useEffect, useMemo, useState } from "react";

export const auditor = "Tessrax Governance Kernel v16";
export const clauses = ["AEP-001", "RVC-001", "EAC-001", "POST-AUDIT-001", "DLK-001", "TESST"];

export default function NewAudit() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [startUrl, setStartUrl] = useState("");
  const [error, setError] = useState(null);
  const [queueStatus, setQueueStatus] = useState(null);
  const [loadingQueue, setLoadingQueue] = useState(true);

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

  const loadQueue = async () => {
    try {
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
      setLoadingQueue(false);
    }
  };

  useEffect(() => {
    loadQueue();
    const interval = setInterval(loadQueue, 7000);
    return () => clearInterval(interval);
  }, []);

  const queueMaps = useMemo(() => queueStatus?.recent_maps || [], [queueStatus]);

  const submit = async (event) => {
    event.preventDefault();
    setError(null);
    try {
      const response = await fetch("/api/audit/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, start_url: startUrl }),
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || "Failed to start audit");
      }
      const payload = await response.json();
      if (!payload.id) {
        throw new Error("Invalid response from audit start endpoint");
      }
      await router.push(`/gallery/${payload.id}`);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <main className="container">
      <h1>Start New Audit</h1>
      <form onSubmit={submit} className="form">
        <label>
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} required />
        </label>
        <label>
          Start URL
          <input
            type="url"
            value={startUrl}
            onChange={(e) => setStartUrl(e.target.value)}
            required
            placeholder="https://example.com"
          />
        </label>
        <button type="submit">Start Audit</button>
      </form>
      {error && <p className="error">{error}</p>}
      <section className="panel">
        <div className="panel-header">
          <h2>Queue Status</h2>
          <button type="button" onClick={loadQueue} disabled={loadingQueue}>Refresh</button>
        </div>
        {loadingQueue ? (
          <p className="muted">Loading queue status…</p>
        ) : queueMaps.length === 0 ? (
          <p className="muted">No recent jobs.</p>
        ) : (
          <ul className="grid">
            {queueMaps.map((entry) => {
              const pct = Math.round(progressFor(entry.status, entry.nodes, entry.edges) * 100);
              return (
                <li key={entry.id} className="card">
                  <div className="card-header">
                    <div>
                      <h3>{entry.title}</h3>
                      <p className="muted">{entry.start_url}</p>
                    </div>
                    <span className={`pill pill-${entry.status}`}>{entry.status}</span>
                  </div>
                  <div className="progress">
                    <div className="progress-fill" style={{ width: `${pct}%` }} />
                  </div>
                  <p className="muted small">{pct}% · Nodes: {entry.nodes} · Edges: {entry.edges} · Contradictions: {entry.contradictions}</p>
                  <a href={`/gallery/${entry.id}`}>Open dashboard</a>
                </li>
              );
            })}
          </ul>
        )}
      </section>
      <style jsx>{`
        .container { padding: 2rem; font-family: sans-serif; max-width: 640px; margin: 0 auto; }
        .form { display: grid; gap: 1rem; }
        label { display: grid; gap: 0.5rem; font-weight: 600; }
        input { padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; }
        button { padding: 0.75rem 1.25rem; border: none; background: #0070f3; color: white; border-radius: 4px; cursor: pointer; }
        button:hover { background: #005bb5; }
        .error { color: #b00020; }
        .panel { border: 1px solid #e0e0e0; border-radius: 8px; padding: 1rem; margin-top: 1.5rem; background: #fafafa; }
        .panel-header { display: flex; justify-content: space-between; align-items: center; gap: 1rem; }
        .grid { list-style: none; padding: 0; display: grid; gap: 0.75rem; }
        .card { border: 1px solid #e0e0e0; border-radius: 8px; padding: 0.75rem; background: white; }
        .card-header { display: flex; justify-content: space-between; gap: 0.75rem; align-items: center; }
        .muted { color: #555; margin: 0.25rem 0; }
        .small { font-size: 0.9rem; }
        .progress { height: 10px; background: #eef2f7; border-radius: 999px; overflow: hidden; margin-top: 0.5rem; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #0f6abf, #00a2ff); }
        .pill { padding: 0.25rem 0.6rem; border-radius: 999px; font-size: 0.85rem; text-transform: capitalize; }
        .pill-queued { background: #e7f1ff; color: #0a3f8f; }
        .pill-running { background: #fff4e5; color: #7a4f0f; }
        .pill-published { background: #e6f4ea; color: #0f5132; }
        .pill-draft { background: #f4f4f4; color: #333; }
        .pill-archived { background: #f4f4f4; color: #333; }
        .pill-failed { background: #fde7e9; color: #a1161a; }
      `}</style>
    </main>
  );
}
