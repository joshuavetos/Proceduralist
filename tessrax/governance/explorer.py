"""Simple governance decision explorer."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

LEDGER_PATH = Path("tessrax/ledger/ledger.jsonl")


@dataclass(slots=True)
class GovernanceSummary:
    total_entries: int
    event_counts: Dict[str, int]


def explore(ledger_path: Path = LEDGER_PATH) -> GovernanceSummary:
    if not ledger_path.exists():
        return GovernanceSummary(total_entries=0, event_counts={})
    counter: Counter[str] = Counter()
    total = 0
    with ledger_path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            stripped = raw.strip()
            if not stripped:
                continue
            total += 1
            entry = json.loads(stripped)
            counter[entry.get("event_type", "UNKNOWN")] += 1
    return GovernanceSummary(total_entries=total, event_counts=dict(counter))


__all__ = ["GovernanceSummary", "explore"]
