"""On-demand file hashing for duplicate detection.

Three hash modes:
  name_size  – deterministic string built from filename + size (no I/O, instant)
  partial    – SHA-256 of first PARTIAL_BYTES bytes (fast, catches most duplicates)
  full       – SHA-256 of entire file contents (accurate, slow on large files)
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

PARTIAL_BYTES = 4 * 1024 * 1024  # 4 MB
_CHUNK = 65536


def hash_name_size(name: str, size_bytes: int) -> str:
    """Deterministic composite key — no file I/O required."""
    raw = f"{name.lower()}::{size_bytes}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def hash_partial(path: str | Path) -> str | None:
    """SHA-256 of the first PARTIAL_BYTES of the file."""
    try:
        h = hashlib.sha256()
        remaining = PARTIAL_BYTES
        with open(path, "rb") as fh:
            while remaining > 0:
                chunk = fh.read(min(_CHUNK, remaining))
                if not chunk:
                    break
                h.update(chunk)
                remaining -= len(chunk)
        return h.hexdigest()
    except OSError as exc:
        log.debug("hash_partial failed for %s: %s", path, exc)
        return None


def hash_full(path: str | Path) -> str | None:
    """SHA-256 of the entire file."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(_CHUNK)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except OSError as exc:
        log.debug("hash_full failed for %s: %s", path, exc)
        return None


def compute_hash(
    hash_type: str,
    path: str,
    name: str,
    size_bytes: int,
) -> str | None:
    if hash_type == "name_size":
        return hash_name_size(name, size_bytes)
    if hash_type == "partial":
        return hash_partial(path)
    if hash_type == "full":
        return hash_full(path)
    raise ValueError(f"Unknown hash_type: {hash_type!r}")


def run_hash_job(
    rows: list[dict],
    hash_type: str,
    progress_cb: Callable[[int, int], None] | None = None,
    cancel_event=None,
) -> list[tuple[int, str, str]]:
    """Hash a list of file rows, returning (file_id, hash_type, hash_value) triples.

    rows must contain keys: file_id, full_path, name, size_bytes.
    Skips files where hashing fails (returns None) or is cancelled.
    """
    results: list[tuple[int, str, str]] = []
    total = len(rows)
    for idx, row in enumerate(rows):
        if cancel_event is not None and cancel_event.is_set():
            break
        value = compute_hash(hash_type, row["full_path"], row["name"], row["size_bytes"])
        if value is not None:
            results.append((row["file_id"], hash_type, value))
        if progress_cb is not None:
            progress_cb(idx + 1, total)
    return results
