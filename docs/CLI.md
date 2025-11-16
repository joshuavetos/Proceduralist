# tessraxctl Command Reference

`tessraxctl` exposes the developer-focused controls required by the Tessrax
Governance Kernel. Each sub-command performs a single deterministic operation
and prints a machine-readable JSON report.

| Command | Description |
| --- | --- |
| `auto-repair` | Repairs the Merkle state and ledger index. |
| `auto-diagnose` | Runs the diagnostics suite and prints an aggregated report. |
| `health-check` | Runs the repository health checker ensuring docs, tests, and requirements exist. |
| `repro-audit` | Performs an end-to-end reproducibility audit over ledger, merkle state, and requirements. |
| `snapshot-export <path>` | Exports ledger/index/merkle artifacts to a deterministic snapshot. |
| `snapshot-restore <snapshot>` | Restores artifacts from a snapshot file. |
| `merkle-profile <ledger>` | Profiles replay time with an optional `--threshold` guard. |
| `divergence-scan <ledger> <index> <merkle>` | Scans ledger/index/merkle for drift and prints a root-cause analysis. |
| `cold-boot-audit` | Validates the cold-start environment variables and file layout. |
| `governance-replay <ledger>` | Replays a ledger to validate governance receipts and Merkle root. |
| `load-test <output>` | Generates >10k deterministic receipts for stress testing. |

All commands can be invoked via `python -m tessrax.cli.tessraxctl <command>`.
