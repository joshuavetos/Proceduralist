"""Lightweight local fallback for :mod:`nacl.signing`."""

from .signing import SignedMessage, SigningKey, VerifyKey

__all__ = ["SignedMessage", "SigningKey", "VerifyKey"]
