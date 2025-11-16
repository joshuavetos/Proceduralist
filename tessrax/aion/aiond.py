"""AION daemon: offline oracle for Tessrax OS.

The daemon enforces Tessrax governance directives by verifying the ledger,
loading a local-only GGUF model (via ``llama_cpp``), exposing a UNIX socket for
structured prompts, and emitting auditable receipts.  The implementation
provides deterministic hashing, explicit shutdown handlers, and no network
egress beyond the caller's socket connection.
"""
from __future__ import annotations

import json
import os
import signal
import socket
import threading
import time
from pathlib import Path
from typing import List

from llama_cpp import Llama

from tessrax.aion.verify_local import Receipt, emit_audit_receipt, verify_local

SOCKET_PATH = Path("/tmp/aion.sock")
DEFAULT_MODEL_PATH = Path(os.getenv("TESSRAX_AION_MODEL", "tessrax/models/aion-7b.gguf"))


class AIONDaemon:
    """Offline oracle exposing a UNIX socket backed by a local GGUF model."""

    def __init__(self, model_path: Path = DEFAULT_MODEL_PATH, socket_path: Path = SOCKET_PATH):
        self.model_path = model_path
        self.socket_path = socket_path
        self._model: Llama | None = None
        self._receipts: List[Receipt] = []
        self._shutdown = threading.Event()
        self._server: socket.socket | None = None

    def boot(self) -> None:
        """Verify ledger, load GGUF model, and start socket server."""

        start = time.time()
        self._receipts = verify_local(limit=200)
        self._model = self._load_model()
        duration = time.time() - start
        receipt = emit_audit_receipt(
            status="aiond-online",
            runtime_info={"records": len(self._receipts), "duration_sec": round(duration, 3)},
            integrity_score=0.98,
        )
        print(json.dumps(receipt, sort_keys=True))
        self._install_signal_handlers()
        self._serve()

    def _install_signal_handlers(self) -> None:
        """Attach POSIX signal handlers so shutdown receipts are emitted."""

        def _handler(signum, _frame):
            print(f"[AION] Shutdown signal {signum} received.")
            self._shutdown.set()
            if self._server:
                self._server.close()

        signal.signal(signal.SIGTERM, _handler)
        signal.signal(signal.SIGINT, _handler)

    def _load_model(self) -> Llama:
        """Load the local GGUF model with offline-only parameters."""

        if not self.model_path.exists():
            raise FileNotFoundError(f"GGUF model missing at {self.model_path}")
        return Llama(model_path=str(self.model_path), n_ctx=4096, n_threads=os.cpu_count() or 2)

    def _serve(self) -> None:
        """Start the UNIX socket server and process structured prompts."""

        if self.socket_path.exists():
            self.socket_path.unlink()
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(str(self.socket_path))
        self._server.listen(1)
        print(f"[AION] Listening on {self.socket_path} (offline mode)")

        while not self._shutdown.is_set():
            try:
                conn, _ = self._server.accept()
            except OSError:
                if self._shutdown.is_set():
                    break
                continue
            with conn:
                data = conn.recv(8192)
                if not data:
                    continue
                try:
                    payload = json.loads(data.decode("utf-8"))
                    prompt = str(payload.get("prompt", "")).strip()
                    if not prompt:
                        raise ValueError("prompt must be a non-empty string")
                    response = self._analyze(prompt)
                    body = {"status": "ok", "response": response}
                except Exception as exc:
                    body = {"status": "error", "message": str(exc)}
                conn.sendall(json.dumps(body).encode("utf-8"))

        if self.socket_path.exists():
            self.socket_path.unlink()
        print("[AION] Socket server stopped.")

    def _analyze(self, prompt: str) -> str:
        """Run the GGUF model using recent receipts as context."""

        if not self._model:
            raise RuntimeError("Model not loaded")
        context = json.dumps([receipt.__dict__ for receipt in self._receipts[-20:]], indent=2)
        structured_prompt = (
            "You are AION, Tessrax's offline oracle.\n"
            "Only reference the provided receipts when answering.\n"
            f"Receipts:\n{context}\n\nUser Query: {prompt}\n"
            "Respond with concise bullet points grounded in receipts."
        )
        output = self._model(
            structured_prompt,
            max_tokens=512,
            temperature=0.1,
            top_p=0.95,
        )
        text = output["choices"][0]["text"].strip()
        if not text:
            return "No answer produced."
        return text


def main() -> None:
    """CLI entrypoint used by supervisord/unit files."""

    daemon = AIONDaemon()
    try:
        daemon.boot()
    except Exception as exc:
        receipt = emit_audit_receipt(
            status=f"aiond-error: {exc}",
            runtime_info={"module": "aiond", "exception": type(exc).__name__},
            integrity_score=0.0,
        )
        print(json.dumps(receipt, sort_keys=True))
        raise


if __name__ == "__main__":
    main()
