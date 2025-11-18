"""Generate demo artifacts with intentional financial contradictions."""
from __future__ import annotations

import os

from fpdf import FPDF

GOVERNANCE_METADATA = {
    "auditor": "Tessrax Governance Kernel v16",
    "clauses": ["AEP-001", "RVC-001", "EAC-001", "POST-AUDIT-001", "DLK-001", "TESST"],
}


def _ensure_directory(target: str) -> None:
    if not os.path.isdir(target):
        os.makedirs(target, exist_ok=True)


def generate_contract(base_dir: str = "demo_data") -> str:
    """Create a loan agreement PDF with deterministic content."""

    _ensure_directory(base_dir)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Loan Agreement", ln=True, align="C")
    pdf.cell(200, 10, txt="APR: 5.2%", ln=True, align="L")
    pdf.cell(200, 10, txt="Late Fee: $50", ln=True, align="L")
    output_path = os.path.join(base_dir, "Loan_Agreement.pdf")
    pdf.output(output_path)
    return output_path


def generate_marketing(base_dir: str = "demo_data") -> str:
    """Create a marketing text file with conflicting terms."""

    _ensure_directory(base_dir)
    content = "\n".join(
        [
            "Super Saver Loan!",
            "APR: 4.9% (Best in class!)",
            "Late Fee: $25",
        ]
    )
    output_path = os.path.join(base_dir, "Marketing_Copy.txt")
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return output_path


def generate_policy(base_dir: str = "demo_data") -> str:
    """Create a policy HTML file declaring an effective date."""

    _ensure_directory(base_dir)
    html = "<html><body><p>Effective Date: January 2024</p></body></html>"
    output_path = os.path.join(base_dir, "Policy_Update.html")
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(html)
    return output_path


if __name__ == "__main__":
    generate_contract()
    generate_marketing()
    generate_policy()
