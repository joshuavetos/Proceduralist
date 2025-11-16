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
SIGNING_KEYS_DIR = INFRA_DIR / "signing_keys"
DEFAULT_KEY_ID = os.getenv("TESSRAX_KEY_ID", "legacy")


def generate(force: bool = False, *, key_id: str = DEFAULT_KEY_ID) -> Tuple[Path, Path]:
    INFRA_DIR.mkdir(parents=True, exist_ok=True)
    SIGNING_KEYS_DIR.mkdir(parents=True, exist_ok=True)
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
    keyed_public_path = SIGNING_KEYS_DIR / f"{key_id}.pub"
    keyed_public_path.write_text(public_hex + "\n", encoding="utf-8")

    return PRIVATE_KEY_PATH, keyed_public_path


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
