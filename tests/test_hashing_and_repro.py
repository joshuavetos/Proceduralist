from __future__ import annotations

from pathlib import Path

import pytest

from tessrax.core.hashing import DeterministicHasher
from tessrax.diagnostics.reproducibility import audit_reproducibility, reproducibility_guard


def test_deterministic_hasher_payload_consistency() -> None:
    hasher = DeterministicHasher()
    hasher.update_payload({"b": 2, "a": 1})
    first = hasher.hexdigest()
    assert len(first) == 64
    assert hasher.digest().digest == first


def test_reproducibility_audit(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    merkle = tmp_path / "merkle_state.json"
    requirements = tmp_path / "requirements.txt"
    ledger.write_text("{\"entry\":1}\n", encoding="utf-8")
    merkle.write_text("{\"root\":\"abc\"}\n", encoding="utf-8")
    requirements.write_text("pytest\n", encoding="utf-8")
    report = audit_reproducibility(ledger_path=ledger, merkle_state_path=merkle, requirements_path=requirements)
    assert report.consistent is True
    reproducibility_guard(reference_hashes=[report.ledger_hash.digest], ledger_path=ledger)
    with pytest.raises(Exception):
        reproducibility_guard(reference_hashes=["deadbeef"], ledger_path=ledger)
