"""Deterministic ingestion and analysis engine for the Proceduralist API."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

from server.services.contradictions import detect_conflicts

try:  # AEP-001: validate serialization imports eagerly.
    from tessrax.core.serialization import canonical_serialize, canonical_payload_hash
    from tessrax.core.merkle import MerkleTree
except Exception:  # pragma: no cover - hardened fallback for cold-start envs
    def canonical_serialize(obj: Any) -> bytes:
        normalized = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return normalized.encode("utf-8")

    def canonical_payload_hash(payload: Dict[str, Any]) -> str:
        materialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(materialized.encode("utf-8")).hexdigest()

    class MerkleTree:  # type: ignore[misc]
        def __init__(self, data_blocks: List[Any]) -> None:
            if not data_blocks:
                raise ValueError("Data blocks cannot be empty for MerkleTree construction.")
            self._data = [canonical_serialize(block) for block in data_blocks]
            self.root_hash = self._calculate_root()

        def _calculate_root(self) -> str:
            layer = [hashlib.sha256(block).hexdigest() for block in self._data]
            while len(layer) > 1:
                next_layer: List[str] = []
                for index in range(0, len(layer), 2):
                    left = layer[index]
                    right = layer[index + 1] if index + 1 < len(layer) else layer[index]
                    combined = hashlib.sha256(f"{left}{right}".encode("utf-8")).hexdigest()
                    next_layer.append(combined)
                layer = next_layer
            return layer[0]

        @property
        def root_hash_value(self) -> str:
            return self.root_hash


GOVERNANCE_METADATA = {
    "auditor": "Tessrax Governance Kernel v16",
    "clauses": ["AEP-001", "RVC-001", "EAC-001", "POST-AUDIT-001", "DLK-001", "TESST"],
}


def _sha256_digest(raw: bytes) -> str:
    digest = hashlib.sha256(raw).hexdigest()
    assert digest, "Digest calculation must produce a non-empty hash"
    return digest


def _prepare_artifact(base: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise artifact structure for serialization."""

    if "sha256" not in base:
        raise ValueError("All artifacts must include a sha256 digest before serialization")
    ordered = dict(sorted(base.items(), key=lambda item: item[0]))
    ordered["__integrity__"] = canonical_payload_hash({"sha256": ordered["sha256"], "type": ordered["type"]})
    return ordered


async def ingest_data(files: List[Any], text: str | None, url: str | None) -> List[Dict[str, Any]]:
    """Ingest heterogeneous inputs into deterministic artifact records."""

    artifacts: List[Dict[str, Any]] = []

    if text and text.strip():
        normalized = text.strip()
        artifacts.append(
            _prepare_artifact(
                {
                    "type": "text",
                    "content": normalized,
                    "length": len(normalized),
                    "sha256": _sha256_digest(normalized.encode("utf-8")),
                }
            )
        )

    if url and url.strip():
        normalized_url = url.strip()
        artifacts.append(
            _prepare_artifact(
                {
                    "type": "url",
                    "value": normalized_url,
                    "length": len(normalized_url),
                    "sha256": _sha256_digest(normalized_url.encode("utf-8")),
                }
            )
        )

    for upload in files:
        content = await upload.read()
        if content is None:
            content = b""
        artifacts.append(
            _prepare_artifact(
                {
                    "type": "file",
                    "name": upload.filename or "unnamed",
                    "length": len(content),
                    "sha256": _sha256_digest(content),
                }
            )
        )

    if not artifacts:
        raise ValueError("ingest_data requires at least one non-empty artifact input")

    return artifacts


def run_deterministic_core(artifacts: List[Dict[str, Any]]) -> str:
    """Generate a Merkle root from canonicalized artifacts with validation."""

    if not artifacts:
        raise ValueError("run_deterministic_core cannot operate on an empty artifact list")

    normalized_blocks = [canonical_serialize(artifact) for artifact in artifacts]
    assert all(block for block in normalized_blocks), "Canonical serialization produced empty payload"

    tree = MerkleTree(artifacts)
    root_hash = getattr(tree, "root_hash", None) or getattr(tree, "root_hash_value", None)
    if not root_hash:
        raise RuntimeError("MerkleTree did not return a root hash")

    validation = canonical_payload_hash({"root": root_hash, "artifacts": [_sha256_digest(block) for block in normalized_blocks]})
    if len(validation) != 64:
        raise RuntimeError("Canonical hash validation failed to produce a 64-character digest")

    return root_hash


def detect_contradictions(artifacts: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Apply deterministic checks for obvious contradictions."""

    return detect_conflicts(artifacts)


def count_artifacts(artifacts: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"file": 0, "text": 0, "url": 0}
    for artifact in artifacts:
        counts[artifact["type"]] += 1
    return counts


__all__ = [
    "GOVERNANCE_METADATA",
    "ingest_data",
    "run_deterministic_core",
    "detect_contradictions",
    "count_artifacts",
]
