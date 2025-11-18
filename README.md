# Proceduralist V3

**auditor:** "Tessrax Governance Kernel v16"  
**clauses:** ["AEP-001","RVC-001","EAC-001","POST-AUDIT-001","DLK-001","TESST"]

## Quick Start

Spin up the stack with deterministic reproducibility using Docker Compose:

```bash
docker-compose up --build
```

## Demo

Generate sample data deterministically, then upload it through the UI:

```bash
python scripts/generate_demo_data.py
```

Drag the produced files into the frontend to explore ledger receipts and audit flows.

## Architecture

Proceduralist V3 pairs a deterministic core with a React-based frontend: the backend enforces append-only, hash-stable operations, while the UI surfaces governance and audit workflows without compromising reproducibility.
