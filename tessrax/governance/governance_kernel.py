"""Proxy module forwarding to :mod:`tessrax.core.governance_kernel`."""

from tessrax.core.governance_kernel import (
    GovernanceDecision,
    Rationale,
    classify_clean,
    classify_contradiction,
)

__all__ = [
    "GovernanceDecision",
    "Rationale",
    "classify_clean",
    "classify_contradiction",
]
