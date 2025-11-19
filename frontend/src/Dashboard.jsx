import React, { useCallback, useMemo, useState } from 'react';
import FileDropZone from './components/FileDropZone';
import AuditSummary from './components/AuditSummary';
import ContradictionList from './components/ContradictionList';
import PDFButton from './components/PDFButton';

const API = import.meta.env.VITE_API_URL || '';

function Dashboard({ onBack }) {
  const [files, setFiles] = useState([]);
  const [text, setText] = useState('');
  const [url, setUrl] = useState('');
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleDrop = useCallback((accepted) => {
    setFiles((prev) => [...prev, ...accepted]);
  }, []);

  const removeFile = useCallback((name) => {
    setFiles((prev) => prev.filter((file) => file.name !== name));
  }, []);

  const formIsEmpty = useMemo(
    () => files.length === 0 && !text.trim() && !url.trim(),
    [files, text, url]
  );

  const runAudit = async () => {
    if (formIsEmpty) {
      setError('Provide a file, text, or URL to run an audit.');
      return;
    }
    setLoading(true);
    setError('');
    const body = new FormData();
    files.forEach((file) => body.append('files', file));
    if (text.trim()) body.append('text', text.trim());
    if (url.trim()) body.append('url', url.trim());

    try {
      const response = await fetch(`${API}/api/audit`, {
        method: 'POST',
        body,
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || 'Audit request failed');
      }
      const data = await response.json();
      setReport(data);
    } catch (err) {
      setError(err.message || 'Unexpected error');
    } finally {
      setLoading(false);
    }
  };

  const auditId = report?.audit_id || report?.auditId || '';
  const merkleRoot = report?.merkle_root || report?.merkleRoot || '';
  const contradictions = report?.contradictions || [];

  return (
    <div className="page dashboard-page">
      <div className="top-bar">
        <button className="ghost" onClick={onBack}>
          ← Back
        </button>
        <h2>Audit Dashboard</h2>
        <div className="spacer" />
      </div>

      <div className="grid">
        <div className="glass-card">
          <div className="section-header">
            <div>
              <p className="eyebrow">Inputs</p>
              <h3>Upload evidence</h3>
            </div>
            <span className="badge">Secure</span>
          </div>
          <FileDropZone files={files} onDrop={handleDrop} onRemove={removeFile} />
          <div className="input-group">
            <label htmlFor="text">Raw Text</label>
            <textarea
              id="text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste transcripts, summaries, or notes"
            />
          </div>
          <div className="input-group">
            <label htmlFor="url">URL</label>
            <input
              id="url"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/source"
            />
          </div>
          {error && <div className="error">{error}</div>}
          <button className="primary" onClick={runAudit} disabled={loading}>
            {loading ? 'Running audit…' : 'Run Audit'}
          </button>
        </div>

        <div className="glass-card">
          <div className="section-header">
            <div>
              <p className="eyebrow">Report</p>
              <h3>Audit Summary</h3>
            </div>
            {auditId && <span className="badge badge-ghost">ID: {auditId}</span>}
          </div>
          {loading && <div className="loader" aria-label="loading" />}
          {!loading && report && (
            <>
              <AuditSummary
                auditId={auditId}
                merkleRoot={merkleRoot}
                findings={report.findings || []}
              />
              <ContradictionList contradictions={contradictions} />
              <PDFButton apiBase={API} report={report} />
            </>
          )}
          {!loading && !report && (
            <p className="muted">Run an audit to see the structured report.</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
