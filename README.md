# Proceduralist

Proceduralist is a high‑assurance governance and verification engine that combines an append‑only ledger, policy‑driven decision kernel, deterministic hashing, and audit‑ready reporting. The project ships with a FastAPI backend, a minimal Next.js frontend, and a CLI toolchain that exercises the full Tessrax governance stack.

![Build](https://github.com/joshuavetos/Proceduralist/actions/workflows/tests.yml/badge.svg)
![Coverage](https://img.shields.io/codecov/c/github/joshuavetos/Proceduralist)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Quick start

Requirements: **Python 3.11+** with `pip` available.

```bash
git clone https://github.com/joshuavetos/Proceduralist.git
cd Proceduralist
pip install -r requirements.txt
pytest -q
```

Key entry points:

- CLI: `python -m tessrax.cli.tessraxctl <command>`
- Backend (FastAPI): `uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000`
- Frontend (Next.js): run with your preferred Next.js runner against the backend API

---

## What Proceduralist provides

- **Ledger engine** — append‑only JSONL ledger with Merkle‑verified state, canonical serialization, snapshot/export tooling, and deterministic replay.
- **Governance kernel** — quorum simulation, policy receipts, receipt diffing, and governance replay with contradiction stress testing.
- **Diagnostics & audits** — reproducibility auditor, cold‑boot/environment validator, repository health checker, drift/divergence scanner, and automatic Merkle/index repair.
- **Developer tooling** — CLI (`tessraxctl`) exposes deterministic subcommands, FastAPI backend surfaces REST endpoints, and a lightweight Next.js UI provides quick audit interactions.

---

## Repository structure

```
backend/       FastAPI application (routers under backend/api) and queue/analyzer helpers
frontend/      Minimal Next.js UI for starting audits
tessrax/       Core governance, ledger, diagnostics, hashing, and CLI modules
docs/          Reference guides (CLI, usage, reproducibility, roadmap, diagrams)
tests/         Pytest suite covering governance, ledger, and diagnostic flows
docker-compose.yml  Dev stack with PostgreSQL and backend service
```

---

## CLI usage (`tessraxctl`)

All commands emit JSON for deterministic downstream processing. Run from the repo root:

```bash
python -m tessrax.cli.tessraxctl auto-diagnose           # Aggregated diagnostics
python -m tessrax.cli.tessraxctl health-check            # Repository health scan
python -m tessrax.cli.tessraxctl repro-audit             # Reproducibility audit
python -m tessrax.cli.tessraxctl stress-harness /tmp/ledger.jsonl --entries 512
python -m tessrax.cli.tessraxctl governance-replay /tmp/ledger.jsonl
python -m tessrax.cli.tessraxctl snapshot-export /tmp/ledger.snapshot
python -m tessrax.cli.tessraxctl snapshot-restore /tmp/ledger.snapshot
python -m tessrax.cli.tessraxctl divergence-scan ledger.jsonl index.db merkle_state.json
python -m tessrax.cli.tessraxctl load-test /tmp/receipts.jsonl --batches 5 --batch-size 2500
```

See [`docs/CLI.md`](docs/CLI.md) and [`docs/USAGE.md`](docs/USAGE.md) for the full matrix of commands and workflows.

---

## Running the backend API

The FastAPI service exposes governance analysis, audit, replay, and history endpoints via routers defined in `backend/api`.

```bash
pip install -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Alternatively, start the PostgreSQL + backend stack with Docker Compose:

```bash
docker-compose up --build
```

The Compose file provisions PostgreSQL with health checks, installs dependencies, and launches the backend on port **8000**.

---

## Frontend

The `frontend/` directory contains a minimal Next.js UI with two pages:

- `pages/index.js` — landing page linking to audit creation
- `pages/new-audit.js` — form that POSTs to `/api/audit/start` and routes to `/gallery/{id}` on success

Point the frontend at the running backend API to initiate and view audits.

---

## Testing & quality

Run the full test suite:

```bash
pytest -q
```

Generate coverage with XML output (used by CI + Codecov):

```bash
pytest --cov=tessrax --cov-report=term-missing --cov-report=xml
```

Static analysis uses `ruff` according to the pinned version in `requirements.txt`.

---

## Documentation

- [`docs/CLI.md`](docs/CLI.md) — command reference for `tessraxctl`
- [`docs/USAGE.md`](docs/USAGE.md) — deterministic workflows and sample invocations
- [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md) — reproducibility auditor internals
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — planned enhancements and milestones
- [`docs/MODULES.md`](docs/MODULES.md) — module-level responsibilities
- [`docs/architecture.svg`](docs/architecture.svg) — high-level architecture diagram

---

## License

Proceduralist is released under the MIT License. See [`LICENSE`](LICENSE) for details.

