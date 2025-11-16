# Proceduralist Usage Guide

This document describes the deterministic workflows that ship with Proceduralist.
All commands MUST be executed from the repository root using **Python 3.11+**.

## Running the Governance Tooling

```bash
# Run the stress harness to generate a deterministic ledger
python -m tessrax.cli.tessraxctl stress-harness /tmp/ledger.jsonl --entries 512

# Verify governance state replay deterministically
python -m tessrax.cli.tessraxctl governance-replay /tmp/ledger.jsonl
```

## Repository Health + Cold Boot

```bash
python -m tessrax.cli.tessraxctl health-check
python -m tessrax.cli.tessraxctl cold-boot-audit
```

## Snapshot + Restore

```bash
python -m tessrax.cli.tessraxctl snapshot-export /tmp/ledger.snapshot
python -m tessrax.cli.tessraxctl snapshot-restore /tmp/ledger.snapshot
```

## Reproducibility Audit

```bash
python -m tessrax.cli.tessraxctl repro-audit
```

All commands emit JSON so they can be piped into additional tooling.
