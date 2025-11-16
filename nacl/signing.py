"""Deterministic HMAC-based fallback for PyNaCl's signing helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class SignedMessage:
    signature: bytes
    message: bytes


class VerifyKey:
    def __init__(self, key: bytes) -> None:
        if not isinstance(key, (bytes, bytearray)) or not key:
            raise ValueError("VerifyKey requires non-empty bytes")
        self._key = bytes(key)

    def encode(self) -> bytes:
        return self._key

    def verify(self, message: bytes, signature: bytes) -> bytes:
        expected = hmac.new(self._key, message, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, signature):
            raise ValueError("Signature verification failed")
        return message


class SigningKey:
    def __init__(self, key: bytes | None = None) -> None:
        if key is not None and (not isinstance(key, (bytes, bytearray)) or not key):
            raise ValueError("SigningKey requires non-empty bytes")
        self._key = bytes(key) if key is not None else secrets.token_bytes(32)

    @classmethod
    def generate(cls) -> "SigningKey":
        return cls(secrets.token_bytes(32))

    def encode(self) -> bytes:
        return self._key

    @property
    def verify_key(self) -> VerifyKey:
        return VerifyKey(self._key)

    def sign(self, message: bytes) -> SignedMessage:
        signature = hmac.new(self._key, message, hashlib.sha256).digest()
        return SignedMessage(signature=signature, message=message)
