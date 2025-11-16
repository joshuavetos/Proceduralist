"""Lightweight receipt validation models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional


@dataclass(slots=True)
class ReceiptPayloadModel:
    event_type: str
    timestamp: str
    payload: Mapping[str, Any]
    payload_hash: str
    audited_state_hash: str
    auditor: Optional[str]
    key_id: str
    signature: str
    previous_entry_hash: Optional[str]
    entry_hash: str
    merkle_root: str
    epoch_id: Optional[str]
    governance_freshness_tag: Optional[str]

    @classmethod
    def model_validate(cls, data: Mapping[str, Any]) -> "ReceiptPayloadModel":
        required = [
            "event_type",
            "timestamp",
            "payload",
            "payload_hash",
            "audited_state_hash",
            "key_id",
            "signature",
            "entry_hash",
            "merkle_root",
        ]
        for field in required:
            if field not in data:
                raise ValueError(f"Missing receipt field '{field}'")
            if not isinstance(data[field], str) and field != "payload":
                raise TypeError(f"Field '{field}' must be a string")
        signature = data["signature"]
        if len(signature) < 32:
            raise ValueError("signature must be hex-like")
        return cls(
            event_type=str(data["event_type"]),
            timestamp=str(data["timestamp"]),
            payload=data["payload"],
            payload_hash=str(data["payload_hash"]),
            audited_state_hash=str(data["audited_state_hash"]),
            auditor=data.get("auditor"),
            key_id=str(data["key_id"]),
            signature=signature,
            previous_entry_hash=data.get("previous_entry_hash"),
            entry_hash=str(data["entry_hash"]),
            merkle_root=str(data["merkle_root"]),
            epoch_id=data.get("epoch_id"),
            governance_freshness_tag=data.get("governance_freshness_tag"),
        )


__all__ = ["ReceiptPayloadModel"]
