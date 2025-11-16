"""Advanced governance coverage utilities."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from tessrax.core import contradiction_engine
from tessrax.core.contradiction_engine import ContradictionNode
from tessrax.core.errors import DiagnosticError
from tessrax.core.serialization import canonical_json, normalize_payload
from tessrax.infra import key_registry
from tessrax.ledger.parallel_replay import parallel_replay_root

AUDITOR_IDENTITY = "Tessrax Governance Kernel v16"


@dataclass(frozen=True)
class ContradictionStressResult:
    nodes_checked: int
    contradictions_found: int
    ledger_index_ready: bool
    auditor: str = AUDITOR_IDENTITY


@dataclass(frozen=True)
class GovernanceReplayReport:
    ledger_path: Path
    merkle_root: str
    entry_count: int
    auditor: str = AUDITOR_IDENTITY


@dataclass(frozen=True)
class ReceiptNormalizationResult:
    canonical_hash: str
    normalized_payload: Mapping[str, object]
    size_bytes: int
    auditor: str = AUDITOR_IDENTITY


@dataclass(frozen=True)
class MultiSigVerificationReport:
    approvals_required: Sequence[str]
    approvals_present: Sequence[str]
    quorum_satisfied: bool
    latest_receipt_hash: str | None
    auditor: str = AUDITOR_IDENTITY


def contradiction_stress_harness(*, total_nodes: int = 16, index_path: Path | None = None) -> ContradictionStressResult:
    if total_nodes <= 0:
        raise DiagnosticError("total_nodes must be positive")
    nodes: list[ContradictionNode] = []
    for idx in range(total_nodes):
        node = ContradictionNode(
            id=idx,
            state_hash=f"{idx:064x}",
            url=f"https://tessrax.invalid/{idx}",
            title=f"synthetic-{idx}",
            is_contradiction=(idx % 3 == 0),
            is_deleted=False,
        )
        nodes.append(node)
    previous_path = contradiction_engine.INDEX_PATH
    if index_path is not None:
        contradiction_engine.INDEX_PATH = Path(index_path)
    try:
        detected = contradiction_engine.find_contradictions(nodes)
    finally:
        contradiction_engine.INDEX_PATH = previous_path
    ledger_index_ready = Path(index_path or previous_path).exists()
    return ContradictionStressResult(
        nodes_checked=len(nodes),
        contradictions_found=len(detected),
        ledger_index_ready=ledger_index_ready,
    )


def governance_replay_simulator(*, ledger_path: Path) -> GovernanceReplayReport:
    ledger_file = Path(ledger_path)
    if not ledger_file.exists():
        raise DiagnosticError(f"Ledger missing at {ledger_file}")
    merkle_root = parallel_replay_root(ledger_path=ledger_file)
    entry_count = sum(1 for line in ledger_file.read_text(encoding="utf-8").splitlines() if line.strip())
    return GovernanceReplayReport(ledger_path=ledger_file, merkle_root=merkle_root, entry_count=entry_count)


def audit_receipt_normalizer(receipt: Mapping[str, object]) -> ReceiptNormalizationResult:
    normalized = normalize_payload(receipt)
    canonical = canonical_json(normalized)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return ReceiptNormalizationResult(
        canonical_hash=digest,
        normalized_payload=normalized,
        size_bytes=len(canonical.encode("utf-8")),
    )


def multisig_rotation_verifier(*, rotation_state_path: Path | None = None) -> MultiSigVerificationReport:
    state_path = Path(rotation_state_path or key_registry.ROTATION_STATE_PATH)
    if not state_path.exists():
        raise DiagnosticError("Rotation state file missing")
    state = json.loads(state_path.read_text(encoding="utf-8") or "{}")
    active_key = state.get("active_key")
    approvals_present: Sequence[str] = []
    if active_key:
        approvals_present = state.get("keys", {}).get(active_key, {}).get("governance_approval", {}).get("approvals", [])
    required_raw = os.getenv("TESSRAX_REQUIRED_APPROVERS", "")
    approvals_required = [token.strip() for token in required_raw.split(",") if token.strip()]
    quorum_satisfied = set(approvals_required).issubset(set(approvals_present)) if approvals_required else bool(approvals_present)
    receipts_path = state_path.parent / "rotation_receipts.json"
    latest_receipt_hash: str | None = None
    if receipts_path.exists():
        receipts = json.loads(receipts_path.read_text(encoding="utf-8") or "[]")
        if receipts:
            canonical = canonical_json(receipts[-1])
            latest_receipt_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return MultiSigVerificationReport(
        approvals_required=approvals_required,
        approvals_present=list(approvals_present),
        quorum_satisfied=quorum_satisfied,
        latest_receipt_hash=latest_receipt_hash,
    )


__all__ = [
    "ContradictionStressResult",
    "GovernanceReplayReport",
    "ReceiptNormalizationResult",
    "MultiSigVerificationReport",
    "audit_receipt_normalizer",
    "contradiction_stress_harness",
    "governance_replay_simulator",
    "multisig_rotation_verifier",
]
