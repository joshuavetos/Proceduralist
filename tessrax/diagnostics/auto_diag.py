"""Auto-diagnose tool aggregating ledger health information."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from tessrax.core.errors import DiagnosticError
from tessrax.ledger.auto_repair import auto_repair
from tessrax.ledger.parallel_replay import parallel_replay_root

LEDGER_PATH = Path("tessrax/ledger/ledger.jsonl")
MERKLE_STATE_PATH = Path("tessrax/ledger/merkle_state.json")
INDEX_PATH = Path("tessrax/ledger/index.db")
REPORT_PATH = Path("tessrax/diagnostics/auto_diag_report.json")


def auto_diagnose(
    *,
    ledger_path: Path = LEDGER_PATH,
    merkle_state_path: Path = MERKLE_STATE_PATH,
    index_path: Path = INDEX_PATH,
    report_path: Path = REPORT_PATH,
) -> Dict[str, Any]:
    if not ledger_path.exists():
        raise DiagnosticError("Ledger missing; cannot diagnose")
    merkle_root = parallel_replay_root(ledger_path=ledger_path)
    repair_report = auto_repair(
        ledger_path=ledger_path,
        merkle_state_path=merkle_state_path,
        index_path=index_path,
    )
    report = {
        "diagnosed": True,
        "merkle_root": merkle_root,
        "repair": repair_report,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


__all__ = ["auto_diagnose"]
