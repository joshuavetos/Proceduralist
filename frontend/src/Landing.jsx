import React from 'react';

function Landing({ onEnter }) {
  return (
    <div className="page landing-page">
      <div className="glass-card hero-card">
        <p className="eyebrow">Distributed Assurance Layer</p>
        <h1>The Truth Warehouse</h1>
        <p className="subtitle">
          Cryptographic forensic auditing for the real world.
        </p>
        <button className="primary" onClick={onEnter}>
          Open Audit Dashboard
        </button>
      </div>
    </div>
  );
}

export default Landing;
