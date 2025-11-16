"""Fallback Ed25519 implementation used when PyNaCl is unavailable."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

_OPENSSL_BIN = shutil.which("openssl")
if _OPENSSL_BIN is None:  # pragma: no cover - environment guard
    raise RuntimeError("OpenSSL binary is required for Ed25519 fallback support.")

_OID_ED25519 = b"\x06\x03\x2B\x65\x70"


@dataclass(slots=True)
class SignedMessage:
    """Minimal stand-in for ``nacl.signing.SignedMessage``."""

    signature: bytes
    message: bytes

    def __bytes__(self) -> bytes:  # pragma: no cover - compatibility helper
        return self.signature + self.message


class BadSignatureError(Exception):
    """Error raised when signature verification fails."""


class VerifyKey:
    """Ed25519 verify key leveraging OpenSSL for verification."""

    def __init__(self, key: bytes) -> None:
        if len(key) != 32:
            raise ValueError("VerifyKey requires exactly 32 bytes of public key material")
        self._key = key
        self._der = _build_spki_public_key(key)

    def encode(self) -> bytes:
        return self._key

    def verify(self, message: bytes, signature: bytes) -> None:
        _openssl_verify(self._der, message, signature)


class SigningKey:
    """Ed25519 signing key backed by OpenSSL."""

    def __init__(self, seed: bytes) -> None:
        if len(seed) != 32:
            raise ValueError("SigningKey seed must be exactly 32 bytes")
        self._seed = seed
        self._der = _build_pkcs8_private_key(seed)
        public = _derive_public_key(seed)
        self._verify_key = VerifyKey(public)

    @classmethod
    def generate(cls) -> SigningKey:
        return cls(os.urandom(32))

    def encode(self) -> bytes:
        return self._seed

    @property
    def verify_key(self) -> VerifyKey:
        return self._verify_key

    def sign(self, message: bytes) -> SignedMessage:
        signature = _openssl_sign(self._der, message)
        return SignedMessage(signature=signature, message=message)


def _install_module() -> None:
    nacl_mod = types.ModuleType("nacl")
    signing_mod = types.ModuleType("nacl.signing")
    signing_mod.SigningKey = SigningKey
    signing_mod.VerifyKey = VerifyKey
    signing_mod.SignedMessage = SignedMessage
    signing_mod.BadSignatureError = BadSignatureError
    exceptions_mod = types.ModuleType("nacl.exceptions")
    exceptions_mod.BadSignatureError = BadSignatureError
    nacl_mod.signing = signing_mod
    nacl_mod.exceptions = exceptions_mod
    sys.modules.setdefault("nacl", nacl_mod)
    sys.modules["nacl.signing"] = signing_mod
    sys.modules["nacl.exceptions"] = exceptions_mod


def install() -> None:
    """Expose fallback implementation under ``nacl.signing``."""

    if "nacl.signing" in sys.modules:
        return
    _install_module()


def _encode_length(length: int) -> bytes:
    if length < 0x80:
        return bytes([length])
    data = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(data)]) + data


def _der_sequence(content: bytes) -> bytes:
    return b"\x30" + _encode_length(len(content)) + content


def _der_octet_string(data: bytes) -> bytes:
    return b"\x04" + _encode_length(len(data)) + data


def _der_bit_string(data: bytes) -> bytes:
    # BIT STRING stores an extra byte indicating number of unused bits.
    return b"\x03" + _encode_length(len(data) + 1) + b"\x00" + data


def _build_pkcs8_private_key(seed: bytes) -> bytes:
    version = b"\x02\x01\x00"
    algorithm = _der_sequence(_OID_ED25519)
    private_key = _der_octet_string(_der_octet_string(seed))
    return _der_sequence(version + algorithm + private_key)


def _build_spki_public_key(public: bytes) -> bytes:
    algorithm = _der_sequence(_OID_ED25519)
    subject = _der_bit_string(public)
    return _der_sequence(algorithm + subject)


def _decode_length(data: bytes, offset: int) -> Tuple[int, int]:
    first = data[offset]
    if first < 0x80:
        return first, 1
    num_bytes = first & 0x7F
    value = int.from_bytes(data[offset + 1 : offset + 1 + num_bytes], "big")
    return value, 1 + num_bytes


def _extract_public_from_spki(der: bytes) -> bytes:
    if not der or der[0] != 0x30:
        raise RuntimeError("Malformed SPKI: missing sequence header")
    total_len, consumed = _decode_length(der, 1)
    idx = 1 + consumed
    if idx >= len(der) or der[idx] != 0x30:
        raise RuntimeError("Malformed SPKI: missing algorithm identifier")
    alg_len, alg_consumed = _decode_length(der, idx + 1)
    idx += 1 + alg_consumed + alg_len
    if idx >= len(der) or der[idx] != 0x03:
        raise RuntimeError("Malformed SPKI: missing BIT STRING")
    length, consumed = _decode_length(der, idx + 1)
    bit_string = der[idx + 1 + consumed : idx + 1 + consumed + length]
    if not bit_string or bit_string[0] != 0x00:
        raise RuntimeError("Malformed SPKI: invalid BIT STRING padding")
    public = bit_string[1:]
    if len(public) != 32:
        raise RuntimeError("Unexpected public key length")
    return public


def _write_temp(data: bytes) -> str:
    handle = tempfile.NamedTemporaryFile(delete=False)
    try:
        handle.write(data)
        return handle.name
    finally:
        handle.close()


def _run_command(args: list[str]) -> None:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"OpenSSL failure: {' '.join(args)} -> {result.stderr.strip()}")


def _derive_public_key(seed: bytes) -> bytes:
    priv_path = _write_temp(_build_pkcs8_private_key(seed))
    pub_path = tempfile.NamedTemporaryFile(delete=False).name
    try:
        _run_command(
            [_OPENSSL_BIN, "pkey", "-in", priv_path, "-inform", "DER", "-pubout", "-outform", "DER", "-out", pub_path]
        )
        pub_der = Path(pub_path).read_bytes()
        return _extract_public_from_spki(pub_der)
    finally:
        for path in (priv_path, pub_path):
            try:
                os.unlink(path)
            except FileNotFoundError:  # pragma: no cover - best effort cleanup
                pass


def _openssl_sign(priv_der: bytes, message: bytes) -> bytes:
    priv_path = _write_temp(priv_der)
    msg_path = _write_temp(message)
    sig_path = tempfile.NamedTemporaryFile(delete=False).name
    try:
        _run_command(
            [
                _OPENSSL_BIN,
                "pkeyutl",
                "-sign",
                "-inkey",
                priv_path,
                "-keyform",
                "DER",
                "-rawin",
                "-in",
                msg_path,
                "-out",
                sig_path,
            ]
        )
        signature = Path(sig_path).read_bytes()
        if len(signature) != 64:
            raise RuntimeError("OpenSSL produced invalid signature length")
        return signature
    finally:
        for path in (priv_path, msg_path, sig_path):
            try:
                os.unlink(path)
            except FileNotFoundError:  # pragma: no cover
                pass


def _openssl_verify(pub_der: bytes, message: bytes, signature: bytes) -> None:
    if len(signature) != 64:
        raise ValueError("Signature must be 64 bytes")
    pub_path = _write_temp(pub_der)
    msg_path = _write_temp(message)
    sig_path = _write_temp(signature)
    try:
        _run_command(
            [
                _OPENSSL_BIN,
                "pkeyutl",
                "-verify",
                "-pubin",
                "-inkey",
                pub_path,
                "-keyform",
                "DER",
                "-rawin",
                "-in",
                msg_path,
                "-sigfile",
                sig_path,
            ]
        )
    except RuntimeError as exc:
        raise BadSignatureError(str(exc)) from exc
    finally:
        for path in (pub_path, msg_path, sig_path):
            try:
                os.unlink(path)
            except FileNotFoundError:  # pragma: no cover
                pass
