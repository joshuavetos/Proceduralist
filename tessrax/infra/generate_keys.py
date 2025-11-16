"""Generate Ed25519 signing + verification keys for Tessrax OS."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Tuple

from nacl.signing import SigningKey

INFRA_DIR = Path(__file__).resolve().parent
PRIVATE_KEY_PATH = INFRA_DIR / "signing_key.pem"
PUBLIC_KEY_PATH = INFRA_DIR / "signing_key.pub"


def generate(force: bool = False) -> Tuple[Path, Path]:
    INFRA_DIR.mkdir(parents=True, exist_ok=True)
    if not force and (PRIVATE_KEY_PATH.exists() or PUBLIC_KEY_PATH.exists()):
        raise FileExistsError(
            "Signing key already exists. Pass --force to overwrite (will invalidate old signatures)."
        )

    signing_key = SigningKey.generate()
    private_hex = signing_key.encode().hex()
    public_hex = signing_key.verify_key.encode().hex()

    PRIVATE_KEY_PATH.write_text(private_hex + "\n", encoding="utf-8")
    os.chmod(PRIVATE_KEY_PATH, 0o600)
    PUBLIC_KEY_PATH.write_text(public_hex + "\n", encoding="utf-8")

    return PRIVATE_KEY_PATH, PUBLIC_KEY_PATH


def main(argv: list[str]) -> None:
    force = "--force" in argv
    private_path, public_path = generate(force=force)
    print(f"[tessrax] Signing key saved to {private_path}")
    print(f"[tessrax] Verification key saved to {public_path}")


if __name__ == "__main__":
    main(sys.argv[1:])
