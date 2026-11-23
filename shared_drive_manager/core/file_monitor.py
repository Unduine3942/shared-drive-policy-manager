"""File-system monitoring engine.

Primary backend: win32file.ReadDirectoryChangesW (zero-lag, Windows native).
Fallback backend: os.scandir snapshot polling (5-second interval).

Each monitored subject runs on its own daemon thread. All events are pushed
to a shared queue.Queue that the UI drains every 400 ms via Tkinter after().
"""
from __future__ import annotations

import logging
import os
import queue
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from shared_drive_manager.core.models import MonitorEvent

log = logging.getLogger(__name__)

_MAX_SUBJECTS = 10
_POLL_INTERVAL = 5.0       # seconds between snapshot diffs (fallback mode)
_WIN32_TIMEOUT_MS = 500    # ReadDirectoryChangesW blocking timeout
_WIN32_BUF = 65536         # 64 KB — safe for network shares

try:
    import win32file  # type: ignore[import]
    import win32con   # type: ignore[import]
    _WIN32 = True
except ImportError:
    win32file = None  # type: ignore[assignment]
    win32con = None   # type: ignore[assignment]
    _WIN32 = False

# FILE_ACTION_* constants → event_type string
_ACTION_MAP: dict[int, str] = {
    1: "created",   # FILE_ACTION_ADDED
    2: "deleted",   # FILE_ACTION_REMOVED
    3: "modified",  # FILE_ACTION_MODIFIED
    4: "renamed",   # FILE_ACTION_RENAMED_OLD_NAME
    5: "renamed",   # FILE_ACTION_RENAMED_NEW_NAME
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_win32_available() -> bool:
    return _WIN32


# ---------------------------------------------------------------------------
# Subject watcher thread
# ---------------------------------------------------------------------------

class _SubjectWatcher(threading.Thread):
    def __init__(
        self,
        subject_id: int,
        label: str,
        watch_path: str,
        watch_type: str,       # 'file' | 'directory'
        recursive: bool,
        out_queue: "queue.Queue[MonitorEvent]",
        stop_event: threading.Event,
    ) -> None:
        super().__init__(
            name=f"monitor-{subject_id}",
            daemon=True,
        )
        self._subject_id = subject_id
        self._label = label
        self._watch_path = watch_path
        self._watch_type = watch_type
        self._recursive = recursive
        self._out = out_queue
        self._stop = stop_event

        # When watching a single file, monitor its parent dir and filter.
        if watch_type == "file":
            self._watch_dir = str(Path(watch_path).parent)
            self._filter_name: str | None = Path(watch_path).name.lower()
        else:
            self._watch_dir = watch_path
            self._filter_name = None

    def _emit(self, event_type: str, path: str, old_path: str | None = None) -> None:
        self._out.put(MonitorEvent(
            subject_id=self._subject_id,
            subject_label=self._label,
            event_type=event_type,
            path=path,
            old_path=old_path,
            timestamp_utc=_utcnow(),
        ))

    def run(self) -> None:
        log.debug("Monitor watcher starting: %s (%s)", self._label, self._watch_dir)
        try:
            if _WIN32:
                self._run_win32()
            else:
                self._run_poll()
        except Exception as exc:
            log.warning("Monitor watcher crashed for %r: %s", self._label, exc)
            self._out.put(MonitorEvent(
                subject_id=self._subject_id,
                subject_label=self._label,
                event_type="deleted",   # placeholder — not stored
                path=self._watch_path,
                timestamp_utc=_utcnow(),
                error=str(exc),
                stopped=True,
            ))
        else:
            self._out.put(MonitorEvent(
                subject_id=self._subject_id,
                subject_label=self._label,
                event_type="deleted",   # placeholder — not stored
                path=self._watch_path,
                timestamp_utc=_utcnow(),
                stopped=True,
            ))
        log.debug("Monitor watcher stopped: %s", self._label)

    # ------------------------------------------------------------------
    # win32 backend
    # ------------------------------------------------------------------

    def _run_win32(self) -> None:
        notify_filter = (
            win32con.FILE_NOTIFY_CHANGE_FILE_NAME
            | win32con.FILE_NOTIFY_CHANGE_DIR_NAME
            | win32con.FILE_NOTIFY_CHANGE_LAST_WRITE
            | win32con.FILE_NOTIFY_CHANGE_SIZE
            | win32con.FILE_NOTIFY_CHANGE_CREATION
        )
        try:
            handle = win32file.CreateFile(
                self._watch_dir,
                0x0001,                               # FILE_LIST_DIRECTORY
                win32con.FILE_SHARE_READ
                | win32con.FILE_SHARE_WRITE
                | win32con.FILE_SHARE_DELETE,
                None,
                win32con.OPEN_EXISTING,
                win32con.FILE_FLAG_BACKUP_SEMANTICS,
                None,
            )
        except Exception as exc:
            log.warning(
                "win32 handle failed for %r, falling back to poll: %s",
                self._watch_dir, exc,
            )
            self._run_poll()
            return

        try:
            pending_rename: str | None = None   # old name from action=4
            while not self._stop.is_set():
                try:
                    results = win32file.ReadDirectoryChangesW(
                        handle,
                        _WIN32_BUF,
                        self._recursive,
                        notify_filter,
                        None,
                        None,
                    )
                except Exception as exc:
                    # Share went offline, path deleted, etc.
                    log.warning("ReadDirectoryChangesW error for %r: %s", self._watch_dir, exc)
                    break

                for action, filename in results:
                    if self._stop.is_set():
                        break

                    full = os.path.join(self._watch_dir, filename)

                    # File-subject filter
                    if self._filter_name and filename.lower() != self._filter_name:
                        pending_rename = None
                        continue

                    event_type = _ACTION_MAP.get(action)
                    if event_type is None:
                        continue

                    if action == 4:
                        # Old name in a rename pair; hold until we see action 5
                        pending_rename = full
                        continue

                    if action == 5:
                        old = pending_rename
                        pending_rename = None
                        self._emit("renamed", full, old_path=old)
                        continue

                    pending_rename = None
                    self._emit(event_type, full)
        finally:
            try:
                win32file.CloseHandle(handle)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Polling fallback backend
    # ------------------------------------------------------------------

    def _run_poll(self) -> None:
        snapshot = self._take_snapshot()
        while not self._stop.is_set():
            time.sleep(_POLL_INTERVAL)
            if self._stop.is_set():
                break
            new_snapshot = self._take_snapshot()
            self._diff_snapshots(snapshot, new_snapshot)
            snapshot = new_snapshot

    def _take_snapshot(self) -> dict[str, float]:
        result: dict[str, float] = {}
        try:
            if self._watch_type == "file":
                st = os.stat(self._watch_path)
                result[self._watch_path] = st.st_mtime
            else:
                for entry in os.scandir(self._watch_dir):
                    if entry.is_file(follow_symlinks=False):
                        try:
                            result[entry.path] = entry.stat(follow_symlinks=False).st_mtime
                        except OSError:
                            pass
        except OSError:
            pass
        return result

    def _diff_snapshots(
        self, old: dict[str, float], new: dict[str, float]
    ) -> None:
        for path in new:
            if path not in old:
                self._emit("created", path)
            elif new[path] != old[path]:
                self._emit("modified", path)
        for path in old:
            if path not in new:
                self._emit("deleted", path)


# ---------------------------------------------------------------------------
# Monitor controller (owned by Application, called from Tkinter main thread)
# ---------------------------------------------------------------------------

class MonitorController:
    def __init__(self) -> None:
        self._watchers: dict[int, tuple[_SubjectWatcher, threading.Event]] = {}
        self._event_queue: "queue.Queue[MonitorEvent]" = queue.Queue()

    # Public interface (Tkinter main thread only)

    def start_subject(
        self,
        subject_id: int,
        label: str,
        watch_path: str,
        watch_type: str,
        recursive: bool,
    ) -> bool:
        """Start watching *subject_id*. Returns False if already watching or at cap."""
        if subject_id in self._watchers:
            return False
        if len(self._watchers) >= _MAX_SUBJECTS:
            log.warning("Monitor cap (%d) reached; cannot add %r", _MAX_SUBJECTS, label)
            return False

        stop_event = threading.Event()
        watcher = _SubjectWatcher(
            subject_id=subject_id,
            label=label,
            watch_path=watch_path,
            watch_type=watch_type,
            recursive=recursive,
            out_queue=self._event_queue,
            stop_event=stop_event,
        )
        self._watchers[subject_id] = (watcher, stop_event)
        watcher.start()
        log.info("Started monitor watcher for %r (id=%d)", label, subject_id)
        return True

    def stop_subject(self, subject_id: int) -> None:
        pair = self._watchers.pop(subject_id, None)
        if pair:
            watcher, stop_event = pair
            stop_event.set()
            log.info("Stop requested for monitor subject id=%d", subject_id)

    def stop_all(self) -> None:
        for subject_id in list(self._watchers):
            self.stop_subject(subject_id)

    def is_watching(self, subject_id: int) -> bool:
        pair = self._watchers.get(subject_id)
        if pair is None:
            return False
        watcher, _ = pair
        return watcher.is_alive()

    def watching_count(self) -> int:
        return sum(1 for sid in self._watchers if self.is_watching(sid))

    def drain(self) -> list[MonitorEvent]:
        events: list[MonitorEvent] = []
        while True:
            try:
                ev = self._event_queue.get_nowait()
                events.append(ev)
                # If the watcher has stopped, remove it from the active dict
                if ev.stopped:
                    self._watchers.pop(ev.subject_id, None)
            except queue.Empty:
                break
        return events
