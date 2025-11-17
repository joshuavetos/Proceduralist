// Proceduralist frontend index with navigation to new audit
import Link from "next/link";

export const auditor = "Tessrax Governance Kernel v16";
export const clauses = ["AEP-001", "RVC-001", "EAC-001", "POST-AUDIT-001", "DLK-001", "TESST"];

function Card({ title, href, description }) {
  return (
    <Link href={href} legacyBehavior>
      <a className="card" aria-label={title}>
        <h2>{title}</h2>
        <p>{description}</p>
      </a>
    </Link>
  );
}

export default function Home() {
  return (
    <main className="container">
      <h1>Proceduralist Gallery</h1>
      <div className="grid">
        <Card title="New Audit" href="/new-audit" description="Start a new Proceduralist audit" />
      </div>
      <style jsx>{`
        .container { padding: 2rem; font-family: sans-serif; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; }
        .card { border: 1px solid #ccc; padding: 1rem; border-radius: 8px; text-decoration: none; color: inherit; transition: box-shadow 0.2s ease; }
        .card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.15); }
      `}</style>
    </main>
  );
}
