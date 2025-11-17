import { useRouter } from "next/router";
import { useState } from "react";

export const auditor = "Tessrax Governance Kernel v16";
export const clauses = ["AEP-001", "RVC-001", "EAC-001", "POST-AUDIT-001", "DLK-001", "TESST"];

export default function NewAudit() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [startUrl, setStartUrl] = useState("");
  const [error, setError] = useState(null);

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
      <style jsx>{`
        .container { padding: 2rem; font-family: sans-serif; max-width: 640px; margin: 0 auto; }
        .form { display: grid; gap: 1rem; }
        label { display: grid; gap: 0.5rem; font-weight: 600; }
        input { padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; }
        button { padding: 0.75rem 1.25rem; border: none; background: #0070f3; color: white; border-radius: 4px; cursor: pointer; }
        button:hover { background: #005bb5; }
        .error { color: #b00020; }
      `}</style>
    </main>
  );
}
