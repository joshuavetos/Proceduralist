"""Professional forensic PDF generator for audit findings."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Tuple

from fpdf import FPDF

from server.services.engine import GOVERNANCE_METADATA


class ForensicReportPDF(FPDF):
    """Structured PDF builder for audit reports with integrity guarantees."""

    def __init__(self, ledger_id: str) -> None:
        assert ledger_id, "ledger_id is required for header integrity"
        super().__init__(orientation="P", unit="mm", format="A4")
        self.ledger_id = str(ledger_id)
        self.generated_at = datetime.utcnow()
        self.set_auto_page_break(auto=True, margin=15)
        self.set_creator(GOVERNANCE_METADATA["auditor"])
        self.set_title("Proceduralist Audit Record")

    def header(self) -> None:  # pragma: no cover - exercised indirectly via generate
        self.set_font("Arial", "B", 15)
        self.set_text_color(37, 99, 235)
        self.cell(80)
        self.cell(30, 10, "PROCEDURALIST", 0, 0, "C")
        self.ln(8)

        self.set_font("Arial", "I", 8)
        self.set_text_color(128, 128, 128)
        timestamp = self.generated_at.strftime("%Y-%m-%d %H:%M")
        self.cell(0, 10, f"Cryptographic Audit Record • Generated {timestamp}", 0, 0, "C")
        self.ln(20)

    def footer(self) -> None:  # pragma: no cover - exercised indirectly via generate
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Page {self.page_no()} • Ledger {self.ledger_id}", 0, 0, "C")

    def chapter_title(self, label: str) -> None:
        self.set_font("Arial", "B", 12)
        self.set_fill_color(240, 245, 255)
        self.set_text_color(0, 0, 0)
        self.cell(0, 10, f"  {label}", 0, 1, "L", 1)
        self.ln(4)

    def chapter_body(self, body: str) -> None:
        self.set_font("Arial", "", 10)
        self.multi_cell(0, 6, body)
        self.ln()

    def add_contradiction(self, contradiction: Dict[str, Any]) -> None:
        self.set_font("Arial", "B", 10)
        self.set_text_color(220, 53, 69)
        ctype = str(contradiction.get("type", "UNKNOWN")).upper()
        severity = str(contradiction.get("severity", "info")).upper()
        self.cell(0, 8, f"TYPE: {ctype} ({severity})", 0, 1)

        self.set_font("Arial", "", 10)
        self.set_text_color(0, 0, 0)
        doc_a = contradiction.get("docA") or {}
        doc_b = contradiction.get("docB") or {}
        self.cell(10)
        self.cell(0, 6, f"Source A ({doc_a.get('name', 'unknown')}): {doc_a.get('text', '')}", 0, 1)
        self.cell(10)
        self.cell(0, 6, f"Source B ({doc_b.get('name', 'unknown')}): {doc_b.get('text', '')}", 0, 1)
        self.ln(4)

    def generate(self, report_data: Dict[str, Any]) -> bytes:
        self._validate_report(report_data)
        summary = report_data["summary"]
        contradictions: List[Dict[str, Any]] = list(report_data.get("contradictions", []))

        self.alias_nb_pages()
        self.add_page()

        self.chapter_title("Executive Summary")
        summary_text = self._summary_block(summary, len(contradictions))
        self.chapter_body(summary_text)

        self.chapter_title("Critical Findings")
        if contradictions:
            for item in contradictions:
                self.add_contradiction(item)
        else:
            self.chapter_body("No contradictions detected.")

        self.ln(20)
        self.set_font("Arial", "B", 10)
        self.cell(0, 10, "_" * 50, 0, 1)
        self.cell(0, 5, "Authorized Signature", 0, 1)

        rendered = self.output(dest="S").encode("latin-1")
        assert rendered, "PDF generation must emit non-empty bytes"
        return rendered

    @staticmethod
    def _summary_block(summary: Dict[str, Any], contradiction_count: int) -> str:
        audit_id = summary.get("auditId") or summary.get("merkle_root") or "unknown"
        merkle_root = summary.get("merkleRoot") or summary.get("merkle_root") or "unknown"
        return (
            f"Audit ID: {audit_id}\n"
            f"Merkle Root: {merkle_root}\n\n"
            f"Total Contradictions Found: {summary.get('contradictions', contradiction_count)}\n"
            f"Critical Violations: {summary.get('violations', 0)}"
        )

    @staticmethod
    def _validate_report(report_data: Dict[str, Any]) -> None:
        if not isinstance(report_data, dict):
            raise TypeError("report_data must be a dictionary containing summary and contradictions")
        summary = report_data.get("summary")
        if not isinstance(summary, dict):
            raise ValueError("report_data must include a summary section")
        if "merkle_root" not in summary and "merkleRoot" not in summary and "auditId" not in summary:
            raise ValueError("summary must contain merkle_root, merkleRoot, or auditId for ledger anchoring")
        if "contradictions" not in report_data:
            raise ValueError("report_data must include a contradictions array")


def generate_pdf(report_data: Dict[str, Any]) -> Tuple[bytes, str]:
    """Create a forensic PDF and return the bytes and SHA-256 digest."""

    generator = ForensicReportPDF(ledger_id=str(report_data.get("summary", {}).get("merkle_root", "unknown")))
    pdf_bytes = generator.generate(report_data)
    digest = _sha256(pdf_bytes)
    return pdf_bytes, digest


def _sha256(payload: bytes) -> str:
    import hashlib

    digest = hashlib.sha256(payload).hexdigest()
    if len(digest) != 64:
        raise RuntimeError("SHA-256 digest calculation failed")
    return digest


__all__ = ["ForensicReportPDF", "generate_pdf"]
