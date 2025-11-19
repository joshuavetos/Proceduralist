import React from 'react';

function AuditSummary({ auditId, merkleRoot, findings }) {
  return (
    <div className="panel">
      <div className="meta-row">
        <div>
          <p className="eyebrow">Audit ID</p>
          <p className="mono">{auditId || '—'}</p>
        </div>
        <div>
          <p className="eyebrow">Merkle Root</p>
          <p className="mono root">{merkleRoot || '—'}</p>
        </div>
      </div>
      <div className="divider" />
      <div>
        <p className="eyebrow">Findings</p>
        {findings.length === 0 ? (
          <p className="muted">No findings reported.</p>
        ) : (
          <ul className="findings">
            {findings.map((item, idx) => (
              <li key={idx}>{item}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default AuditSummary;
