import hashlib
import os
from pathlib import Path


def normalize_path_for_hash(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def path_hash(path: str) -> str:
    normalized = normalize_path_for_hash(path)
    return hashlib.sha256(normalized.encode("utf-8", errors="surrogatepass")).hexdigest()


def path_depth(full_path: str, root_path: str) -> int:
    try:
        rel = Path(full_path).relative_to(Path(root_path))
        return len(rel.parts)
    except ValueError:
        return len(Path(full_path).parts)


def format_bytes(num_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0  # type: ignore[assignment]
    return f"{num_bytes:.1f} PB"
