"""Repository health checker covering cold-start readiness."""
from __future__ import annotations

import platform
from dataclasses import dataclass
from pathlib import Path
from typing import List

AUDITOR_IDENTITY = "Tessrax Governance Kernel v16"


@dataclass(frozen=True)
class HealthCheck:
    name: str
    passed: bool
    details: dict[str, object]


@dataclass(frozen=True)
class RepositoryHealthReport:
    healthy: bool
    checks: List[HealthCheck]
    auditor: str = AUDITOR_IDENTITY


class RepositoryHealthChecker:
    """Perform deterministic repository inspections for CI and local runs."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[2])
        self.required_paths = [self.project_root / name for name in ("tessrax", "tests", "docs")]
        self.requirements_path = self.project_root / "requirements.txt"

    def _check_paths(self) -> HealthCheck:
        missing = [str(path) for path in self.required_paths if not path.exists()]
        return HealthCheck(
            name="filesystem",
            passed=not missing,
            details={"missing": missing, "scanned": [str(path) for path in self.required_paths]},
        )

    def _check_requirements(self) -> HealthCheck:
        required_packages = {"pytest", "pytest-cov"}
        if not self.requirements_path.exists():
            return HealthCheck("requirements", False, {"reason": "requirements.txt missing"})
        content = self.requirements_path.read_text(encoding="utf-8")
        missing = sorted(pkg for pkg in required_packages if pkg not in content)
        return HealthCheck(
            name="requirements",
            passed=not missing,
            details={"missing_packages": missing, "path": str(self.requirements_path)},
        )

    def _check_docs(self) -> HealthCheck:
        docs = self.project_root / "docs"
        reference_files = [docs / name for name in ("USAGE.md", "CLI.md", "MODULES.md")]
        missing = [str(path) for path in reference_files if not path.exists()]
        details = {
            "reference_files": [str(path) for path in reference_files],
            "missing": missing,
        }
        return HealthCheck(name="documentation", passed=not missing, details=details)

    def _environment(self) -> HealthCheck:
        details = {"python": platform.python_version(), "platform": platform.platform()}
        return HealthCheck(name="environment", passed=True, details=details)

    def run(self) -> RepositoryHealthReport:
        checks = [self._check_paths(), self._check_requirements(), self._check_docs(), self._environment()]
        healthy = all(check.passed for check in checks)
        return RepositoryHealthReport(healthy=healthy, checks=checks)


__all__ = ["HealthCheck", "RepositoryHealthChecker", "RepositoryHealthReport"]
