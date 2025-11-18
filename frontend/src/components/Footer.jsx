export default function Footer() {
  const currentYear = new Date().getFullYear();
  return (
    <footer className="footer" aria-label="Site footer">
      <div>© {currentYear} Proceduralist</div>
      <a className="footer-link" href="/docs" aria-label="Documentation">
        Docs
      </a>
    </footer>
  );
}
