"""Generate demo artifacts with intentional financial contradictions."""
from __future__ import annotations

import hashlib
import os
from typing import Dict, Tuple

from fpdf import FPDF

GOVERNANCE_METADATA = {
    "auditor": "Tessrax Governance Kernel v16",
    "clauses": ["AEP-001", "RVC-001", "EAC-001", "POST-AUDIT-001", "DLK-001", "TESST"],
}

DEMO_DIR = "demo_data"


def _ensure_dir(target: str) -> None:
    if not os.path.isdir(target):
        os.makedirs(target, exist_ok=True)
    assert os.path.isdir(target), "Demo directory creation failed"


def _write_text_file(path: str, content: str) -> str:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return _finalize_artifact(path)


def _finalize_artifact(path: str) -> str:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Expected artifact at {path}")
    if os.path.getsize(path) == 0:
        raise ValueError(f"Artifact {path} is empty")
    return path


def _hash_file(path: str) -> str:
    with open(path, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()
    if len(digest) != 64:
        raise RuntimeError("SHA-256 digest generation failed")
    return digest


def generate_pdf_contract(base_dir: str = DEMO_DIR) -> Tuple[str, str]:
    """Create a loan agreement PDF with deterministic content."""

    _ensure_dir(base_dir)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, txt="NEO BANK - PERSONAL LOAN AGREEMENT", ln=1, align="C")
    pdf.ln(10)

    pdf.set_font("Arial", size=12)
    text = (
        "This agreement is made between Neo Bank Inc. and the Borrower.\n\n"
        "TERMS OF REPAYMENT:\n"
        "1. Principal Amount: $10,000\n"
        "2. Annual Percentage Rate (APR): 5.2%\n"
        "3. Term: 36 Months\n"
        "4. Late Fee: $50.00\n\n"
        "Effective Date: January 2024\n"
        "Jurisdiction: Delaware"
    )
    pdf.multi_cell(0, 10, text)

    output_path = os.path.join(base_dir, "Loan_Agreement_v4.pdf")
    pdf.output(output_path)
    finalized = _finalize_artifact(output_path)
    return finalized, _hash_file(finalized)


def generate_marketing_text(base_dir: str = DEMO_DIR) -> Tuple[str, str]:
    """Create a marketing text file with conflicting terms."""

    _ensure_dir(base_dir)
    content = (
        "\n"
        "NEO BANK SUPER SAVER LOAN!\n\n"
        "Get the cash you need instantly.\n\n"
        "- Low Rates starting at APR: 4.9%  <--- The Contradiction! (5.2 vs 4.9)\n"
        "- No hidden fees!\n"
        "- Instant approval!\n\n"
        "*Rates subject to change.\n"
    )
    output_path = os.path.join(base_dir, "Marketing_Campaign_Q1.txt")
    finalized = _write_text_file(output_path, content)
    return finalized, _hash_file(finalized)


def generate_website_html(base_dir: str = DEMO_DIR) -> Tuple[str, str]:
    """Create a landing page missing FDIC disclosures."""

    _ensure_dir(base_dir)
    html = """
    <!DOCTYPE html>
    <html>
    <head><title>Neo Bank - High Yield Savings</title></head>
    <body style="font-family: sans-serif; padding: 40px; background: #f0f9ff;">
        <h1 style="color: #2563eb;">Neo Bank Savings</h1>
        <p>Earn 4.0% APY on your savings today!</p>
        <div style="border: 1px solid #ccc; padding: 20px; background: white;">
            <h2>Terms</h2>
            <p>Effective Date: March 2023</p>
            <p>No minimum balance.</p>
        </div>
        <p style="font-size: small; color: gray;">Copyright 2024 Neo Bank.</p>
    </body>
    </html>
    """
    output_path = os.path.join(base_dir, "NeoBank_Landing.html")
    finalized = _write_text_file(output_path, html)
    return finalized, _hash_file(finalized)


def generate_demo_set(base_dir: str = DEMO_DIR) -> Dict[str, Tuple[str, str]]:
    """Generate all artifacts and return their paths and hashes."""

    pdf_path, pdf_hash = generate_pdf_contract(base_dir)
    marketing_path, marketing_hash = generate_marketing_text(base_dir)
    website_path, website_hash = generate_website_html(base_dir)

    return {
        "Loan Agreement": (pdf_path, pdf_hash),
        "Marketing": (marketing_path, marketing_hash),
        "Website": (website_path, website_hash),
    }


def _receipt(artifacts: Dict[str, Tuple[str, str]]) -> str:
    lines = ["✅ Demo Data Generated"]
    for label, (path, digest) in artifacts.items():
        lines.append(f"- {label}: {path} (sha256={digest})")
    return "\n".join(lines)


if __name__ == "__main__":
    assets = generate_demo_set()
    print(_receipt(assets))
