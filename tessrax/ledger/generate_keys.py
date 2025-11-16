"""Convenience wrapper that proxies to :mod:`tessrax.infra.generate_keys`."""

from __future__ import annotations

import sys

from tessrax.infra.generate_keys import generate as infra_generate, main as infra_main


def generate(*, force: bool = False, key_id: str | None = None):
    """Generate signing keys using the infrastructure helper."""

    return infra_generate(force=force, key_id=key_id or "legacy")


def main(argv: list[str] | None = None) -> None:
    infra_main(argv or sys.argv[1:])


if __name__ == "__main__":
    main()
