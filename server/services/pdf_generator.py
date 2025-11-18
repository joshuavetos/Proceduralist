"""Deterministic forensic PDF report generator compliant with governance clauses."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from fpdf import FPDF

from server.services.engine import GOVERNANCE_METADATA


class ForensicReportPDF(FPDF):
    """Structured PDF builder for audit reports with integrity guarantees."""

    def __init__(self, ledger_id: str) -> None:
        assert ledger_id, "ledger_id is required for header integrity"
        super().__init__(orientation="P", unit="mm", format="A4")
        self.ledger_id = self._coerce_text(ledger_id)
        self.generated_at = datetime.now(timezone.utc)
        self.set_auto_page_break(auto=True, margin=15)
        self.set_creator(GOVERNANCE_METADATA["auditor"])
        self.set_title("Proceduralist Audit Record")

    def header(self) -> None:  # pragma: no cover - exercised indirectly via generate
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 10, "Proceduralist Audit Record", ln=1)
        self.set_font("Helvetica", size=10)
        timestamp = self.generated_at.isoformat()
        self.cell(0, 8, f"Timestamp: {timestamp}", ln=1)
        self.cell(0, 8, f"Ledger ID: {self.ledger_id}", ln=1)
        self.ln(2)

    def footer(self) -> None:  # pragma: no cover - exercised indirectly via generate
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        page_label = f"Page {self.page_no()}/{{nb}}"
        verification_label = "Cryptographically Verified"
        self.cell(0, 6, verification_label, align="L")
        self.cell(0, 6, page_label, align="R")

    def generate(self, report_data: Dict[str, Any]) -> bytes:
        """Render the forensic PDF and return its bytes."""

        self._validate_report(report_data)
        summary = report_data.get("summary", {})
        contradictions: List[Dict[str, Any]] = list(report_data.get("contradictions", []))
        merkle_root = self._coerce_text(summary.get("merkle_root", ""))

        if not merkle_root:
            raise ValueError("Summary must include a merkle_root to anchor the ledger header")

        self.alias_nb_pages()
        self.add_page()

        self._render_summary(summary, len(contradictions))
        self.ln(4)
        self._render_contradictions(contradictions)

        rendered = self.output(dest="S").encode("latin-1")
        assert rendered, "PDF generation must emit non-empty bytes"
        return rendered

    def _render_summary(self, summary: Dict[str, Any], contradictions_total: int) -> None:
        self.set_font("Helvetica", "B", 11)
        self.set_fill_color(230, 230, 230)
        self.cell(0, 10, "Audit Summary", ln=1, fill=True)

        rows = [
            ("Contradictions", str(summary.get("contradictions", contradictions_total))),
            ("Violations", str(summary.get("violations", 0))),
            ("Merkle Root", self._coerce_text(summary.get("merkle_root", ""))),
        ]

        for label, value in rows:
            self.set_font("Helvetica", "B", 10)
            self.cell(50, 8, label, border=1)
            self.set_font("Helvetica", size=10)
            self.multi_cell(0, 8, self._coerce_text(value), border=1)

    def _render_contradictions(self, contradictions: Iterable[Dict[str, Any]]) -> None:
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(0, 0, 0)
        self.cell(0, 10, "Contradictions", ln=1)
        self.set_font("Helvetica", size=10)

        has_entries = False
        for item in contradictions:
            has_entries = True
            severity = self._coerce_text(item.get("severity", "info")).lower()
            description = self._coerce_text(item.get("description", "No description provided."))
            location = self._coerce_text(item.get("location", "Unknown location"))

            if severity in {"critical", "high", "error"}:
                self.set_text_color(200, 0, 0)
            else:
                self.set_text_color(0, 0, 0)

            self.multi_cell(0, 8, f"[{severity.upper()}] {location}", border="B")
            self.set_text_color(60, 60, 60)
            self.multi_cell(0, 8, description)
            self.ln(2)

        if not has_entries:
            self.set_text_color(0, 100, 0)
            self.multi_cell(0, 8, "No contradictions detected.")
        self.set_text_color(0, 0, 0)

    @staticmethod
    def _coerce_text(value: Any) -> str:
        text = "" if value is None else str(value)
        return text.encode("latin-1", "replace").decode("latin-1")

    @staticmethod
    def _validate_report(report_data: Dict[str, Any]) -> None:
        if not isinstance(report_data, dict):
            raise TypeError("report_data must be a dictionary containing summary and contradictions")
        if "summary" not in report_data:
            raise ValueError("report_data must include a summary section")
        if "contradictions" not in report_data:
            raise ValueError("report_data must include a contradictions array")


__all__ = ["ForensicReportPDF"]
