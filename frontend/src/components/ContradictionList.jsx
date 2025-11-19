import React from 'react';

function ContradictionList({ contradictions }) {
  return (
    <div className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Contradictions</p>
          <h4>Conflict Map</h4>
        </div>
        <span className="badge badge-ghost">{contradictions.length}</span>
      </div>
      {contradictions.length === 0 ? (
        <p className="muted">No contradictions detected.</p>
      ) : (
        <ul className="contradictions">
          {contradictions.map((item, idx) => (
            <li key={`${item}-${idx}`} className="contradiction-item">
              <span className="dot" aria-hidden />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default ContradictionList;
