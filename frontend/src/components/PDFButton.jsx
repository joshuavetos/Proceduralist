import React, { useState } from 'react';

function PDFButton({ apiBase, report }) {
  const [downloading, setDownloading] = useState(false);
  if (!report) return null;

  const download = async () => {
    setDownloading(true);
    try {
      const response = await fetch(`${apiBase}/api/audit/pdf`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(report),
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || 'PDF generation failed');
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `audit-${report.audit_id || report.auditId || 'report'}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert(err.message || 'Failed to download PDF');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <button className="secondary" onClick={download} disabled={downloading}>
      {downloading ? 'Preparing PDF…' : 'Download PDF'}
    </button>
  );
}

export default PDFButton;
