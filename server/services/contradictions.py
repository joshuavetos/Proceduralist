"""Regex-driven contradiction detection for financial artifacts."""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional

GOVERNANCE_METADATA = {
    "auditor": "Tessrax Governance Kernel v16",
    "clauses": ["AEP-001", "RVC-001", "EAC-001", "POST-AUDIT-001", "DLK-001", "TESST"],
}

PATTERNS = {
    "apr": r"APR[:\s]*(\d+\.?\d*)%",
    "late_fee": r"Late Fee[:\s]*\$?(\d+)",
    "effective_date": r"Effective[:\s]*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})",
    "arbitration": r"(arbitration|class action waiver)",
    "fdic": r"(Member FDIC|insured by the FDIC)",
}


class ArtifactValidationError(ValueError):
    """Deterministic validation error for malformed artifacts."""


CompiledPatternMap = Dict[str, re.Pattern[str]]


def _compile_patterns(pattern_map: Dict[str, str]) -> CompiledPatternMap:
    if not pattern_map:
        raise ValueError("Pattern map cannot be empty for contradiction engine initialization")
    compiled: CompiledPatternMap = {}
    for key, expr in pattern_map.items():
        try:
            compiled[key] = re.compile(expr, re.IGNORECASE)
        except re.error as exc:  # pragma: no cover - defensive branch
            raise ValueError(f"Invalid regex for pattern '{key}': {exc}") from exc
    assert set(compiled) == set(pattern_map), "Pattern compilation drift detected"
    return compiled


_COMPILED_PATTERNS = _compile_patterns(PATTERNS)


def _text_from_artifact(artifact: Dict[str, Any]) -> str:
    if not isinstance(artifact, dict):
        raise ArtifactValidationError("Artifact must be a dictionary with textual content")

    candidates = (
        artifact.get("content"),
        artifact.get("value"),
        artifact.get("text"),
        artifact.get("body"),
    )
    text = next((candidate for candidate in candidates if isinstance(candidate, str)), None)
    if text is None:
        raise ArtifactValidationError("Artifact missing textual content required for analysis")
    return text


def _artifact_name(artifact: Dict[str, Any]) -> str:
    raw = artifact.get("name") or artifact.get("type") or "artifact"
    return str(raw)


def extract_terms(text: str) -> Dict[str, Any]:
    """Scan text for specific financial and legal terms using regex."""

    if not isinstance(text, str):
        raise TypeError("extract_terms expects a string input for analysis")

    findings: Dict[str, Any] = {}

    apr_match = _COMPILED_PATTERNS["apr"].search(text)
    if apr_match:
        findings["apr"] = float(apr_match.group(1))

    fee_match = _COMPILED_PATTERNS["late_fee"].search(text)
    if fee_match:
        findings["late_fee"] = int(fee_match.group(1))

    date_match = _COMPILED_PATTERNS["effective_date"].search(text)
    if date_match:
        findings["effective_date"] = f"{date_match.group(1)} {date_match.group(2)}"

    findings["has_arbitration"] = bool(_COMPILED_PATTERNS["arbitration"].search(text))
    findings["has_fdic"] = bool(_COMPILED_PATTERNS["fdic"].search(text))

    return findings


def _contradiction_entry(
    *,
    identifier: int,
    ctype: str,
    severity: str,
    doc_a: str,
    text_a: str,
    doc_b: str,
    text_b: str,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    detail = description or f"{ctype}: {text_a} vs {text_b}"
    digest_source = f"{identifier}:{ctype}:{doc_a}:{doc_b}:{text_a}:{text_b}:{severity}"
    signature = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()
    assert signature, "Contradiction signature must not be empty"
    return {
        "id": identifier,
        "type": ctype,
        "severity": severity,
        "docA": {"name": doc_a, "text": text_a},
        "docB": {"name": doc_b, "text": text_b},
        "location": f"{doc_a} vs {doc_b}",
        "description": detail,
        "signature": signature,
    }


def detect_conflicts(artifacts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compare extracted terms across artifacts to find contradictions."""

    if not isinstance(artifacts, list):
        raise TypeError("detect_conflicts expects a list of artifact dictionaries")
    if not artifacts:
        raise ArtifactValidationError("detect_conflicts requires at least one artifact input")

    sorted_artifacts = sorted(artifacts, key=_artifact_name)
    artifact_terms: List[Dict[str, Any]] = []
    for artifact in sorted_artifacts:
        text = _text_from_artifact(artifact)
        terms = extract_terms(text)
        artifact_terms.append({"name": _artifact_name(artifact), "terms": terms, "content": text})

    contradictions: List[Dict[str, Any]] = []
    identifier = 1

    reference_apr: Optional[float] = None
    reference_apr_source: Optional[str] = None
    for item in artifact_terms:
        apr = item["terms"].get("apr")
        if apr is not None:
            if reference_apr is None:
                reference_apr = apr
                reference_apr_source = item["name"]
            elif apr != reference_apr:
                assert reference_apr_source is not None
                contradictions.append(
                    _contradiction_entry(
                        identifier=identifier,
                        ctype="Rate Discrepancy",
                        severity="high",
                        doc_a=reference_apr_source,
                        text_a=f"APR: {reference_apr}%",
                        doc_b=item["name"],
                        text_b=f"APR: {apr}%",
                    )
                )
                identifier += 1

    reference_date: Optional[str] = None
    reference_date_source: Optional[str] = None
    for item in artifact_terms:
        date = item["terms"].get("effective_date")
        if date is not None:
            if reference_date is None:
                reference_date = date
                reference_date_source = item["name"]
            elif date != reference_date:
                assert reference_date_source is not None
                contradictions.append(
                    _contradiction_entry(
                        identifier=identifier,
                        ctype="Effective-Date Drift",
                        severity="medium",
                        doc_a=reference_date_source,
                        text_a=f"Effective: {reference_date}",
                        doc_b=item["name"],
                        text_b=f"Effective: {date}",
                    )
                )
                identifier += 1

    all_text = " ".join(item["content"] for item in artifact_terms).lower()
    has_savings = "savings" in all_text
    has_fdic = any(item["terms"].get("has_fdic") for item in artifact_terms)
    if has_savings and not has_fdic:
        contradictions.append(
            _contradiction_entry(
                identifier=identifier,
                ctype="Missing Regulatory Disclosure",
                severity="critical",
                doc_a="Global Audit",
                text_a="Product 'Savings' detected",
                doc_b="All Documents",
                text_b="Missing 'Member FDIC' disclosure",
            )
        )

    return contradictions


__all__ = [
    "GOVERNANCE_METADATA",
    "extract_terms",
    "detect_conflicts",
    "ArtifactValidationError",
]
