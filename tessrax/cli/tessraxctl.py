"""tessraxctl — governance operations CLI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tessrax.diagnostics.auto_diag import auto_diagnose
from tessrax.docs.diagram_generator import generate_diagram
from tessrax.governance.explorer import explore
from tessrax.ledger.auto_repair import auto_repair, rebuild_index_from_ledger
from tessrax.ledger.merkle import MerkleAccumulator
from tessrax.ledger.receipt_diff import semantic_diff
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


COMMANDS = {
    "auto-repair": _cmd_auto_repair,
    "auto-diagnose": _cmd_auto_diag,
    "rebuild-index": _cmd_rebuild_index,
    "diff-receipts": _cmd_diff,
    "explore-governance": _cmd_explore,
    "stress-harness": _cmd_stress,
    "export-architecture": _cmd_architecture,
    "export-merkle-svg": _cmd_merkle_svg,
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

    args = parser.parse_args(argv)
    handler = COMMANDS[args.command]
    handler(args)


if __name__ == "__main__":  # pragma: no cover - manual entry point
    main()
