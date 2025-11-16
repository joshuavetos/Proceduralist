"""Re-export Tessrax core memory engine under ``tessrax.memory`` namespace."""

from tessrax.core.memory_engine import Receipt, write_receipt

__all__ = ["Receipt", "write_receipt"]
