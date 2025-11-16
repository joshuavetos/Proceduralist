from __future__ import annotations

from pathlib import Path

from tessrax.diagnostics.cold_boot import run_cold_boot_audit
from tessrax.diagnostics.repository_health import RepositoryHealthChecker


def test_repository_health_checker_passes() -> None:
    checker = RepositoryHealthChecker(project_root=Path(__file__).resolve().parents[1])
    report = checker.run()
    assert report.healthy is True
    assert any(check.name == "documentation" and check.passed for check in report.checks)


def test_cold_boot_audit_reports_missing(monkeypatch) -> None:
    monkeypatch.delenv("TESSRAX_KEY_ID", raising=False)
    monkeypatch.delenv("TESSRAX_GOVERNANCE_TOKEN", raising=False)
    audit = run_cold_boot_audit(required_env=("TESSRAX_KEY_ID",))
    assert audit.environment_ok is False
    assert "TESSRAX_KEY_ID" in audit.missing_env
