"""Tessrax Governance Kernel v1.3 (Hardened).

This module consolidates the governance policies that determine whether a state
node is a contradiction requiring escalation or a clean verification.  It is
framework-agnostic: callers may pass any object exposing the attributes used in
this file (``id``, ``state_hash``, ``url``, ``title``).  Runtime validation
ensures deterministic behaviour regardless of caller context.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Protocol
import hashlib
import urllib.parse

from tessrax.core.time import canonical_datetime
from tessrax.governance.policy_registry import REGISTRY

DecisionType = Literal["LOGGED", "VERIFIED", "ESCALATE", "DEFER"]
SeverityTier = Literal["low", "medium", "high", "critical"]


class NodeView(Protocol):
    id: int | None
    state_hash: str | None
    url: str | None
    title: str | None


@dataclass(slots=True, frozen=True)
class Rationale:
    summary: str
    evidence: dict
    rules_applied: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class GovernanceDecision:
    decision: DecisionType
    severity: SeverityTier
    rationale: Rationale
    policy_code: str
    node_id: Optional[int]
    state_hash: Optional[str]
    category: Optional[str]
    tags: tuple[str, ...]
    recurrence_count: int
    first_seen: str
    last_seen: str
    confidence: float
    digest: str


def _policy_version() -> str:
    return REGISTRY.active_version()
BASE_POLICY = {
    "ERROR_PAGE": ("high", "POL#ERR_001"),
    "NOT_FOUND_404": ("high", "POL#ERR_404"),
    "DISABLED_ACTION": ("medium", "POL#UI_002"),
    "BROKEN_LINK": ("medium", "POL#NAV_003"),
    "UNKNOWN": ("high", "POL#UNK_000"),
}
CATEGORY_MAX = {
    "DISABLED_ACTION": "high",
    "BROKEN_LINK": "high",
    "ERROR_PAGE": "critical",
    "NOT_FOUND_404": "critical",
    "UNKNOWN": "critical",
}
ROOT_PATTERNS = {
    "paths": ["/", "/home", "/login", "/signin", "/dashboard", "/admin", "/checkout"],
    "title_keywords": ["home", "login", "signin", "dashboard", "landing"],
    "max_depth": 2,
}


def _compute_digest(*fields: str) -> str:
    joined = "|".join(fields)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:32]


def _depth_from_url(url: str | None) -> int:
    if not url:
        return 0
    path = urllib.parse.urlparse(url).path
    return len([part for part in path.split("/") if part])


def _is_root_state(node: NodeView) -> bool:
    url = (getattr(node, "url", None) or "").lower()
    title = (getattr(node, "title", None) or "").lower()
    parsed = urllib.parse.urlparse(url)
    depth = _depth_from_url(url)
    return (
        any(parsed.path.startswith(p) for p in ROOT_PATTERNS["paths"])
        or any(keyword in title for keyword in ROOT_PATTERNS["title_keywords"])
        or depth <= ROOT_PATTERNS["max_depth"]
    )


def _categorize(node: NodeView) -> tuple[str, tuple[str, ...]]:
    title = (getattr(node, "title", None) or "").lower()
    signals: list[str] = []
    if "404" in title or "not found" in title:
        signals.append("NOT_FOUND_404")
    if "error" in title or "exception" in title:
        signals.append("ERROR_PAGE")
    if "disabled" in title or title.startswith("trap: disabled"):
        signals.append("DISABLED_ACTION")
    if "broken" in title and "link" in title:
        signals.append("BROKEN_LINK")
    if not signals:
        return "UNKNOWN", tuple()
    priority = ["ERROR_PAGE", "NOT_FOUND_404", "DISABLED_ACTION", "BROKEN_LINK"]
    signals_sorted = sorted(signals, key=lambda s: priority.index(s))
    return signals_sorted[0], tuple(signals)


def _adjust_severity(base: SeverityTier, category: str, is_root: bool, signals: tuple[str, ...], title: str | None) -> SeverityTier:
    order = ["low", "medium", "high", "critical"]
    idx = order.index(base)
    if is_root and idx < 3:
        idx += 1
    danger_words = ("error", "fatal", "exception", "failure", "invalid")
    lowered = (title or "").lower()
    if any(word in lowered for word in danger_words) and idx < 3:
        idx += 1
    idx = min(idx, order.index(CATEGORY_MAX.get(category, "critical")))
    return order[idx]


def _should_escalate(severity: SeverityTier, category: str, is_root: bool, signals: tuple[str, ...]) -> bool:
    if severity == "critical":
        return True
    if severity == "high" and is_root:
        return True
    if "ERROR_PAGE" in signals or "NOT_FOUND_404" in signals:
        return True
    if category == "UNKNOWN" and is_root:
        return True
    return False


def _timestamp() -> str:
    return canonical_datetime()


def classify_contradiction(node: NodeView, *, recurrence_count: int = 0, first_seen: Optional[str] = None) -> GovernanceDecision:
    category, signals = _categorize(node)
    base_severity, base_policy = BASE_POLICY.get(category, BASE_POLICY["UNKNOWN"])
    is_root = _is_root_state(node)
    severity = _adjust_severity(base_severity, category, is_root, signals, getattr(node, "title", None))
    decision_type: DecisionType = "ESCALATE" if _should_escalate(severity, category, is_root, signals) else "LOGGED"
    now = _timestamp()
    rationale = Rationale(
        summary=f"Contradiction classified as {category} (severity={severity}).",
        evidence={
            "url": getattr(node, "url", None),
            "title": getattr(node, "title", None),
            "signals": list(signals),
            "is_root_state": is_root,
            "recurrence_count": recurrence_count,
        },
        rules_applied=(
            f"baseline:{base_severity}",
            f"adjusted:{severity}",
            f"signals:{','.join(signals) or 'none'}",
            f"root:{is_root}",
        ),
    )
    policy_code = f"{base_policy}@{_policy_version()}"
    digest = _compute_digest(
        decision_type,
        severity,
        policy_code,
        category,
        str(getattr(node, "id", "")),
        getattr(node, "state_hash", "") or "",
        now,
    )
    return GovernanceDecision(
        decision=decision_type,
        severity=severity,
        rationale=rationale,
        policy_code=policy_code,
        node_id=getattr(node, "id", None),
        state_hash=getattr(node, "state_hash", None),
        category=category,
        tags=("contradiction", f"cat:{category}", f"severity:{severity}", f"policy:{_policy_version()}"),
        recurrence_count=recurrence_count,
        first_seen=first_seen or now,
        last_seen=now,
        confidence=1.0,
        digest=digest,
    )


def classify_clean(node: NodeView, *, recurrence_count: int = 0, first_seen: Optional[str] = None) -> GovernanceDecision:
    is_root = _is_root_state(node)
    severity: SeverityTier = "medium" if is_root else "low"
    now = _timestamp()
    rationale = Rationale(
        summary="Clean state verified.",
        evidence={
            "url": getattr(node, "url", None),
            "title": getattr(node, "title", None),
            "is_root_state": is_root,
        },
        rules_applied=("clean_state", f"severity:{severity}"),
    )
    policy_code = f"POL#CLEAN_000@{_policy_version()}"
    digest = _compute_digest(
        "VERIFIED",
        severity,
        policy_code,
        "CLEAN",
        str(getattr(node, "id", "")),
        getattr(node, "state_hash", "") or "",
        now,
    )
    return GovernanceDecision(
        decision="VERIFIED",
        severity=severity,
        rationale=rationale,
        policy_code=policy_code,
        node_id=getattr(node, "id", None),
        state_hash=getattr(node, "state_hash", None),
        category="CLEAN",
        tags=("clean", f"severity:{severity}", f"policy:{_policy_version()}"),
        recurrence_count=recurrence_count,
        first_seen=first_seen or now,
        last_seen=now,
        confidence=1.0,
        digest=digest,
    )


__all__ = ["GovernanceDecision", "Rationale", "classify_contradiction", "classify_clean"]
