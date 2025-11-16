"""System orchestrator responsible for Tessrax heartbeat scheduling.

The orchestrator enforces Tessrax governance by supervising the crawler queue,
the core runner thread, and ledger/index health checks.  Each heartbeat cycle
records an auditable receipt so the organism's metabolism remains falsifiable
even when individual components restart.
"""
from __future__ import annotations

import json
import os
import signal
import threading
import time
from dataclasses import dataclass

import redis
from rq import Queue
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from tessrax.aion.verify_local import emit_audit_receipt, verify_local
from tessrax.core.core_runner import run_loop as core_run_loop
from tessrax.crawler.agent import run_crawl_job

REDIS_URL = os.getenv("TESSRAX_REDIS_URL", "redis://redis:6379/0")
HEARTBEAT_SECONDS = float(os.getenv("TESSRAX_HEARTBEAT", "10"))
TARGET_URL = os.getenv("TESSRAX_TARGET_URL", "http://example.com")
DB_URL = os.getenv(
    "TESSRAX_DB_URL",
    "postgresql://tessrax:password@postgres:5432/tessrax_state",
)


@dataclass
class HeartbeatStats:
    cycle: int
    ledger_verified: bool
    db_alive: bool
    queued_job_id: str | None


class SystemOrchestrator:
    """Coordinates crawler jobs, core runner thread, and ledger health checks."""

    def __init__(self) -> None:
        self.engine = create_engine(DB_URL, pool_pre_ping=True, future=True)
        self.redis_conn = redis.from_url(REDIS_URL)
        self.queue = Queue("crawler_jobs", connection=self.redis_conn)
        self._core_thread: threading.Thread | None = None
        self._shutdown = threading.Event()
        self._cycle = 0

    def start(self) -> None:
        """Run the orchestrator heartbeat loop until a shutdown signal arrives."""

        self._install_signals()
        self._launch_core()
        print("[ORCH] Tessrax System Orchestrator online.")
        while not self._shutdown.is_set():
            self._cycle += 1
            stats = self._run_cycle(self._cycle)
            receipt = emit_audit_receipt(
                status="heartbeat",
                runtime_info={
                    "cycle": stats.cycle,
                    "ledger_verified": stats.ledger_verified,
                    "db_alive": stats.db_alive,
                    "queued_job_id": stats.queued_job_id,
                },
                integrity_score=0.95 if stats.ledger_verified and stats.db_alive else 0.6,
            )
            print(json.dumps(receipt, sort_keys=True))
            time.sleep(HEARTBEAT_SECONDS)
        print("[ORCH] Shutdown complete.")

    def _install_signals(self) -> None:
        """Install SIGTERM/SIGINT handlers so the heartbeat loop stops cleanly."""

        def _handler(signum, _frame):
            print(f"[ORCH] Signal {signum} received. Exiting...")
            self._shutdown.set()

        signal.signal(signal.SIGTERM, _handler)
        signal.signal(signal.SIGINT, _handler)

    def _launch_core(self) -> None:
        """Launch the core runner thread once per orchestrator lifetime."""

        if self._core_thread and self._core_thread.is_alive():
            return
        self._core_thread = threading.Thread(target=core_run_loop, daemon=True, name="core-runner")
        self._core_thread.start()
        print("[ORCH] Core runner thread started.")

    def _run_cycle(self, cycle: int) -> HeartbeatStats:
        """Perform one heartbeat: verify ledger, DB, and enqueue crawl job."""

        ledger_verified = self._verify_ledger_safely()
        db_alive = self._db_alive()
        job_id = self._schedule_crawl_job() if db_alive else None
        return HeartbeatStats(
            cycle=cycle,
            ledger_verified=ledger_verified,
            db_alive=db_alive,
            queued_job_id=job_id,
        )

    def _verify_ledger_safely(self) -> bool:
        """Guarded ledger verification that logs but never raises to the loop."""

        try:
            verify_local(limit=5)
            return True
        except Exception as exc:
            print(f"[ORCH] Ledger verification failed: {exc}")
            return False

    def _db_alive(self) -> bool:
        """Run a lightweight SELECT 1 probe against Postgres."""

        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError as exc:
            print(f"[ORCH] Database unreachable: {exc}")
            return False

    def _schedule_crawl_job(self) -> str | None:
        """Enqueue a crawler job and return its job id if successful."""

        try:
            job = self.queue.enqueue(run_crawl_job, TARGET_URL, job_timeout="15m")
            print(f"[ORCH] Enqueued crawl job {job.id} for {TARGET_URL}")
            return job.id
        except Exception as exc:
            print(f"[ORCH] Failed to enqueue crawl job: {exc}")
            return None


def main() -> None:
    orchestrator = SystemOrchestrator()
    try:
        orchestrator.start()
    except Exception as exc:
        receipt = emit_audit_receipt(
            status=f"orchestrator-error: {exc}",
            runtime_info={"module": "system_orchestrator"},
            integrity_score=0.1,
        )
        print(json.dumps(receipt, sort_keys=True))
        raise


if __name__ == "__main__":
    main()
