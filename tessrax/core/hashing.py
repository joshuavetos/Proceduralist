"""Deterministic hashing toolkit with optional BLAKE3 support."""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from tessrax.core.serialization import canonical_json, normalize_payload

AUDITOR_IDENTITY = "Tessrax Governance Kernel v16"


@dataclass(frozen=True)
class HashResult:
    algorithm: str
    digest: str
    bytes_processed: int
    auditor: str = AUDITOR_IDENTITY


class DeterministicHasher:
    """Streaming hasher that enforces deterministic encoding for payloads."""

    def __init__(self, algorithm: str = "sha256") -> None:
        self.algorithm = algorithm.lower()
        try:
            self._hasher = hashlib.new(self.algorithm)
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise ValueError(f"Unsupported hash algorithm '{algorithm}'") from exc
        self._bytes = 0

    def update(self, data: bytes) -> None:
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("Hasher update expects bytes-like input")
        self._hasher.update(data)
        self._bytes += len(data)

    def update_payload(self, payload: Mapping[str, object]) -> None:
        canonical = canonical_json(normalize_payload(payload)).encode("utf-8")
        self.update(canonical)

    def digest(self) -> HashResult:
        return HashResult(
            algorithm=self.algorithm,
            digest=self._hasher.hexdigest(),
            bytes_processed=self._bytes,
        )

    def hexdigest(self) -> str:  # pragma: no cover - passthrough
        return self._hasher.hexdigest()


def _load_blake3():
    module = importlib.util.find_spec("blake3")
    if module is None:
        return None
    return importlib.import_module("blake3")


def blake3_digest(data: bytes) -> HashResult:
    blake3_module = _load_blake3()
    if blake3_module is None:
        raise RuntimeError("blake3 package is not installed; install 'blake3' for optional support")
    hasher = blake3_module.blake3()
    hasher.update(data)
    return HashResult(algorithm="blake3", digest=hasher.hexdigest(), bytes_processed=len(data))


def hash_paths(paths: Sequence[Path]) -> HashResult:
    hasher = DeterministicHasher()
    for path in sorted(Path(p) for p in paths):
        data = path.read_bytes() if path.exists() else b""
        hasher.update(data)
    return hasher.digest()


__all__ = ["HashResult", "DeterministicHasher", "blake3_digest", "hash_paths"]
