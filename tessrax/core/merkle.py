"""Merkle tree implementation for Tessrax."""
from __future__ import annotations

import math
from typing import List, Any, Optional
from tessrax.core.serialization import canonical_serialize
from tessrax.core.hashing import DeterministicHasher, HashResult


class MerkleNode:
    """Represents a node in the Merkle tree."""
    def __init__(self, left: Optional["MerkleNode"], right: Optional["MerkleNode"], data_hash: Optional[bytes] = None, hash_value: Optional[str] = None) -> None:
        self.left = left
        self.right = right
        if hash_value is None:
            # If it's a leaf node and data_hash is provided
            if data_hash is not None:
                hasher = DeterministicHasher()
                hasher.update(data_hash)  # Use the pre-canonicalized data hash
                self.hash_value = hasher.digest().digest
            # If it's an internal node, hash children's hashes
            elif left is not None and right is not None:
                hasher = DeterministicHasher()
                hasher.update(left.hash_value.encode('utf-8'))
                hasher.update(right.hash_value.encode('utf-8'))
                self.hash_value = hasher.digest().digest
            elif left is not None:  # Single child case for odd number of leaves
                self.hash_value = left.hash_value
            else:
                raise ValueError("Cannot create a MerkleNode without data_hash or child hashes.")
        else:
            self.hash_value = hash_value

    def __repr__(self) -> str:
        return f"MerkleNode(hash='{self.hash_value[:8]}...')"


class MerkleTree:
    """Builds and manages a Merkle tree from a list of data blocks."""
    def __init__(self, data_blocks: List[Any]) -> None:
        if not data_blocks:
            raise ValueError("Data blocks cannot be empty for MerkleTree construction.")
        self.leaves: List[MerkleNode] = []
        for block in data_blocks:
            # Canonicalize block here before creating the leaf node
            canonical_block_bytes = canonical_serialize(block)
            self.leaves.append(MerkleNode(None, None, data_hash=canonical_block_bytes))
        self.root: MerkleNode = self._build_tree(self.leaves)

    def _build_tree(self, nodes: List[MerkleNode]) -> MerkleNode:
        if len(nodes) == 1:
            return nodes[0]
        next_level: List[MerkleNode] = []
        for i in range(0, len(nodes), 2):
            left = nodes[i]
            right = nodes[i + 1] if i + 1 < len(nodes) else left  # Handle odd number of leaves by duplicating the last one
            parent = MerkleNode(left, right)
            next_level.append(parent)
        return self._build_tree(next_level)

    @property
    def root_hash(self) -> str:
        """Returns the root hash of the Merkle tree."""
        return self.root.hash_value


__all__ = ["MerkleNode", "MerkleTree"]
