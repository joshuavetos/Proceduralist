"""Structured error utilities for Tessrax subsystems."""
from __future__ import annotations

from typing import Mapping


class TessraxError(RuntimeError):
    """Base class for structured Tessrax errors with stable codes."""

    __slots__ = ("code", "message", "details")

    def __init__(self, *, code: str, message: str, details: Mapping[str, object] | None = None) -> None:
        self.code = code
        self.message = message
        self.details = details
        super().__init__(f"[{self.code}] {self.message}")


class EpochError(TessraxError):
    def __init__(self, message: str, *, details: Mapping[str, object] | None = None):
        super().__init__(code="EPOCH_VIOLATION", message=message, details=details)


class GovernanceTokenError(TessraxError):
    def __init__(self, message: str, *, details: Mapping[str, object] | None = None):
        super().__init__(code="GOV_TOKEN", message=message, details=details)


class LedgerRepairError(TessraxError):
    def __init__(self, message: str, *, details: Mapping[str, object] | None = None):
        super().__init__(code="LEDGER_REPAIR", message=message, details=details)


class PolicyError(TessraxError):
    def __init__(self, message: str, *, details: Mapping[str, object] | None = None):
        super().__init__(code="POLICY", message=message, details=details)


class DiagnosticError(TessraxError):
    def __init__(self, message: str, *, details: Mapping[str, object] | None = None):
        super().__init__(code="DIAG", message=message, details=details)


class SnapshotError(TessraxError):
    def __init__(self, message: str, *, details: Mapping[str, object] | None = None):
        super().__init__(code="SNAPSHOT", message=message, details=details)


class ReproducibilityError(TessraxError):
    def __init__(self, message: str, *, details: Mapping[str, object] | None = None):
        super().__init__(code="REPRO", message=message, details=details)


def classify_failure(error: Exception) -> dict[str, object]:
    if isinstance(error, TessraxError):
        return {"code": error.code, "message": error.message, "details": error.details or {}}
    return {"code": "GENERIC", "message": str(error), "details": {}}


__all__ = [
    "ReproducibilityError",
    "SnapshotError",
    "classify_failure",
    "DiagnosticError",
    "EpochError",
    "GovernanceTokenError",
    "LedgerRepairError",
    "PolicyError",
    "TessraxError",
]
