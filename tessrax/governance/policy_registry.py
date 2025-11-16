"""Policy pinning and rollback receipts."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

from tessrax.core.errors import PolicyError
from tessrax.core.time import canonical_datetime

POLICY_STATE_PATH = Path("tessrax/governance/policy_state.json")


@dataclass(slots=True)
class PolicySnapshot:
    version: str
    pinned_at: str
    reason: str
    approver: str


class PolicyRegistry:
    def __init__(self, path: Path = POLICY_STATE_PATH) -> None:
        self.path = path

    def _load(self) -> dict:
        if not self.path.exists():
            return {"active_version": "v1.3", "history": []}
        raw = self.path.read_bytes()
        if not raw.strip():
            return {"active_version": "v1.3", "history": []}
        return json.loads(raw.decode("utf-8"))

    def _save(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def active_version(self) -> str:
        state = self._load()
        return state.get("active_version", "v1.3")

    def pin(self, version: str, *, reason: str, approver: str) -> PolicySnapshot:
        if not version:
            raise PolicyError("Version must be non-empty")
        state = self._load()
        snapshot = PolicySnapshot(
            version=version,
            pinned_at=canonical_datetime(),
            reason=reason,
            approver=approver,
        )
        history = state.setdefault("history", [])
        history.append(asdict(snapshot))
        state["active_version"] = version
        self._save(state)
        return snapshot

    def rollback(self, *, reason: str) -> PolicySnapshot:
        state = self._load()
        history = state.get("history", [])
        if len(history) < 2:
            raise PolicyError("No previous policy version to rollback to")
        history.pop()  # remove current
        previous = history[-1]
        state["active_version"] = previous["version"]
        state.setdefault("rollbacks", []).append(
            {
                "timestamp": canonical_datetime(),
                "reason": reason,
                "restored_version": previous["version"],
            }
        )
        self._save(state)
        return PolicySnapshot(**previous)


REGISTRY = PolicyRegistry()


__all__ = ["PolicyRegistry", "PolicySnapshot", "REGISTRY", "POLICY_STATE_PATH"]
