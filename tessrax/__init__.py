"""Tessrax monorepo namespace exposing hardened governance utilities."""

from __future__ import annotations


def _bootstrap_nacl() -> None:
    try:
        import nacl.signing  # noqa: F401
    except Exception:  # pragma: no cover - executed in CI
        from tessrax._vendor import ed25519_nacl_fallback

        ed25519_nacl_fallback.install()


_bootstrap_nacl()


__all__ = [
    "aion",
    "core",
    "crawler",
    "dashboard",
    "governance",
    "infra",
    "ledger",
    "memory",
    "orchestrator",
    "services",
]
