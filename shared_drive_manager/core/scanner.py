"""Directory scanner — pure worker-level scan logic, no DB writes."""
from __future__ import annotations

import fnmatch
import json
import logging
import os
import threading
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone

from shared_drive_manager.core.doc_properties import read_doc_properties
from shared_drive_manager.core.hidden_files import get_patterns, matches_any
from shared_drive_manager.core.models import FileRecord, Policy
from shared_drive_manager.core.owner_resolver import resolve_owner
from shared_drive_manager.core.path_utils import path_depth as calc_depth, path_hash
from shared_drive_manager.core.policy_engine import PolicyEngine

log = logging.getLogger(__name__)

_engine = PolicyEngine()


@dataclass
class ScanResult:
    """Result of scanning one directory on a worker thread."""

    dir_hash: str
    root_id: int
    file_records: list[FileRecord] = field(default_factory=list)
    touch_hashes: list[str] = field(default_factory=list)
    subdir_dicts: list[dict] = field(default_factory=list)
    error_dicts: list[dict] = field(default_factory=list)
    dir_error: str | None = None
    dir_mtime: str | None = None
    skipped: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _should_exclude(name: str, exclude_globs: list[str]) -> bool:
    name_lower = name.lower()
    return any(fnmatch.fnmatchcase(name_lower, pat.lower()) for pat in exclude_globs)


def _find_section(path: str, sections: list[dict]) -> str | None:
    path_lower = path.lower()
    best: tuple[str, int] | None = None
    for s in sections:
        prefix = s["path_prefix"].lower()
        if path_lower.startswith(prefix):
            if best is None or len(prefix) > best[1]:
                best = (s["section_name"], len(prefix))
    return best[0] if best else None


# ---------------------------------------------------------------------------
# Public scan function (called from ThreadPoolExecutor workers)
# ---------------------------------------------------------------------------

def scan_directory(
    dir_path: str,
    dir_hash: str,
    root_id: int,
    depth: int,
    run_id: int,
    root: dict,
    policies: list[Policy],
    sections: list[dict],
    collect_owner: bool,
    collect_doc_props: bool,
    cancel_event: threading.Event,
    prev_dir_mtime: str | None = None,
    existing_stats: dict[str, tuple[str | None, int]] | None = None,
) -> ScanResult:
    """Scan one directory; return file records, child dirs, and errors.

    Does NOT touch the database — the controller thread writes results.
    """
    result = ScanResult(dir_hash=dir_hash, root_id=root_id)

    try:
        result.dir_mtime = _ts(os.stat(dir_path).st_mtime)
    except Exception:
        pass

    if prev_dir_mtime is not None and result.dir_mtime == prev_dir_mtime:
        result.skipped = True
        return result

    _hidden = get_patterns()   # read once per directory; list is small

    max_depth: int | None = root.get("max_depth")
    follow_symlinks: bool = bool(root.get("follow_symlinks", False))
    exclude_globs: list[str] = json.loads(root.get("exclude_globs_json") or "[]")
    root_path: str = root["root_path"]

    try:
        entries = list(os.scandir(dir_path))
    except Exception as exc:
        result.dir_error = str(exc)
        result.error_dicts.append({
            "run_id": run_id,
            "root_id": root_id,
            "path": dir_path,
            "operation": "scandir",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "traceback_text": traceback.format_exc(),
        })
        return result

    for entry in entries:
        if cancel_event.is_set():
            break

        try:
            if _should_exclude(entry.name, exclude_globs):
                continue

            is_symlink = entry.is_symlink()

            if entry.is_dir(follow_symlinks=follow_symlinks):
                if is_symlink and not follow_symlinks:
                    continue
                if max_depth is not None and (depth + 1) > max_depth:
                    continue
                child_hash = path_hash(entry.path)
                result.subdir_dicts.append({
                    "run_id": run_id,
                    "dir_hash": child_hash,
                    "root_id": root_id,
                    "dir_path": entry.path,
                    "parent_hash": dir_hash,
                    "depth": depth + 1,
                })
                continue

            if not entry.is_file(follow_symlinks=follow_symlinks):
                continue

            if matches_any(entry.path, _hidden):
                continue

            st = entry.stat(follow_symlinks=False)
            name = entry.name
            ext = os.path.splitext(name)[1].lower()
            full_path = entry.path
            size_bytes = st.st_size
            ph = path_hash(full_path)

            if existing_stats is not None:
                prev = existing_stats.get(ph)
                if prev is not None and prev[0] == _ts(st.st_mtime) and prev[1] == st.st_size:
                    result.touch_hashes.append(ph)
                    continue

            section = _find_section(full_path, sections)
            pdepth = calc_depth(full_path, root_path)
            file_attrs = getattr(st, "st_file_attributes", None)

            owner_sid, owner_name = None, None
            if collect_owner:
                owner_sid, owner_name = resolve_owner(full_path)

            doc_creator, doc_modifier = None, None
            if collect_doc_props:
                dp = read_doc_properties(full_path, ext)
                doc_creator = dp.creator
                doc_modifier = dp.modifier

            result.file_records.append(FileRecord(
                root_id=root_id,
                path_hash=ph,
                full_path=full_path,
                parent_path=dir_path,
                name=name,
                extension=ext,
                size_bytes=size_bytes,
                path_depth=pdepth,
                path_length=len(full_path),
                is_empty=(size_bytes == 0),
                section_name=section,
                ctime_utc=_ts(st.st_ctime),
                mtime_utc=_ts(st.st_mtime),
                atime_utc=_ts(st.st_atime),
                owner_sid=owner_sid,
                owner_name=owner_name,
                doc_creator=doc_creator,
                doc_modifier=doc_modifier,
                file_attrs=file_attrs,
            ))

        except Exception as exc:
            result.error_dicts.append({
                "run_id": run_id,
                "root_id": root_id,
                "path": getattr(entry, "path", dir_path),
                "operation": "process_entry",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "traceback_text": traceback.format_exc(),
            })

    return result
