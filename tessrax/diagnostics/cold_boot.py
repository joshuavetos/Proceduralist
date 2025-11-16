"""Environment cold-boot audit helpers."""
from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

AUDITOR_IDENTITY = "Tessrax Governance Kernel v16"


@dataclass(frozen=True)
class ColdBootAudit:
    python_version: str
    environment_ok: bool
    missing_env: Sequence[str]
    missing_paths: Sequence[str]
    required_paths: Sequence[str]
    auditor: str = AUDITOR_IDENTITY


def run_cold_boot_audit(
    *,
    required_env: Sequence[str] | None = None,
    required_paths: Sequence[Path] | None = None,
) -> ColdBootAudit:
    required_env = list(required_env or ("TESSRAX_KEY_ID", "TESSRAX_GOVERNANCE_TOKEN"))
    missing_env = [name for name in required_env if not os.getenv(name)]
    required_paths = list(required_paths or (Path("tessrax"), Path("tests")))
    missing_paths = [str(path) for path in required_paths if not Path(path).exists()]
    environment_ok = not missing_env and not missing_paths and sys.version_info >= (3, 11)
    return ColdBootAudit(
        python_version=platform.python_version(),
        environment_ok=environment_ok,
        missing_env=missing_env,
        missing_paths=missing_paths,
        required_paths=[str(path) for path in required_paths],
    )


__all__ = ["ColdBootAudit", "run_cold_boot_audit"]
