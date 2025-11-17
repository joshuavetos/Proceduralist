import { useEffect, useState } from "react";

export const auditor = "Tessrax Governance Kernel v16";
export const clauses = ["AEP-001", "RVC-001", "EAC-001", "POST-AUDIT-001", "DLK-001", "TESST"];

export default function Storefront() {
  const [maps, setMaps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const load = async () => {
      try {
        const response = await fetch("/api/maps?status=published");
        if (!response.ok) throw new Error("Failed to load published maps");
        const payload = await response.json();
        setMaps(payload);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const startCheckout = async (mapId) => {
    try {
      setError(null);
      const response = await fetch("/api/store/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ map_id: mapId }),
      });
      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || "Checkout failed");
      }
      const payload = await response.json();
      window.location.href = payload.url;
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <main className="container">
      <h1>Proceduralist Store</h1>
      {error && <p className="error">{error}</p>}
      {loading ? (
        <p>Loading published audits…</p>
      ) : maps.length === 0 ? (
        <p>No published maps available.</p>
      ) : (
        <ul className="grid">
          {maps.map((map) => (
            <li key={map.id} className="card">
              <h3>{map.title}</h3>
              <p className="muted">Start URL: {map.start_url}</p>
              <button onClick={() => startCheckout(map.id)}>Buy Export</button>
            </li>
          ))}
        </ul>
      )}
      <style jsx>{`
        .container { padding: 2rem; font-family: sans-serif; }
        .grid { list-style: none; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; }
        .card { border: 1px solid #e0e0e0; padding: 1rem; border-radius: 8px; }
        .muted { color: #555; font-size: 0.9rem; }
        button { margin-top: 0.5rem; padding: 0.5rem 1rem; background: #0f6abf; color: white; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #0a5596; }
        .error { color: #b00020; }
      `}</style>
    </main>
  );
}
