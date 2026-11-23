"""Hidden file patterns — managed by secret_admin, distributed with the codebase.

Entries support fnmatch glob syntax matched case-insensitively against the
full path or the filename alone.  Examples:
  \\\\server\\share\\private\\*     hide everything under a folder
  confidential_*.docx               hide by filename glob
  \\\\server\\share\\exact\\file.txt  hide one specific file
"""
from __future__ import annotations

import ast
import fnmatch
import re
from pathlib import Path

# ── Persisted list — edited via Secret Admin › Hidden Files ─────────────────
HIDDEN_PATTERNS: list[str] = []

# ── Runtime API ──────────────────────────────────────────────────────────────

_SELF = Path(__file__)
_LIST_RE = re.compile(
    r"(HIDDEN_PATTERNS\s*:\s*list\[str\]\s*=\s*)(\[.*?\])",
    re.DOTALL,
)


def get_patterns() -> list[str]:
    """Parse HIDDEN_PATTERNS directly from this source file (always fresh)."""
    text = _SELF.read_text(encoding="utf-8")
    m = _LIST_RE.search(text)
    if not m:
        return []
    try:
        return ast.literal_eval(m.group(2))
    except (ValueError, SyntaxError):
        return []


def save_patterns(patterns: list[str]) -> None:
    """Rewrite HIDDEN_PATTERNS in this source file with the given list."""
    text = _SELF.read_text(encoding="utf-8")
    if not patterns:
        new_list = "[]"
    else:
        inner = ",\n    ".join(repr(p) for p in sorted(set(patterns)))
        new_list = f"[\n    {inner},\n]"
    new_text = _LIST_RE.sub(lambda m: m.group(1) + new_list, text)
    _SELF.write_text(new_text, encoding="utf-8")


def matches_any(path: str, patterns: list[str]) -> bool:
    """Return True if *path* matches any hidden pattern."""
    if not patterns:
        return False
    lower_path = path.replace("\\", "/").lower()
    lower_name = Path(path).name.lower()
    for pat in patterns:
        p = pat.replace("\\", "/").lower()
        if fnmatch.fnmatch(lower_path, p) or fnmatch.fnmatch(lower_name, p):
            return True
    return False
