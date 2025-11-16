"""Canonical datetime helpers enforcing UTC + ISO-8601 with ``Z`` suffix."""
from __future__ import annotations

from datetime import datetime, timezone


def canonical_datetime(dt: datetime | None = None) -> str:
    reference = dt.astimezone(timezone.utc) if dt else datetime.now(timezone.utc)
    normalized = reference.replace(microsecond=reference.microsecond // 1000 * 1000)
    return normalized.isoformat().replace("+00:00", "Z")


def parse_canonical_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc)


__all__ = ["canonical_datetime", "parse_canonical_datetime"]
