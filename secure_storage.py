# -*- coding: utf-8 -*-
"""Lưu JSON bằng AES-GCM, chống chỉnh sửa và chống copy sang máy khác."""
import base64
import hashlib
import json
import os
import tempfile

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from hardware_identity import get_machine_secret

_VERSION = 1
_PEPPER = b"ATG Multi Monitor Control|secure-storage|v1"


def _key() -> bytes:
    return hashlib.sha256(get_machine_secret() + _PEPPER).digest()


def save_encrypted_json(path: str, data: dict, purpose: str):
    nonce = os.urandom(12)
    aad = f"ATG|{purpose}|v{_VERSION}".encode()
    plain = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
    encrypted = AESGCM(_key()).encrypt(nonce, plain, aad)
    envelope = {
        "version": _VERSION,
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "data": base64.b64encode(encrypted).decode("ascii"),
    }
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".atg-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="ascii") as f:
            json.dump(envelope, f, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def load_encrypted_json(path: str, purpose: str):
    with open(path, "r", encoding="ascii") as f:
        envelope = json.load(f)
    if envelope.get("version") != _VERSION:
        raise ValueError("Phiên bản file mã hóa không được hỗ trợ.")
    nonce = base64.b64decode(envelope["nonce"], validate=True)
    encrypted = base64.b64decode(envelope["data"], validate=True)
    aad = f"ATG|{purpose}|v{_VERSION}".encode()
    plain = AESGCM(_key()).decrypt(nonce, encrypted, aad)
    result = json.loads(plain.decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError("Dữ liệu mã hóa không đúng định dạng.")
    return result
