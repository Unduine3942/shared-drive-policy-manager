"""Password hashing and verification — stdlib only (hashlib + secrets).

SHA-256 + 128-bit random salt is used because bcrypt/Argon2 are not available
in the ArcGIS Pro 3.3.1 arcgispro-py3 environment.  This is acceptable for a
local single-user desktop application on an airgapped system per CLAUDE.md.
"""
from __future__ import annotations

import hashlib
import secrets


def generate_salt() -> str:
    return secrets.token_hex(16)


def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    return hash_password(password, salt) == stored_hash
