"""Static-style type verification helpers for FrozenPayload."""
from __future__ import annotations

import inspect
from typing import Any, TypeGuard, get_type_hints

from tessrax.core.serialization import FrozenPayload, snapshot_payload


def is_frozen_payload(value: Any) -> TypeGuard[FrozenPayload]:
    return isinstance(value, FrozenPayload)


def run_frozen_payload_typecheck() -> bool:
    hints = get_type_hints(snapshot_payload)
    return hints.get("return") is FrozenPayload and is_frozen_payload(snapshot_payload({}))


__all__ = ["is_frozen_payload", "run_frozen_payload_typecheck"]
