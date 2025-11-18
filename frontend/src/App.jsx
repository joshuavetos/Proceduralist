import { useMemo, useState } from "react";
import Link from "next/link";
import Landing from "./Landing";
import Footer from "./components/Footer";

function Dashboard() {
  const cards = useMemo(
    () => [
      {
        title: "New Audit",
        href: "/new-audit",
        description: "Start a new Proceduralist audit",
      },
      {
        title: "Admin Settings",
        href: "/admin",
        description: "Publish, archive, or delete audits",
      },
      {
        title: "What It Solves",
        href: "/what-it-solves",
        description: "See how Proceduralist resolves governance and UX drift",
      },
    ],
    [],
  );

  return (
    <div className="app-shell">
      <header className="nav">
        <div className="brand">Proceduralist</div>
        <nav className="nav-links">
          <Link href="/" legacyBehavior>
            <a className="nav-link" aria-label="Return home">
              Home
            </a>
          </Link>
          <Link href="/admin" legacyBehavior>
            <a className="nav-link" aria-label="Admin settings">
              Admin
            </a>
          </Link>
        </nav>
      </header>
      <main className="app-grid">
        <div className="intro">
          <h1>Proceduralist Gallery</h1>
          <p className="lede">
            Navigate directly to the tools you need to launch audits, administer maps, and explore how the governance stack works
            in practice.
          </p>
        </div>
        <div className="grid">
          {cards.map((card) => (
            <Link key={card.title} href={card.href} legacyBehavior>
              <a className="card" aria-label={card.title}>
                <h2>{card.title}</h2>
                <p>{card.description}</p>
              </a>
            </Link>
          ))}
        </div>
      </main>
      <Footer />
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState("landing");

  if (page === "landing") {
    return (
      <div className="page">
        <Landing onEnter={() => setPage("app")} />
        <Footer />
        <style jsx>{styles}</style>
      </div>
    );
  }

  return (
    <div className="page">
      <Dashboard />
      <style jsx>{styles}</style>
    </div>
  );
}

const styles = `
  :global(body) {
    margin: 0;
    background: radial-gradient(circle at 10% 20%, rgba(0, 189, 255, 0.12), transparent 25%),
      radial-gradient(circle at 80% 0%, rgba(111, 66, 193, 0.12), transparent 25%),
      #0b1528;
    color: #e8eef9;
    font-family: "Inter", system-ui, -apple-system, sans-serif;
    min-height: 100vh;
  }

  .page {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  .landing-shell,
  .app-shell {
    flex: 1;
    padding: 48px 56px 32px;
    background: linear-gradient(135deg, rgba(14, 26, 47, 0.8), rgba(11, 21, 40, 0.92));
    backdrop-filter: blur(12px);
  }

  .nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 0;
    position: sticky;
    top: 0;
    z-index: 10;
    background: rgba(11, 21, 40, 0.75);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  }

  .brand {
    font-weight: 700;
    letter-spacing: 0.02em;
    color: #9ecbff;
  }

  .nav-links {
    display: flex;
    gap: 16px;
    align-items: center;
  }

  .nav-link,
  .nav-button {
    color: #e8eef9;
    text-decoration: none;
    padding: 10px 16px;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: rgba(255, 255, 255, 0.05);
    transition: all 160ms ease;
    cursor: pointer;
  }

  .nav-button {
    font-weight: 600;
  }

  .nav-link:hover,
  .nav-button:hover,
  .cta:hover {
    border-color: rgba(255, 255, 255, 0.2);
    background: rgba(255, 255, 255, 0.12);
  }

  .hero {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 28px;
    align-items: center;
    margin-top: 32px;
  }

  .hero-copy h1 {
    font-size: clamp(2.6rem, 4vw, 3.5rem);
    margin: 12px 0;
  }

  .subhead {
    color: #c2d4f6;
    line-height: 1.6;
    max-width: 640px;
    margin-bottom: 18px;
  }

  .cta {
    padding: 14px 22px;
    font-weight: 700;
    border-radius: 14px;
    background: linear-gradient(120deg, #1a83ff, #23d1ff);
    border: none;
    color: #0b1528;
    cursor: pointer;
    box-shadow: 0 10px 30px rgba(35, 209, 255, 0.22);
  }

  .hero-panel {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 18px 20px;
    border-radius: 16px;
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.25);
  }

  .panel-heading {
    text-transform: uppercase;
    font-size: 0.8rem;
    letter-spacing: 0.08em;
    color: #8eb8ff;
    margin-bottom: 10px;
  }

  .panel-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    gap: 10px;
  }

  .panel-list li::before {
    content: "•";
    color: #23d1ff;
    margin-right: 8px;
  }

  .features {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 18px;
    margin-top: 36px;
  }

  .feature-card {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 18px;
    border-radius: 14px;
    box-shadow: 0 12px 30px rgba(0, 0, 0, 0.2);
  }

  .feature-card h3 {
    margin-top: 0;
    margin-bottom: 8px;
  }

  .app-grid {
    display: flex;
    flex-direction: column;
    gap: 20px;
    margin-top: 18px;
  }

  .intro {
    max-width: 720px;
  }

  .lede {
    color: #c2d4f6;
    line-height: 1.6;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 16px;
  }

  .card {
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 18px;
    border-radius: 12px;
    text-decoration: none;
    color: inherit;
    background: rgba(255, 255, 255, 0.05);
    box-shadow: 0 14px 30px rgba(0, 0, 0, 0.18);
    transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
  }

  .card:hover {
    transform: translateY(-2px);
    box-shadow: 0 18px 38px rgba(0, 0, 0, 0.24);
    border-color: rgba(35, 209, 255, 0.3);
  }

  .eyebrow {
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-size: 0.75rem;
    color: #90b4ff;
    margin: 0;
  }

  .footer {
    padding: 18px 56px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: rgba(11, 21, 40, 0.9);
    color: #c2d4f6;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
  }

  .footer-link {
    color: #9ecbff;
    text-decoration: none;
    font-weight: 600;
  }

  @media (max-width: 640px) {
    .landing-shell,
    .app-shell {
      padding: 32px 20px 24px;
    }

    .footer {
      padding: 18px 20px;
    }
  }
`;
