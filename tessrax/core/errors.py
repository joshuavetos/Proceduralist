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


__all__ = [
    "DiagnosticError",
    "EpochError",
    "GovernanceTokenError",
    "LedgerRepairError",
    "PolicyError",
    "TessraxError",
]
