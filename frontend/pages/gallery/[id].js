import { useRouter } from "next/router";
import { useEffect, useState } from "react";

export const auditor = "Tessrax Governance Kernel v16";
export const clauses = ["AEP-001", "RVC-001", "EAC-001", "POST-AUDIT-001", "DLK-001", "TESST"];

export default function GalleryEntry() {
  const router = useRouter();
  const { id } = router.query;
  const [graph, setGraph] = useState({ nodes: [], edges: [] });
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!id) return;
    const load = async () => {
      try {
        const response = await fetch(`/api/graph/${id}`);
        if (!response.ok) throw new Error("Graph fetch failed");
        const payload = await response.json();
        setGraph(payload);
      } catch (err) {
        setError(err.message);
      }
    };
    load();
  }, [id]);

  return (
    <main className="container">
      <h1>Audit #{id}</h1>
      {error && <p className="error">{error}</p>}
      <section>
        <h2>Nodes</h2>
        <ul>
          {graph.nodes.map((node) => (
            <li key={node.id}>
              <strong>{node.title || node.url}</strong>
              {node.contradiction_type && (
                <span className="badge">{node.contradiction_type}</span>
              )}
            </li>
          ))}
        </ul>
      </section>
      <style jsx>{`
        .container { padding: 2rem; font-family: sans-serif; }
        .error { color: #b00020; }
        .badge { margin-left: 0.5rem; padding: 0.1rem 0.4rem; background: #ffe6e6; border: 1px solid #f5b5b5; border-radius: 4px; }
      `}</style>
    </main>
  );
}
