"""tessraxctl — governance operations CLI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tessrax.diagnostics.auto_diag import auto_diagnose
from tessrax.diagnostics.cold_boot import run_cold_boot_audit
from tessrax.diagnostics.repository_health import RepositoryHealthChecker
from tessrax.diagnostics.reproducibility import audit_reproducibility
from tessrax.docs.diagram_generator import generate_diagram
from tessrax.governance.explorer import explore
from tessrax.governance.coverage import governance_replay_simulator
from tessrax.ledger.auto_repair import auto_repair, rebuild_index_from_ledger
from tessrax.ledger.divergence import analyze_root_cause, scan_state_divergence
from tessrax.ledger.load_test import generate_high_volume_receipts
from tessrax.ledger.merkle import MerkleAccumulator
from tessrax.ledger.merkle_profiler import profile_replay
from tessrax.ledger.receipt_diff import semantic_diff
from tessrax.ledger.snapshots import export_snapshot, restore_snapshot
from tessrax.ledger.svg_exporter import export_merkle_svg
from tessrax.ledger.stress_harness import generate_stress_ledger


def _cmd_auto_repair(args: argparse.Namespace) -> None:
    report = auto_repair()
    print(json.dumps(report, indent=2))


def _cmd_rebuild_index(args: argparse.Namespace) -> None:
    count = rebuild_index_from_ledger()
    print(json.dumps({"entries": count}, indent=2))


def _cmd_diff(args: argparse.Namespace) -> None:
    left = json.loads(Path(args.left).read_text(encoding="utf-8"))
    right = json.loads(Path(args.right).read_text(encoding="utf-8"))
    diff = semantic_diff(left, right)
    print(json.dumps(diff, indent=2))


def _cmd_explore(args: argparse.Namespace) -> None:
    summary = explore()
    print(json.dumps(summary.__dict__, indent=2))


def _cmd_stress(args: argparse.Namespace) -> None:
    result = generate_stress_ledger(output_path=Path(args.output), entries=args.entries)
    print(json.dumps(result.__dict__, indent=2))


def _cmd_architecture(args: argparse.Namespace) -> None:
    path = generate_diagram(Path(args.output))
    print(f"diagram written to {path}")


def _cmd_merkle_svg(args: argparse.Namespace) -> None:
    accumulator = MerkleAccumulator()
    path = export_merkle_svg(accumulator.state, Path(args.output))
    print(f"svg exported to {path}")


def _cmd_auto_diag(args: argparse.Namespace) -> None:
    report = auto_diagnose()
    print(json.dumps(report, indent=2))


def _cmd_health_check(args: argparse.Namespace) -> None:
    checker = RepositoryHealthChecker()
    report = checker.run()
    print(json.dumps(report.__dict__, default=lambda o: o.__dict__, indent=2))


def _cmd_repro_audit(args: argparse.Namespace) -> None:
    report = audit_reproducibility()
    print(json.dumps(report.__dict__, default=lambda o: o.__dict__, indent=2))


def _cmd_snapshot_export(args: argparse.Namespace) -> None:
    snapshot = export_snapshot(snapshot_path=Path(args.output))
    print(json.dumps(snapshot.__dict__, default=lambda o: o.__dict__, indent=2))


def _cmd_snapshot_restore(args: argparse.Namespace) -> None:
    metadata = restore_snapshot(snapshot_path=Path(args.snapshot))
    print(json.dumps(metadata.__dict__, indent=2))


def _cmd_merkle_profile(args: argparse.Namespace) -> None:
    profile = profile_replay(ledger_path=Path(args.ledger), threshold_seconds=args.threshold)
    print(json.dumps(profile.__dict__, indent=2))


def _cmd_divergence_scan(args: argparse.Namespace) -> None:
    report = scan_state_divergence(ledger_path=Path(args.ledger), index_path=Path(args.index), merkle_state_path=Path(args.merkle))
    rca = analyze_root_cause(report)
    payload = {"report": report.__dict__, "root_cause": rca.__dict__}
    print(json.dumps(payload, indent=2))


def _cmd_cold_boot(args: argparse.Namespace) -> None:
    audit = run_cold_boot_audit()
    print(json.dumps(audit.__dict__, indent=2))


def _cmd_governance_replay(args: argparse.Namespace) -> None:
    report = governance_replay_simulator(ledger_path=Path(args.ledger))
    print(json.dumps(report.__dict__, indent=2))


def _cmd_load_test(args: argparse.Namespace) -> None:
    summary = generate_high_volume_receipts(output_path=Path(args.output), batches=args.batches, batch_size=args.batch_size)
    print(json.dumps(summary.__dict__, indent=2))


COMMANDS = {
    "auto-repair": _cmd_auto_repair,
    "auto-diagnose": _cmd_auto_diag,
    "rebuild-index": _cmd_rebuild_index,
    "diff-receipts": _cmd_diff,
    "explore-governance": _cmd_explore,
    "stress-harness": _cmd_stress,
    "export-architecture": _cmd_architecture,
    "export-merkle-svg": _cmd_merkle_svg,
    "health-check": _cmd_health_check,
    "repro-audit": _cmd_repro_audit,
    "snapshot-export": _cmd_snapshot_export,
    "snapshot-restore": _cmd_snapshot_restore,
    "merkle-profile": _cmd_merkle_profile,
    "divergence-scan": _cmd_divergence_scan,
    "cold-boot-audit": _cmd_cold_boot,
    "governance-replay": _cmd_governance_replay,
    "load-test": _cmd_load_test,
}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="tessraxctl")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("auto-repair")
    subparsers.add_parser("auto-diagnose")
    subparsers.add_parser("rebuild-index")

    diff_parser = subparsers.add_parser("diff-receipts")
    diff_parser.add_argument("left")
    diff_parser.add_argument("right")

    subparsers.add_parser("explore-governance")

    stress_parser = subparsers.add_parser("stress-harness")
    stress_parser.add_argument("output")
    stress_parser.add_argument("--entries", type=int, default=10_000)

    arch_parser = subparsers.add_parser("export-architecture")
    arch_parser.add_argument("output")

    svg_parser = subparsers.add_parser("export-merkle-svg")
    svg_parser.add_argument("output")

    subparsers.add_parser("health-check")
    subparsers.add_parser("repro-audit")

    snapshot_export = subparsers.add_parser("snapshot-export")
    snapshot_export.add_argument("output")

    snapshot_restore = subparsers.add_parser("snapshot-restore")
    snapshot_restore.add_argument("snapshot")

    merkle_profile = subparsers.add_parser("merkle-profile")
    merkle_profile.add_argument("ledger")
    merkle_profile.add_argument("--threshold", type=float, default=1.0)

    divergence = subparsers.add_parser("divergence-scan")
    divergence.add_argument("ledger")
    divergence.add_argument("index")
    divergence.add_argument("merkle")

    subparsers.add_parser("cold-boot-audit")

    governance = subparsers.add_parser("governance-replay")
    governance.add_argument("ledger")

    load_test = subparsers.add_parser("load-test")
    load_test.add_argument("output")
    load_test.add_argument("--batches", type=int, default=5)
    load_test.add_argument("--batch-size", type=int, default=2500)

    args = parser.parse_args(argv)
    handler = COMMANDS[args.command]
    handler(args)


if __name__ == "__main__":  # pragma: no cover - manual entry point
    main()
