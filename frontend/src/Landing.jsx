const features = [
  {
    title: "Deterministic Replay",
    description:
      "Bit-for-bit reenactments of every ledger step so regulators can trace decisions without drift.",
  },
  {
    title: "Contradiction Detection",
    description:
      "Continuous checks for policy clashes, stale inputs, and hidden divergences before they ship.",
  },
  {
    title: "Legal-Grade Receipts",
    description:
      "Cryptographically signed evidence packages with timestamps, hashes, and provenance lineage.",
  },
];

export default function Landing({ onEnter }) {
  return (
    <div className="landing-shell">
      <header className="nav">
        <div className="brand">The Truth Warehouse</div>
        <button className="nav-button" onClick={onEnter} aria-label="Enter live demo">
          Enter App
        </button>
      </header>

      <main className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Automated Forensic Auditing</p>
          <h1>The Truth Warehouse.</h1>
          <p className="subhead">
            Automated forensic auditing for compliance teams. Catch drift before the regulators do.
          </p>
          <button className="cta" onClick={onEnter} aria-label="Try live demo">
            Try Live Demo
          </button>
        </div>
        <div className="hero-panel">
          <div className="panel-heading">Proof Stack</div>
          <ul className="panel-list">
            <li>Deterministic timelines</li>
            <li>Live contradiction alarms</li>
            <li>Receipt lineage with hashes</li>
            <li>Cold-start reproducibility reports</li>
          </ul>
        </div>
      </main>

      <section className="features" aria-label="Feature highlights">
        {features.map((feature) => (
          <article key={feature.title} className="feature-card">
            <h3>{feature.title}</h3>
            <p>{feature.description}</p>
          </article>
        ))}
      </section>
    </div>
  );
}
