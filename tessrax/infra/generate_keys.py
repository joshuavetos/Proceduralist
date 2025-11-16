"""Generate or rotate Ed25519 signing keys via the key registry."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Tuple

from tessrax.infra import key_registry

INFRA_DIR = Path(__file__).resolve().parent
DEFAULT_KEY_ID = os.getenv("TESSRAX_KEY_ID", "legacy")


def generate(
    force: bool = False,
    *,
    key_id: str = DEFAULT_KEY_ID,
    reason: str = "manual-generate",
    governance_token: str | None = None,
) -> Tuple[Path, Path]:
    """Rotate to ``key_id`` via the registry, returning (private, public) paths."""

    token = governance_token or os.getenv("TESSRAX_GOVERNANCE_TOKEN", "manual")
    return key_registry.rotate_key(
        reason=reason,
        governance_token=token,
        new_key_id=key_id,
        force=force,
    )


def _parse_args(argv: list[str]) -> tuple[bool, str]:
    force = "--force" in argv
    key_id = DEFAULT_KEY_ID
    for arg in argv:
        if arg.startswith("--key-id="):
            key_id = arg.split("=", 1)[1] or DEFAULT_KEY_ID
    return force, key_id


def main(argv: list[str]) -> None:
    force, key_id = _parse_args(argv)
    private_path, public_path = generate(force=force, key_id=key_id)
    print(f"[tessrax] Signing key saved to {private_path}")
    print(f"[tessrax] Verification key saved to {public_path}")


if __name__ == "__main__":
    main(sys.argv[1:])
