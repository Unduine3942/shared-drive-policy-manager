"""Scan controller — orchestrates workers, writes results, emits progress events."""
from __future__ import annotations

import concurrent.futures
import logging
import queue
import sqlite3
import threading
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from shared_drive_manager.core.models import FileRecord, Policy, ProgressEvent
from shared_drive_manager.core.path_utils import path_hash
from shared_drive_manager.core.policy_engine import PolicyEngine
from shared_drive_manager.core.scanner import ScanResult, scan_directory
from shared_drive_manager.db.connection import open_connection
from shared_drive_manager.db.repositories import (
    FileInventoryRepo,
    ScanDirectoryRepo,
    ScanErrorRepo,
    ScanRootRepo,
    ScanRunRepo,
    SectionMapRepo,
    ViolationRepo,
)

if TYPE_CHECKING:
    from shared_drive_manager.app import Application

log = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ScanController:
    """Runs scans on a background thread; caller polls drain_progress()."""

    def __init__(self, app: "Application") -> None:
        self.app = app
        self._cancel_event = threading.Event()
        self._progress_queue: queue.Queue[ProgressEvent] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._engine = PolicyEngine()

    # ------------------------------------------------------------------
    # Public interface — safe to call from the Tkinter main thread
    # ------------------------------------------------------------------

    def start(self, root_ids: list[int], run_type: str = "full") -> None:
        if self.is_running():
            return
        self._cancel_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(root_ids, run_type),
            daemon=True,
            name="scan-controller",
        )
        self._thread.start()

    def resume(self, existing_run_id: int) -> None:
        """Resume a previously interrupted run using its existing run_id."""
        if self.is_running():
            return
        self._cancel_event.clear()
        self._thread = threading.Thread(
            target=self._run_resume,
            args=(existing_run_id,),
            daemon=True,
            name="scan-controller",
        )
        self._thread.start()

    def cancel(self) -> None:
        self._cancel_event.set()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def drain_progress(self) -> list[ProgressEvent]:
        events: list[ProgressEvent] = []
        while True:
            try:
                events.append(self._progress_queue.get_nowait())
            except queue.Empty:
                break
        return events

    # ------------------------------------------------------------------
    # Background thread entry points
    # ------------------------------------------------------------------

    def _run(self, root_ids: list[int], run_type: str) -> None:
        conn: sqlite3.Connection | None = None
        run_id: int | None = None
        try:
            conn = open_connection(self.app.db_path)
            run_id = self._do_scan(conn, root_ids, run_type)
        except Exception as exc:
            log.error("Scan controller unhandled exception: %s", exc, exc_info=True)
            if run_id is not None and conn is not None:
                try:
                    ScanRunRepo().finish(conn, run_id, "failed", str(exc))
                except Exception:
                    pass
            self._progress_queue.put(
                ProgressEvent(finished=True, status=f"Scan failed: {exc}")
            )
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def _run_resume(self, existing_run_id: int) -> None:
        conn: sqlite3.Connection | None = None
        try:
            conn = open_connection(self.app.db_path)
            self._do_resume(conn, existing_run_id)
        except Exception as exc:
            log.error("Resume scan unhandled exception: %s", exc, exc_info=True)
            if conn is not None:
                try:
                    ScanRunRepo().finish(conn, existing_run_id, "failed", str(exc))
                except Exception:
                    pass
            self._progress_queue.put(
                ProgressEvent(finished=True, status=f"Resume failed: {exc}")
            )
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Core scan logic — full / incremental
    # ------------------------------------------------------------------

    def _do_scan(
        self, conn: sqlite3.Connection, root_ids: list[int], run_type: str
    ) -> int:
        run_repo = ScanRunRepo()
        root_repo = ScanRootRepo()
        dir_repo = ScanDirectoryRepo()
        file_repo = FileInventoryRepo()
        violation_repo = ViolationRepo()
        error_repo = ScanErrorRepo()
        section_repo = SectionMapRepo()

        settings = self.app.settings
        max_workers: int = max(1, min(16, int(settings.get("max_workers", 4))))
        batch_size: int = max(100, int(settings.get("batch_size", 1000)))
        collect_owner: bool = bool(settings.get("collect_owner", True))
        collect_doc_props: bool = bool(settings.get("collect_doc_props", True))
        max_error_threshold: int = int(settings.get("max_error_threshold", 0))

        run_id = run_repo.create(conn, run_type)

        roots = [root_repo.get(conn, rid) for rid in root_ids]
        roots = [r for r in roots if r is not None]
        if not roots:
            run_repo.finish(conn, run_id, "failed", "No valid roots selected")
            self._progress_queue.put(
                ProgressEvent(finished=True, status="No valid roots selected.")
            )
            return run_id

        run_repo.set_running(conn, run_id, len(roots))

        seed_entries = [
            {
                "run_id": run_id,
                "dir_hash": path_hash(r["root_path"]),
                "root_id": r["root_id"],
                "dir_path": r["root_path"],
                "parent_hash": None,
                "depth": 0,
            }
            for r in roots
        ]
        dir_repo.seed(conn, seed_entries)

        sections = section_repo.list_active(conn)
        policies = self._engine.load_active_policies(conn)
        roots_by_id = {r["root_id"]: r for r in roots}

        self._progress_queue.put(
            ProgressEvent(
                status=f"Starting {run_type} scan — {len(roots)} root(s), "
                f"{len(policies)} active polic{'y' if len(policies)==1 else 'ies'}..."
            )
        )

        is_incremental = (run_type != "full")
        (total_files, total_bytes, total_violations,
         total_errors, total_dirs) = self._scan_loop(
            conn, run_id, roots_by_id, sections, policies,
            max_workers, batch_size, collect_owner, collect_doc_props,
            max_error_threshold, 0, 0, 0, 0, 0, is_incremental,
        )

        if run_type == "full" and not self._cancel_event.is_set():
            for root in roots:
                file_repo.mark_deleted(conn, root["root_id"], run_id)
            conn.commit()

        run_repo.increment_counters(
            conn, run_id,
            dirs=total_dirs, files=total_files, bytez=total_bytes,
            violations=total_violations, errors=total_errors,
        )

        if self._cancel_event.is_set():
            run_repo.finish(conn, run_id, "canceled")
            self._progress_queue.put(ProgressEvent(finished=True, status="Scan canceled."))
        else:
            run_repo.finish(conn, run_id, "completed")
            self._progress_queue.put(
                ProgressEvent(
                    finished=True,
                    status=(
                        f"Scan complete — {total_files:,} files, "
                        f"{total_violations:,} violations, "
                        f"{total_errors:,} errors."
                    ),
                )
            )

        return run_id

    # ------------------------------------------------------------------
    # Core scan logic — resume
    # ------------------------------------------------------------------

    def _do_resume(self, conn: sqlite3.Connection, run_id: int) -> None:
        run_repo = ScanRunRepo()
        root_repo = ScanRootRepo()
        dir_repo = ScanDirectoryRepo()
        file_repo = FileInventoryRepo()
        section_repo = SectionMapRepo()

        settings = self.app.settings
        max_workers: int = max(1, min(16, int(settings.get("max_workers", 4))))
        batch_size: int = max(100, int(settings.get("batch_size", 1000)))
        collect_owner: bool = bool(settings.get("collect_owner", True))
        collect_doc_props: bool = bool(settings.get("collect_doc_props", True))
        max_error_threshold: int = int(settings.get("max_error_threshold", 0))

        # Reset any dirs that were left in_progress when the run was interrupted
        dir_repo.reset_stale_in_progress(conn, run_id)

        # Discover which roots this run covers from the directory queue
        root_id_rows = conn.execute(
            "SELECT DISTINCT root_id FROM scan_directories WHERE run_id = ?",
            (run_id,),
        ).fetchall()
        root_ids = [r["root_id"] for r in root_id_rows]

        roots = [root_repo.get(conn, rid) for rid in root_ids]
        roots = [r for r in roots if r is not None]

        if not roots:
            run_repo.finish(conn, run_id, "failed", "No roots found for resumed run")
            self._progress_queue.put(
                ProgressEvent(finished=True, status="Resume failed: no roots found.")
            )
            return

        # Mark this run as running again
        run_repo.set_running(conn, run_id, len(roots))

        sections = section_repo.list_active(conn)
        policies = self._engine.load_active_policies(conn)
        roots_by_id = {r["root_id"]: r for r in roots}

        pending_count = conn.execute(
            "SELECT COUNT(*) FROM scan_directories WHERE run_id = ? AND status = 'pending'",
            (run_id,),
        ).fetchone()[0]

        self._progress_queue.put(
            ProgressEvent(
                status=f"Resuming run #{run_id} — {pending_count:,} director"
                f"{'y' if pending_count == 1 else 'ies'} remaining..."
            )
        )

        orig_run = conn.execute(
            "SELECT run_type FROM scan_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        is_incremental = orig_run["run_type"] != "full" if orig_run else True
        (total_files, total_bytes, total_violations,
         total_errors, total_dirs) = self._scan_loop(
            conn, run_id, roots_by_id, sections, policies,
            max_workers, batch_size, collect_owner, collect_doc_props,
            max_error_threshold, 0, 0, 0, 0, 0, is_incremental,
        )

        run_repo.increment_counters(
            conn, run_id,
            dirs=total_dirs, files=total_files, bytez=total_bytes,
            violations=total_violations, errors=total_errors,
        )

        if self._cancel_event.is_set():
            run_repo.finish(conn, run_id, "canceled")
            self._progress_queue.put(ProgressEvent(finished=True, status="Scan canceled."))
        else:
            run_repo.finish(conn, run_id, "completed")
            self._progress_queue.put(
                ProgressEvent(
                    finished=True,
                    status=(
                        f"Resume complete — {total_files:,} files, "
                        f"{total_violations:,} violations, "
                        f"{total_errors:,} errors."
                    ),
                )
            )

    # ------------------------------------------------------------------
    # Shared scan loop used by both _do_scan and _do_resume
    # ------------------------------------------------------------------

    def _scan_loop(
        self,
        conn: sqlite3.Connection,
        run_id: int,
        roots_by_id: dict,
        sections: list,
        policies: list,
        max_workers: int,
        batch_size: int,
        collect_owner: bool,
        collect_doc_props: bool,
        max_error_threshold: int,
        total_files: int,
        total_bytes: int,
        total_violations: int,
        total_errors: int,
        total_dirs: int,
        is_incremental: bool = False,
    ) -> tuple[int, int, int, int, int]:
        dir_repo = ScanDirectoryRepo()
        file_repo = FileInventoryRepo()

        result_q: queue.Queue = queue.Queue()
        _DONE = object()
        # [files, bytes, violations, errors, dirs] — mutated by writer thread only
        totals = [total_files, total_bytes, total_violations, total_errors, total_dirs]
        _in_flight = [0]
        _in_flight_lock = threading.Lock()
        _pending_writes = [0]
        _pw_lock = threading.Lock()

        def _writer() -> None:
            w_dir = ScanDirectoryRepo()
            w_files = FileInventoryRepo()
            w_violations = ViolationRepo()
            w_errors = ScanErrorRepo()
            wconn = open_connection(self.app.db_path)
            try:
                while True:
                    try:
                        item = result_q.get(timeout=1.0)
                    except queue.Empty:
                        continue
                    if item is _DONE:
                        break
                    result, d, existing_stats = item
                    try:
                        if result.skipped:
                            if existing_stats:
                                w_files.touch_by_hashes(
                                    wconn, d["root_id"], list(existing_stats.keys()), run_id
                                )
                            w_dir.mark_scanned(wconn, run_id, result.dir_hash, result.dir_mtime)
                            wconn.commit()
                            totals[4] += 1
                            self._progress_queue.put(
                                ProgressEvent(dirs_delta=1, current_path=d["dir_path"])
                            )
                            continue

                        if result.subdir_dicts:
                            w_dir.seed(wconn, result.subdir_dicts)

                        for err in result.error_dicts:
                            w_errors.insert(wconn, **err)
                        dir_error_count = (
                            len(result.error_dicts) + (1 if result.dir_error else 0)
                        )

                        nf = nb = nv = 0

                        if result.touch_hashes:
                            w_files.touch_by_hashes(
                                wconn, result.root_id, result.touch_hashes, run_id
                            )

                        if result.file_records:
                            for i in range(0, len(result.file_records), batch_size):
                                chunk = result.file_records[i : i + batch_size]
                                w_files.upsert_batch(
                                    wconn, [_record_to_dict(r) for r in chunk], run_id
                                )
                                enriched = _fetch_file_ids(
                                    wconn, result.root_id, [r.path_hash for r in chunk]
                                )
                                for rec in enriched:
                                    viols = self._engine.evaluate(rec, policies, run_id)
                                    if viols:
                                        w_violations.insert_batch(
                                            wconn,
                                            [
                                                {
                                                    "run_id": v.run_id,
                                                    "file_id": v.file_id,
                                                    "policy_id": v.policy_id,
                                                    "severity": v.severity,
                                                    "reason": v.reason,
                                                }
                                                for v in viols
                                            ],
                                        )
                                        nv += len(viols)
                                nf += len(chunk)
                                nb += sum(r.size_bytes for r in chunk)

                        if result.dir_error:
                            w_dir.mark_error(wconn, run_id, result.dir_hash, result.dir_error)
                        else:
                            w_dir.mark_scanned(
                                wconn, run_id, result.dir_hash, result.dir_mtime
                            )
                        wconn.commit()

                        totals[0] += nf
                        totals[1] += nb
                        totals[2] += nv
                        totals[3] += dir_error_count
                        totals[4] += 1
                        self._progress_queue.put(
                            ProgressEvent(
                                files_delta=nf,
                                bytes_delta=nb,
                                violations_delta=nv,
                                errors_delta=dir_error_count,
                                dirs_delta=1,
                                current_path=d["dir_path"],
                            )
                        )

                    except Exception as exc:
                        log.error(
                            "Writer error for %s: %s", d.get("dir_path"), exc, exc_info=True
                        )
                    finally:
                        with _pw_lock:
                            _pending_writes[0] -= 1
            finally:
                try:
                    wconn.close()
                except Exception:
                    pass

        writer_thread = threading.Thread(target=_writer, name="scan-writer", daemon=True)
        writer_thread.start()

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                while not self._cancel_event.is_set():
                    if max_error_threshold > 0 and totals[3] >= max_error_threshold:
                        self._progress_queue.put(
                            ProgressEvent(
                                status=f"Stopping: error threshold reached ({totals[3]} errors)."
                            )
                        )
                        self._cancel_event.set()
                        break

                    pending = dir_repo.claim_pending(conn, run_id, limit=max_workers * 8)
                    if not pending:
                        with _in_flight_lock:
                            flying = _in_flight[0] > 0
                        with _pw_lock:
                            writing = _pending_writes[0] > 0
                        if flying or writing:
                            time.sleep(0.05)
                            continue
                        break

                    for d in pending:
                        root = roots_by_id.get(d["root_id"])
                        if root is None:
                            continue

                        prev_dir_mtime: str | None = None
                        existing_stats: dict | None = None
                        if is_incremental:
                            prev_dir_mtime = dir_repo.get_prev_dir_mtime(
                                conn, d["dir_hash"], run_id
                            )
                            existing_stats = file_repo.get_stats_for_dir(
                                conn, d["root_id"], d["dir_path"]
                            )

                        with _in_flight_lock:
                            _in_flight[0] += 1

                        fut = executor.submit(
                            scan_directory,
                            d["dir_path"],
                            d["dir_hash"],
                            d["root_id"],
                            d["depth"],
                            run_id,
                            root,
                            policies,
                            sections,
                            collect_owner,
                            collect_doc_props,
                            self._cancel_event,
                            prev_dir_mtime,
                            existing_stats,
                        )

                        def _cb(
                            f: concurrent.futures.Future,
                            _d: dict = d,
                            _stats: dict | None = existing_stats,
                        ) -> None:
                            try:
                                r = f.result()
                            except Exception as exc:
                                log.error(
                                    "Worker exception for %s: %s",
                                    _d["dir_path"], exc, exc_info=True,
                                )
                                r = ScanResult(
                                    dir_hash=_d["dir_hash"], root_id=_d["root_id"]
                                )
                                r.dir_error = str(exc)
                                r.error_dicts.append({
                                    "run_id": run_id,
                                    "root_id": _d["root_id"],
                                    "path": _d["dir_path"],
                                    "operation": "scan_directory",
                                    "error_type": type(exc).__name__,
                                    "error_message": str(exc),
                                    "traceback_text": None,
                                })
                            with _pw_lock:
                                _pending_writes[0] += 1
                            result_q.put((r, _d, _stats))
                            with _in_flight_lock:
                                _in_flight[0] -= 1

                        fut.add_done_callback(_cb)
        finally:
            result_q.put(_DONE)
            writer_thread.join()

        return totals[0], totals[1], totals[2], totals[3], totals[4]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _record_to_dict(r: FileRecord) -> dict:
    return {
        "root_id": r.root_id,
        "path_hash": r.path_hash,
        "full_path": r.full_path,
        "parent_path": r.parent_path,
        "name": r.name,
        "extension": r.extension,
        "section_name": r.section_name,
        "size_bytes": r.size_bytes,
        "ctime_utc": r.ctime_utc,
        "mtime_utc": r.mtime_utc,
        "atime_utc": r.atime_utc,
        "owner_sid": r.owner_sid,
        "owner_name": r.owner_name,
        "doc_creator": r.doc_creator,
        "doc_modifier": r.doc_modifier,
        "file_attrs": r.file_attrs,
        "path_depth": r.path_depth,
        "path_length": r.path_length,
        "is_empty": int(r.is_empty),
        "last_error": r.last_error,
    }


def _fetch_file_ids(
    conn: sqlite3.Connection, root_id: int, path_hashes: list[str]
) -> list[FileRecord]:
    """Query file_inventory to resolve file_ids for policy evaluation."""
    if not path_hashes:
        return []
    placeholders = ",".join("?" * len(path_hashes))
    rows = conn.execute(
        f"""
        SELECT file_id, root_id, path_hash, full_path, parent_path, name,
               extension, section_name, size_bytes, ctime_utc, mtime_utc,
               atime_utc, owner_sid, owner_name, doc_creator, doc_modifier,
               file_attrs, path_depth, path_length, is_empty
          FROM file_inventory
         WHERE root_id = ? AND path_hash IN ({placeholders})
        """,
        [root_id] + path_hashes,
    ).fetchall()
    return [
        FileRecord(
            file_id=row["file_id"],
            root_id=row["root_id"],
            path_hash=row["path_hash"],
            full_path=row["full_path"],
            parent_path=row["parent_path"],
            name=row["name"],
            extension=row["extension"],
            section_name=row["section_name"],
            size_bytes=row["size_bytes"],
            ctime_utc=row["ctime_utc"],
            mtime_utc=row["mtime_utc"],
            atime_utc=row["atime_utc"],
            owner_sid=row["owner_sid"],
            owner_name=row["owner_name"],
            doc_creator=row["doc_creator"],
            doc_modifier=row["doc_modifier"],
            file_attrs=row["file_attrs"],
            path_depth=row["path_depth"],
            path_length=row["path_length"],
            is_empty=bool(row["is_empty"]),
        )
        for row in rows
    ]
