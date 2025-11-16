# Module Reference Overview

## Governance Coverage
- `tessrax.governance.coverage` provides the contradiction stress harness,
  governance replay simulator, receipt normalizer, and multi-sig verifier.

## Diagnostics
- `tessrax.diagnostics.repository_health` exposes the repository health checker.
- `tessrax.diagnostics.reproducibility` implements the reproducibility auditor.
- `tessrax.diagnostics.cold_boot` validates environment cold-boot readiness.

## Ledger
- `tessrax.ledger.snapshots` exports/restores ledger snapshots.
- `tessrax.ledger.merkle_profiler` profiles Merkle replay time with guard rails.
- `tessrax.ledger.divergence` scans ledger/index/merkle state drift.
- `tessrax.ledger.load_test` emits high-volume (>10k) deterministic receipts.

## Core
- `tessrax.core.hashing` implements deterministic hashing utilities with optional
  BLAKE3 support.

Each module includes stable dataclasses that return structured reports so that
CI workflows and operators can process results without parsing unstructured logs.
