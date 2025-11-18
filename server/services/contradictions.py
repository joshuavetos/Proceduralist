"""Rule-based contradiction detection utilities using regex extraction."""
from __future__ import annotations

import re
from typing import Dict, List


GOVERNANCE_METADATA = {
    "auditor": "Tessrax Governance Kernel v16",
    "clauses": ["AEP-001", "RVC-001", "EAC-001", "POST-AUDIT-001", "DLK-001", "TESST"],
}


APR_PATTERN = re.compile(r"APR:?\s*(?P<value>\d+\.?\d*)%", re.IGNORECASE)
FEE_PATTERN = re.compile(r"(?:Late\s+)?Fee:?\s*\$(?P<value>\d+)", re.IGNORECASE)
DATE_PATTERN = re.compile(r"Effective:?\s*(?P<value>[A-Za-z]+\s+\d{4})", re.IGNORECASE)


def extract_financial_terms(text: str) -> Dict[str, object]:
    """Extract APR, fee, and effective date values from free-form text."""

    if text is None:
        return {}

    apr_match = APR_PATTERN.search(text)
    fee_match = FEE_PATTERN.search(text)
    date_match = DATE_PATTERN.search(text)

    extracted: Dict[str, object] = {}
    if apr_match:
        extracted["apr"] = float(apr_match.group("value"))
    if fee_match:
        extracted["fee"] = int(fee_match.group("value"))
    if date_match:
        extracted["date"] = date_match.group("value")

    return extracted


def _artifact_location(artifact: Dict[str, object]) -> str:
    artifact_type = str(artifact.get("type", "unknown"))
    name = artifact.get("name") or artifact.get("value") or "payload"
    return f"{artifact_type}:{name}"


def detect_conflicts(artifacts: List[Dict[str, object]]) -> List[Dict[str, str]]:
    """Detect conflicts between financial terms extracted from artifacts."""

    if artifacts is None:
        raise ValueError("detect_conflicts requires an artifact list")

    contradictions: List[Dict[str, str]] = []
    parsed_terms: List[Dict[str, object]] = []

    for artifact in artifacts:
        content_sources = (
            artifact.get("content"),
            artifact.get("value"),
            artifact.get("text"),
            artifact.get("body"),
        )
        content = next((source for source in content_sources if isinstance(source, str)), "")
        terms = extract_financial_terms(content)
        parsed_terms.append({"location": _artifact_location(artifact), "terms": terms})

    for idx, current in enumerate(parsed_terms):
        for comparison in parsed_terms[idx + 1 :]:
            for field, label in (("apr", "APR"), ("fee", "Fee"), ("date", "Effective Date")):
                first_value = current["terms"].get(field)
                second_value = comparison["terms"].get(field)
                if first_value is None or second_value is None:
                    continue
                if first_value != second_value:
                    contradictions.append(
                        {
                            "location": f"{current['location']} vs {comparison['location']}",
                            "description": f"{label} mismatch: {first_value} != {second_value}",
                            "severity": "warning",
                        }
                    )

    return contradictions


__all__ = [
    "GOVERNANCE_METADATA",
    "extract_financial_terms",
    "detect_conflicts",
]
