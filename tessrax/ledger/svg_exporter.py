"""Exports a Merkle state visualization as SVG."""
from __future__ import annotations

from pathlib import Path

from tessrax.core.time import canonical_datetime
from tessrax.ledger.merkle import MerkleState


def export_merkle_svg(state: MerkleState, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "<svg xmlns='http://www.w3.org/2000/svg' width='400' height='200'>",
        "  <text x='200' y='20' text-anchor='middle' font-size='14'>Merkle State</text>",
    ]
    for idx, peak in enumerate(state.peaks):
        x = 40 + idx * 60
        lines.append(
            f"  <rect x='{x}' y='60' width='50' height='30' fill='#123' stroke='#0ff'/>"
        )
        lines.append(
            f"  <text x='{x + 25}' y='80' text-anchor='middle' font-size='10' fill='#fff'>{peak[:8]}</text>"
        )
    lines.append(
        f"  <text x='200' y='150' text-anchor='middle' font-size='12'>root={state.root()[:16]} updated={canonical_datetime()}</text>"
    )
    lines.append("</svg>")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


__all__ = ["export_merkle_svg"]
