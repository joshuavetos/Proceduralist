import Link from "next/link";

const solutions = [
  "Broken link structures",
  "Contradictory UX flows",
  "Policy-compliance drift",
  "Accessibility inconsistencies",
  "Content-governance violations",
  "SEO entropy",
  "Structure decay of websites",
];

export default function WhatItSolves() {
  return (
    <main className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">Proceduralist</p>
          <h1>What Proceduralist Solves</h1>
          <p className="lede">
            Turn sprawling websites into governed, consistent experiences. Proceduralist audits,
            reconciles, and reports on every contradiction before it reaches your users.
          </p>
          <div className="actions">
            <Link href="/new-audit" legacyBehavior>
              <a className="button primary">Try a demo audit</a>
            </Link>
            <Link href="/admin" legacyBehavior>
              <a className="button ghost">Manage audits</a>
            </Link>
          </div>
        </div>
        <div className="callout" aria-label="Solution summary">
          <p className="callout-title">Built for reliability</p>
          <p className="callout-copy">
            Deterministic crawling, queue-safe execution, and export-ready reporting keep every audit
            reproducible and customer-ready.
          </p>
        </div>
      </header>

      <section className="grid">
        {solutions.map((item) => (
          <div key={item} className="card">
            <h2>{item}</h2>
            <p>
              Proceduralist maps the site graph, runs deterministic analyzers, and produces PDF and
              JSON receipts so you can fix issues with confidence.
            </p>
          </div>
        ))}
      </section>

      <section className="cta">
        <div>
          <h2>Ready to ship a cleaner site?</h2>
          <p>
            Start a crawl, watch the graph render, and download exportable reports in one flow.
          </p>
        </div>
        <div className="actions">
          <Link href="/new-audit" legacyBehavior>
            <a className="button primary">Launch an audit</a>
          </Link>
          <Link href="/admin" legacyBehavior>
            <a className="button ghost">Manage audits</a>
          </Link>
        </div>
      </section>

      <style jsx>{`
        .page {
          padding: 2.5rem 1.75rem 3rem;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          color: #0f172a;
          background: linear-gradient(180deg, #f8fafc 0%, #ffffff 20%);
        }

        .hero {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
          gap: 1.5rem;
          align-items: center;
          margin-bottom: 2rem;
        }

        .eyebrow {
          text-transform: uppercase;
          letter-spacing: 0.08em;
          font-weight: 700;
          font-size: 0.8rem;
          color: #2563eb;
          margin: 0 0 0.25rem;
        }

        h1 {
          margin: 0 0 0.6rem;
          font-size: clamp(2rem, 4vw, 2.6rem);
        }

        .lede {
          margin: 0 0 1rem;
          font-size: 1.05rem;
          line-height: 1.6;
          color: #1f2937;
        }

        .actions {
          display: flex;
          flex-wrap: wrap;
          gap: 0.75rem;
          margin-top: 0.5rem;
        }

        .button {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border-radius: 999px;
          padding: 0.75rem 1.25rem;
          font-weight: 600;
          text-decoration: none;
          border: 1px solid #2563eb;
        }

        .button.primary {
          background: #2563eb;
          color: #ffffff;
          box-shadow: 0 10px 25px rgba(37, 99, 235, 0.2);
        }

        .button.ghost {
          color: #2563eb;
          background: #e0ecff;
        }

        .callout {
          border: 1px solid #e5e7eb;
          border-radius: 12px;
          padding: 1rem 1.25rem;
          background: #ffffff;
          box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
        }

        .callout-title {
          margin: 0 0 0.35rem;
          font-weight: 700;
        }

        .callout-copy {
          margin: 0;
          color: #374151;
          line-height: 1.5;
        }

        .grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
          gap: 1rem;
          margin: 2rem 0 2.5rem;
        }

        .card {
          background: #ffffff;
          border: 1px solid #e5e7eb;
          border-radius: 12px;
          padding: 1rem 1.1rem;
          box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
        }

        .card h2 {
          margin: 0 0 0.4rem;
          font-size: 1.05rem;
        }

        .card p {
          margin: 0;
          color: #374151;
          line-height: 1.5;
        }

        .cta {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          justify-content: space-between;
          gap: 1rem;
          padding: 1.25rem 1.5rem;
          background: #0f172a;
          color: #e5e7eb;
          border-radius: 14px;
          box-shadow: 0 16px 36px rgba(0, 0, 0, 0.25);
        }

        .cta h2 {
          margin: 0 0 0.35rem;
          color: #ffffff;
        }

        .cta p {
          margin: 0;
          max-width: 520px;
          color: #cbd5e1;
        }

        @media (max-width: 640px) {
          .actions {
            width: 100%;
          }

          .cta {
            flex-direction: column;
            align-items: flex-start;
          }
        }
      `}</style>
    </main>
  );
}
