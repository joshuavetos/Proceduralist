"""Compatibility namespace exposing governance kernel utilities."""

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
