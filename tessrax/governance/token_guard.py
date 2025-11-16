"""Governance token freshness guard implementing anti-replay semantics."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

from tessrax.core.errors import GovernanceTokenError
from tessrax.core.time import canonical_datetime, parse_canonical_datetime

DEFAULT_WINDOW_SECONDS = 300
STATE_PATH = Path("tessrax/governance/token_state.json")


class GovernanceTokenGuard:
    """Stateful freshness guard ensuring tokens are periodically renewed."""

    def __init__(
        self,
        *,
        state_path: Path = STATE_PATH,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        self.state_path = state_path
        self.window = timedelta(seconds=window_seconds)

    def _load_state(self) -> Dict[str, Any]:
        if not self.state_path.exists():
            return {}
        raw = self.state_path.read_bytes()
        if not raw.strip():
            return {}
        return json.loads(raw.decode("utf-8"))

    def _save_state(self, state: Dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def validate(self, *, ledger_counter: int) -> str:
        token = os.getenv("TESSRAX_GOVERNANCE_TOKEN")
        if not token:
            raise GovernanceTokenError("Governance token missing from environment")
        digest = self._hash_token(token)
        state = self._load_state()
        now = datetime.now(timezone.utc)
        record = state.get(digest)
        if record:
            last_seen = parse_canonical_datetime(record["last_seen"])
            if now - last_seen > self.window:
                raise GovernanceTokenError(
                    "Governance token expired; refresh required",
                    details={"last_seen": record["last_seen"], "window_seconds": self.window.total_seconds()},
                )
            if record.get("last_counter") == ledger_counter:
                raise GovernanceTokenError(
                    "Governance token replay detected",
                    details={"counter": ledger_counter},
                )
        tag = f"{digest}:{ledger_counter}"
        state[digest] = {
            "last_seen": canonical_datetime(now),
            "last_counter": ledger_counter,
            "last_tag": tag,
        }
        self._save_state(state)
        return tag


__all__ = ["GovernanceTokenGuard"]
