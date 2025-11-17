import Link from "next/link";
import { useRouter } from "next/router";
import { useEffect, useState } from "react";

export const auditor = "Tessrax Governance Kernel v16";
export const clauses = ["AEP-001", "RVC-001", "EAC-001", "POST-AUDIT-001", "DLK-001", "TESST"];

export default function StoreResult() {
  const router = useRouter();
  const { map_id: mapId, success, canceled } = router.query;
  const [message, setMessage] = useState("Awaiting checkout status…");
  const [mapDetails, setMapDetails] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (success) setMessage("Payment successful. Downloads are ready.");
    else if (canceled) setMessage("Checkout canceled. You can try again.");
    else setMessage("Complete checkout to access exports.");
  }, [success, canceled]);

  useEffect(() => {
    const loadMap = async () => {
      if (!mapId) return;
      try {
        setError(null);
        const response = await fetch("/api/maps");
        if (!response.ok) {
          const text = await response.text();
          throw new Error(text || "Unable to load map metadata");
        }
        const payload = await response.json();
        const found = payload.find((item) => String(item.id) === String(mapId));
        if (!found) throw new Error("Map not found or not published");
        setMapDetails(found);
      } catch (err) {
        setError(err.message);
      }
    };

    loadMap();
  }, [mapId]);

  return (
    <main className="container">
      <h1>Export for Map {mapId}</h1>
      {mapDetails && <p className="muted">{mapDetails.title}</p>}
      {error && <p className="error">{error}</p>}
      <p>{message}</p>
      {success && (
        <div className="downloads">
          <a href={`/api/store/download/${mapId}?format=json`}>Download JSON</a>
          <a href={`/api/store/download/${mapId}?format=pdf`}>Download PDF</a>
        </div>
      )}
      <p>
        <Link href="/store">Back to store</Link>
      </p>
      <style jsx>{`
        .container { padding: 2rem; font-family: sans-serif; }
        .downloads { display: flex; gap: 1rem; margin: 1rem 0; }
        .downloads a { color: #0f6abf; text-decoration: none; font-weight: 600; }
        .downloads a:hover { text-decoration: underline; }
        .muted { color: #555; }
        .error { color: #b00020; }
      `}</style>
    </main>
  );
}
