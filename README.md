# Proceduralist

Proceduralist is a high‑assurance governance and verification engine designed for systems where determinism, traceability, and audit integrity must be guaranteed. It provides a unified framework for append‑only ledgering, policy‑driven decision making, verifiable state transitions, and cryptographically signed memory operations.

This repository contains the reference implementation of the Proceduralist Engine.

---

## Overview

Proceduralist integrates four core components:

### 1. Ledger System  
A Merkle‑verified, append‑only ledger with:

- hash‑chained entries  
- canonical serialization  
- corruption detection and recovery  
- indexed historical lookup  
- reproducible state replay  

### 2. Governance Kernel  
A policy‑driven decision engine featuring:

- quorum simulation  
- version‑pinned policies  
- rollback capability  
- governance token freshness checks  
- deterministic decision receipts  

### 3. Memory Engine  
A signing and serialization layer providing:

- canonical JSON normalization  
- immutable payload snapshots  
- Ed25519 signatures (PyNaCl or OpenSSL fallback)  
- deterministic hashing  
- reproducible cold‑start behavior  

### 4. Verification Pipeline  
End‑to‑end integrity checks:

- environment cold‑boot verification  
- state divergence detection  
- exception consistency rules  
- reproducibility tests  
- strict serialization guarantees  

---

## Installation

Requirements: **Python 3.11+**

```bash
git clone https://github.com/joshuavetos/Proceduralist.git
cd Proceduralist
pip install -r requirements.txt
```

---

## Running Tests

```bash
pytest -q
```

Coverage:

```bash
pytest --cov=tessrax --cov-report=term-missing
```

---

## Project Structure

```
tessrax/
  core/
    memory_engine.py
    governance_kernel.py
    serialization.py
  infra/
    key_registry.py
  ledger/
    ledger.jsonl
    index.db
    merkle_state.json
tests/
docs/
```

---

## Documentation

Extended documentation and architectural references are in:

- `docs/ROADMAP.md`
- `docs/architecture.svg`
- `tessrax/core/` inline module documentation

---

## Roadmap Summary

Future enhancements include:

- ledger snapshot formats  
- multi‑signature governance  
- sharded ledger and parallel replay  
- deterministic hash pipelines (BLAKE3 optional)  
- visualization and inspection tooling  
- Rust‑backed hashing module  
- expanded test matrices  

Full roadmap is maintained in `docs/ROADMAP.md`.

---

## Design Principles

Proceduralist is built around four principles:

### Determinism  
Identical results across environments, cold starts, and machines.

### Auditability  
All outputs must be verifiable, reproducible, and permanently traceable.

### Integrity  
No hidden state, no silent mutation, no ambiguous serialization.

### Governance as Code  
All decisions governed by explicit, inspectable, versioned policy.

---

## License

Proceduralist is released under the MIT License.  
See `LICENSE` for details.
