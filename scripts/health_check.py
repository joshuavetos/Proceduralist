"""Subsystem integrity probe for Proceduralist.

This script performs lightweight checks to ensure imports, core routines,
PDF generation, and contradiction detection all function in a cold-start
Python 3.11 environment.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

GOVERNANCE_METADATA = {
    "auditor": "Tessrax Governance Kernel v16",
    "clauses": ["AEP-001", "RVC-001", "EAC-001", "POST-AUDIT-001", "DLK-001", "TESST"],
}

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _record(statuses: List[Tuple[str, bool, str]], name: str, ok: bool, detail: str) -> None:
    statuses.append((name, ok, detail))


def _check_import(module_name: str) -> Tuple[bool, str]:
    try:
        importlib.import_module(module_name)
        return True, "imported"
    except Exception as exc:  # pragma: no cover - diagnostic path
        return False, f"failed import: {exc}"  # deterministic message


def core_imports() -> Tuple[bool, str]:
    targets = [
        "tessrax.core.serialization",
        "tessrax.core.merkle",
        "tessrax.ledger",
    ]
    failures = [name for name in targets if not _check_import(name)[0]]
    if failures:
        return False, f"missing core imports: {', '.join(failures)}"
    return True, "core imports ok"


def server_imports() -> Tuple[bool, str]:
    targets = [
        "server.main",
        "server.routers.audit",
        "server.services.engine",
        "server.services.contradictions",
        "server.services.pdf_generator",
    ]
    failures = [name for name in targets if not _check_import(name)[0]]
    if failures:
        return False, f"missing server imports: {', '.join(failures)}"
    return True, "server imports ok"


def frontend_manifest() -> Tuple[bool, str]:
    manifest_path = Path(__file__).resolve().parent.parent / "frontend" / "package.json"
    if not manifest_path.is_file():
        return False, f"frontend manifest missing at {manifest_path}"
    data = json.loads(manifest_path.read_text())
    required = ["name", "version", "scripts"]
    missing = [key for key in required if key not in data]
    if missing:
        return False, f"frontend manifest missing keys: {', '.join(missing)}"
    return True, "frontend manifest ok"


def mini_contradiction() -> Tuple[bool, str]:
    from server.services.contradictions import detect_conflicts

    artifacts = [
        {"name": "docA", "content": "APR: 5.2% Effective: Jan 2024"},
        {"name": "docB", "content": "APR: 4.9% Effective: Mar 2023 savings"},
    ]
    contradictions = detect_conflicts(artifacts)
    if not contradictions:
        return False, "contradiction detection returned zero results"
    signatures = [item.get("signature") for item in contradictions]
    if any(len(sig or "") != 64 for sig in signatures):
        return False, "invalid contradiction signature length"
    return True, f"contradictions detected: {len(contradictions)}"


def mini_pdf() -> Tuple[bool, str]:
    from server.services.pdf_generator import generate_pdf

    sample_report: Dict[str, object] = {
        "summary": {
            "auditId": "demo-root",
            "merkle_root": "demo-root",
            "contradictions": 1,
            "violations": 1,
        },
        "contradictions": [
            {
                "type": "Rate Discrepancy",
                "severity": "high",
                "docA": {"name": "A", "text": "APR 5.2%"},
                "docB": {"name": "B", "text": "APR 4.9%"},
                "description": "APR mismatch",
            }
        ],
    }
    pdf_bytes, digest = generate_pdf(sample_report)
    if not pdf_bytes:
        return False, "pdf generation returned empty payload"
    if len(digest) != 64:
        return False, "pdf digest length invalid"
    return True, "pdf generation ok"


def main() -> None:
    statuses: List[Tuple[str, bool, str]] = []
    _record(statuses, "core_imports", *core_imports())
    _record(statuses, "server_imports", *server_imports())
    _record(statuses, "frontend_manifest", *frontend_manifest())
    _record(statuses, "mini_contradiction", *mini_contradiction())
    _record(statuses, "mini_pdf", *mini_pdf())

    overall = all(ok for _, ok, _ in statuses)
    for name, ok, detail in statuses:
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}: {detail}")

    receipt = {
        "timestamp": "",
        "executor": "Codex",
        "integrity_score": 1.0 if overall else 0.0,
        "completeness_score": 1.0 if overall else 0.0,
        "runtime_context": {
            "python": sys.version.split()[0],
            "files_touched": [],
            "tests_detected": [],
            "dependencies": list(sorted(sys.modules.keys())),
        },
        "status": "PASS" if overall else "FAIL",
        "signature": "sha256:stub",
        "auditor": GOVERNANCE_METADATA["auditor"],
        "clauses": GOVERNANCE_METADATA["clauses"],
    }
    print(json.dumps(receipt, indent=2))

    assert overall, "Health check failed one or more subsystems"


if __name__ == "__main__":
    main()
