# Proceduralist

Proceduralist is a hardened, self-auditing governance engine designed for environments where integrity, traceability, and deterministic behavior are non-negotiable. It provides a unified framework for append-only ledgering, policy-driven governance decisions, reproducible state verification, and cryptographically signed memory operations.

This repository represents the reference implementation of the Proceduralist Engine, built to power high-assurance systems, agent orchestration frameworks, and autonomous auditing pipelines.

## Features

### Ledger System
- Merkle-verified append-only ledger (`ledger.jsonl`)
- Immutable hash-chained entries
- Deterministic serialization and hashing
- Corruption detection and Merkle-state replay
- Indexed database for fast lookup and historical inspection

### Governance Kernel
- Policy-driven evaluation
- Quorum simulation
- Version-pinned policies with rollback capability
- Governance tokens with freshness validation
- Verified decision receipts

### Memory Engine
- Canonical serialization (deterministic JSON)
- Immutable payload snapshots
- Ed25519 signatures (PyNaCl or OpenSSL fallback)
- State hashing for reproducible audits
- Cold-start reproducibility guarantees

### Verification Pipeline
- End-to-end reproducibility tests
- Environment cold-boot verification
- State divergence detection (index ↔ ledger ↔ merkle)
- Structured exception model for predictable failure modes

## Installation

Proceduralist requires Python 3.11+.

```
git clone https://github.com/joshuavetos/Proceduralist.git
cd Proceduralist
pip install -r requirements.txt
```

## Running Tests

Proceduralist includes a comprehensive test suite covering the serialization engine, Merkle accumulator, memory engine, key-management subsystem, and governance kernel.

```
pytest -q
```

To run coverage:

```
pytest --cov=tessrax --cov-report=term-missing
```

## Project Layout

```
tessrax/
  core/
    memory_engine.py
    governance_kernel.py
    serialization.py
  ledger/
    ledger.jsonl
    index.db
    merkle_state.json
  infra/
    key_registry.py
tests/
docs/
```

## Roadmap

A complete roadmap is maintained at `docs/ROADMAP.md` and includes planned improvements to:
- Ledger compaction and snapshotting
- Multi-signature governance
- Sharded ledger segments and concurrency improvements
- CLI tools for inspection and debugging
- Advanced validation and policy engines
- Rust-backed hashing options
- Visualization tools

## Philosophy

Proceduralist is built on four principles:

1. **Determinism**  
   Every component must behave identically across environments and cold starts.

2. **Auditability**  
   All outputs must be verifiable, reproducible, and permanently traceable.

3. **Integrity**  
   No hidden state, no mutable history, no ambiguity in serialization or hashing.

4. **Governance as Code**  
   Decisions must be governed by explicit, inspectable policy rather than implicit behavior.

## License

MIT License. See `LICENSE` for details.
