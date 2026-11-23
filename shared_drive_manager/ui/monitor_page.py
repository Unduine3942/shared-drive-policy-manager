"""Live file-system monitoring tab."""
from __future__ import annotations

import csv
import logging
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING

from shared_drive_manager.ui.theme import Theme
from shared_drive_manager.ui.widgets import section_header, separator

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from shared_drive_manager.app import Application

_POLL_MS = 400
_FEED_CAP = 2000

_TYPE_COLORS: dict[str, str] = {
    "created":  Theme.GREEN,
    "modified": Theme.BLUE,
    "deleted":  Theme.RED,
    "renamed":  Theme.AMBER,
}

_STATUS_WATCHING = "Watching"
_STATUS_IDLE     = "Idle"
_STATUS_STOPPED  = "Stopped"
_STATUS_ERROR    = "Error"

_FILTER_OPTIONS = ["All", "created", "modified", "deleted", "renamed"]


class MonitorPage(ttk.Frame):
    def __init__(self, parent: tk.Widget, app: "Application") -> None:
        super().__init__(parent)
        self._app = app
        self._event_count = 0
        self._filter_var = tk.StringVar(value="All")
        self._build()
        self._schedule_poll()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self) -> None:
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=6, pady=6)

        left = ttk.Frame(paned, width=270)
        left.pack_propagate(False)
        paned.add(left, weight=0)

        right = ttk.Frame(paned)
        paned.add(right, weight=1)

        self._build_left(left)
        self._build_right(right)

    def _build_left(self, parent: ttk.Frame) -> None:
        section_header(parent, "Monitored Subjects")
        separator(parent)

        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill="both", expand=True)

        cols = ("label", "type", "status")
        self._subj_tree = ttk.Treeview(
            tree_frame,
            columns=cols,
            show="headings",
            selectmode="browse",
            height=14,
        )
        self._subj_tree.heading("label",  text="Label")
        self._subj_tree.heading("type",   text="Type")
        self._subj_tree.heading("status", text="Status")
        self._subj_tree.column("label",  width=130, stretch=True)
        self._subj_tree.column("type",   width=65,  stretch=False)
        self._subj_tree.column("status", width=70,  stretch=False)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._subj_tree.yview)
        self._subj_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._subj_tree.pack(fill="both", expand=True)
        self._subj_tree.tag_configure("empty", foreground=Theme.MUTED)

        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill="x", pady=(6, 0))

        ttk.Button(btn_frame, text="Add Path…",  command=self._add_subject).pack(fill="x", pady=1)
        ttk.Button(btn_frame, text="Remove",      command=self._remove_subject).pack(fill="x", pady=1)
        ttk.Separator(btn_frame, orient="horizontal").pack(fill="x", pady=4)
        ttk.Button(btn_frame, text="Start",       command=self._start_selected).pack(fill="x", pady=1)
        ttk.Button(btn_frame, text="Stop",        command=self._stop_selected).pack(fill="x", pady=1)
        ttk.Button(btn_frame, text="Stop All",    command=self._stop_all).pack(fill="x", pady=1)

    def _build_right(self, parent: ttk.Frame) -> None:
        filter_bar = ttk.Frame(parent)
        filter_bar.pack(fill="x", pady=(0, 4))

        ttk.Label(filter_bar, text="Filter:").pack(side="left", padx=(0, 4))
        self._filter_cb = ttk.Combobox(
            filter_bar,
            textvariable=self._filter_var,
            values=_FILTER_OPTIONS,
            state="readonly",
            width=12,
        )
        self._filter_cb.pack(side="left")
        self._filter_cb.bind("<<ComboboxSelected>>", self._on_filter_change)

        ttk.Button(filter_bar, text="Clear Feed",   command=self._clear_feed).pack(side="left", padx=(8, 2))
        ttk.Button(filter_bar, text="Export CSV…", command=self._export_csv).pack(side="left", padx=2)

        separator(parent)

        feed_frame = ttk.Frame(parent)
        feed_frame.pack(fill="both", expand=True)

        feed_cols = ("time", "type", "subject", "path", "details")
        self._feed_tree = ttk.Treeview(
            feed_frame,
            columns=feed_cols,
            show="headings",
            selectmode="browse",
        )
        self._feed_tree.heading("time",    text="Time (UTC)")
        self._feed_tree.heading("type",    text="Type")
        self._feed_tree.heading("subject", text="Subject")
        self._feed_tree.heading("path",    text="Path")
        self._feed_tree.heading("details", text="Details")
        self._feed_tree.column("time",    width=130, stretch=False)
        self._feed_tree.column("type",    width=70,  stretch=False)
        self._feed_tree.column("subject", width=110, stretch=False)
        self._feed_tree.column("path",    width=320, stretch=True)
        self._feed_tree.column("details", width=200, stretch=True)

        for etype, color in _TYPE_COLORS.items():
            self._feed_tree.tag_configure(etype, foreground=color)
        self._feed_tree.tag_configure("error_row", foreground=Theme.RED)
        self._feed_tree.tag_configure("empty", foreground=Theme.MUTED)

        vsb2 = ttk.Scrollbar(feed_frame, orient="vertical", command=self._feed_tree.yview)
        hsb2 = ttk.Scrollbar(feed_frame, orient="horizontal", command=self._feed_tree.xview)
        self._feed_tree.configure(yscrollcommand=vsb2.set, xscrollcommand=hsb2.set)
        vsb2.pack(side="right", fill="y")
        hsb2.pack(side="bottom", fill="x")
        self._feed_tree.pack(fill="both", expand=True)

        self._status_var = tk.StringVar(value="0 events | watching 0 subjects")
        ttk.Label(parent, textvariable=self._status_var, anchor="w").pack(
            fill="x", pady=(4, 0)
        )

        # In-memory feed rows (for export — stores all rows regardless of filter)
        self._feed_rows: list[tuple] = []

    # ------------------------------------------------------------------
    # Subject management
    # ------------------------------------------------------------------

    def _add_subject(self) -> None:
        dialog = _AddSubjectDialog(self, self._app)
        if dialog.result is None:
            return
        label, path, watch_type, recursive = dialog.result
        try:
            subject_id = self._app.monitor_subject_repo.add(
                self._app.get_db(), label, path, watch_type, recursive
            )
        except Exception as exc:
            messagebox.showerror("Add Subject", f"Could not add subject:\n{exc}", parent=self)
            return
        self._subj_tree.insert(
            "", "end",
            iid=str(subject_id),
            values=(label, watch_type, _STATUS_IDLE),
        )

    def _remove_subject(self) -> None:
        sel = self._subj_tree.selection()
        if not sel:
            return
        subject_id = int(sel[0])

        watching = self._app.monitor_controller.is_watching(subject_id)
        if watching:
            if not messagebox.askyesno(
                "Remove Subject",
                "This subject is currently being watched.\nStop watching and remove it?",
                parent=self,
            ):
                return
            self._app.monitor_controller.stop_subject(subject_id)

        try:
            self._app.monitor_subject_repo.remove(self._app.get_db(), subject_id)
        except Exception as exc:
            messagebox.showerror("Remove Subject", f"Could not remove:\n{exc}", parent=self)
            return

        self._subj_tree.delete(sel[0])

    def _start_selected(self) -> None:
        sel = self._subj_tree.selection()
        if not sel:
            return
        subject_id = int(sel[0])
        if self._app.monitor_controller.is_watching(subject_id):
            return

        row = self._subj_tree.item(sel[0], "values")
        label, watch_type, _ = row

        # Reload watch_path from DB
        subjects = self._app.monitor_subject_repo.list_all(self._app.get_db())
        subject = next((s for s in subjects if s["subject_id"] == subject_id), None)
        if subject is None:
            return

        started = self._app.monitor_controller.start_subject(
            subject_id=subject_id,
            label=subject["label"],
            watch_path=subject["watch_path"],
            watch_type=subject["watch_type"],
            recursive=bool(subject["recursive"]),
        )
        if started:
            self._subj_tree.set(sel[0], "status", _STATUS_WATCHING)
        else:
            messagebox.showwarning(
                "Monitor",
                "Could not start watcher (cap reached or already watching).",
                parent=self,
            )

    def _stop_selected(self) -> None:
        sel = self._subj_tree.selection()
        if not sel:
            return
        subject_id = int(sel[0])
        self._app.monitor_controller.stop_subject(subject_id)
        self._subj_tree.set(sel[0], "status", _STATUS_STOPPED)

    def _stop_all(self) -> None:
        self._app.monitor_controller.stop_all()
        for iid in self._subj_tree.get_children():
            self._subj_tree.set(iid, "status", _STATUS_STOPPED)

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------

    def _schedule_poll(self) -> None:
        self.after(_POLL_MS, self._poll)

    def _poll(self) -> None:
        try:
            events = self._app.monitor_controller.drain()
            if events:
                self._handle_events(events)
        finally:
            self._schedule_poll()

    def _handle_events(self, events) -> None:
        to_store = []
        current_filter = self._filter_var.get()

        for ev in events:
            if ev.stopped:
                self._mark_subject_stopped(ev.subject_id, bool(ev.error))
                continue

            details = ""
            if ev.event_type == "renamed" and ev.old_path:
                details = f"← {ev.old_path}"
            elif ev.error:
                details = f"Error: {ev.error}"

            row = (ev.timestamp_utc, ev.event_type, ev.subject_label, ev.path, details)
            self._feed_rows.append(row)
            self._event_count += 1

            tag = "error_row" if ev.error else ev.event_type
            if current_filter in ("All", ev.event_type):
                self._insert_feed_row(row, tag)

            if not ev.error:
                to_store.append({
                    "subject_id":     ev.subject_id,
                    "event_type":     ev.event_type,
                    "path":           ev.path,
                    "old_path":       ev.old_path,
                    "created_at_utc": ev.timestamp_utc,
                })

        if to_store:
            try:
                self._app.monitor_event_repo.add_batch(self._app.get_db(), to_store)
            except Exception as exc:
                log.error("Failed to store monitor events: %s", exc)

        self._trim_feed()
        self._update_status()

    def _insert_feed_row(self, row: tuple, tag: str) -> None:
        self._feed_tree.insert("", 0, values=row, tags=(tag,))

    def _trim_feed(self) -> None:
        children = self._feed_tree.get_children()
        excess = len(children) - _FEED_CAP
        if excess > 0:
            for iid in children[-excess:]:
                self._feed_tree.delete(iid)

    def _mark_subject_stopped(self, subject_id: int, is_error: bool) -> None:
        iid = str(subject_id)
        if self._subj_tree.exists(iid):
            status = _STATUS_ERROR if is_error else _STATUS_STOPPED
            self._subj_tree.set(iid, "status", status)

    def _update_status(self) -> None:
        watching = self._app.monitor_controller.watching_count()
        self._status_var.set(f"{self._event_count} events | watching {watching} subjects")

    # ------------------------------------------------------------------
    # Feed controls
    # ------------------------------------------------------------------

    def _on_filter_change(self, _event=None) -> None:
        current_filter = self._filter_var.get()
        for iid in self._feed_tree.get_children():
            self._feed_tree.delete(iid)
        for row in reversed(self._feed_rows[-_FEED_CAP:]):
            etype = row[1]
            if current_filter in ("All", etype):
                tag = etype if etype in _TYPE_COLORS else "error_row"
                self._feed_tree.insert("", 0, values=row, tags=(tag,))

    def _clear_feed(self) -> None:
        for iid in self._feed_tree.get_children():
            self._feed_tree.delete(iid)
        self._feed_rows.clear()
        self._event_count = 0
        try:
            self._app.monitor_event_repo.clear(self._app.get_db())
        except Exception as exc:
            log.error("Failed to clear monitor events: %s", exc)
        self._update_status()

    def _export_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export Event Feed",
        )
        if not path:
            return
        try:
            current_filter = self._filter_var.get()
            rows = self._feed_rows if current_filter == "All" else [
                r for r in self._feed_rows if r[1] == current_filter
            ]
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(["Time (UTC)", "Type", "Subject", "Path", "Details"])
                writer.writerows(rows)
            messagebox.showinfo("Export", f"Exported {len(rows)} rows to:\n{path}", parent=self)
        except Exception as exc:
            messagebox.showerror("Export Error", str(exc), parent=self)

    # ------------------------------------------------------------------
    # Tab activate
    # ------------------------------------------------------------------

    def on_tab_activate(self) -> None:
        self._refresh_subjects()

    def _refresh_subjects(self) -> None:
        try:
            subjects = self._app.monitor_subject_repo.list_all(self._app.get_db())
        except Exception as exc:
            log.error("Failed to refresh monitor subjects: %s", exc)
            return

        existing_ids = set(self._subj_tree.get_children())
        db_ids = {str(s["subject_id"]) for s in subjects}

        # Remove subjects deleted from DB while tab was inactive
        for iid in existing_ids - db_ids:
            self._subj_tree.delete(iid)

        for s in subjects:
            iid = str(s["subject_id"])
            watching = self._app.monitor_controller.is_watching(s["subject_id"])
            status = _STATUS_WATCHING if watching else _STATUS_IDLE
            if iid in existing_ids:
                # Preserve "Stopped" / "Error" status set by watcher exit
                current = self._subj_tree.set(iid, "status")
                if current not in (_STATUS_STOPPED, _STATUS_ERROR, _STATUS_WATCHING):
                    self._subj_tree.set(iid, "status", status)
            else:
                self._subj_tree.insert(
                    "", "end",
                    iid=iid,
                    values=(s["label"], s["watch_type"], status),
                )

        if not subjects:
            self._subj_tree.insert("", "end",
                                   values=("(no subjects)", "", ""),
                                   tags=("empty",))

        self._update_status()


# ---------------------------------------------------------------------------
# Add-subject dialog
# ---------------------------------------------------------------------------

class _AddSubjectDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, app: "Application") -> None:
        super().__init__(parent)
        self.title("Add Monitor Subject")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self._app = app
        self.result: tuple | None = None
        self._build()
        self.wait_window(self)

    def _build(self) -> None:
        pad = {"padx": 8, "pady": 4}
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Label:").grid(row=0, column=0, sticky="e", **pad)
        self._label_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self._label_var, width=42).grid(
            row=0, column=1, columnspan=2, sticky="ew", **pad
        )

        ttk.Label(frm, text="Path:").grid(row=1, column=0, sticky="e", **pad)
        self._path_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self._path_var, width=42).grid(
            row=1, column=1, sticky="ew", **pad
        )
        ttk.Button(frm, text="Browse…", command=self._browse).grid(
            row=1, column=2, **pad
        )

        ttk.Label(frm, text="Watch type:").grid(row=2, column=0, sticky="e", **pad)
        self._type_var = tk.StringVar(value="directory")
        type_frame = ttk.Frame(frm)
        type_frame.grid(row=2, column=1, columnspan=2, sticky="w", **pad)
        ttk.Radiobutton(type_frame, text="Directory", variable=self._type_var,
                         value="directory").pack(side="left", padx=(0, 12))
        ttk.Radiobutton(type_frame, text="File",      variable=self._type_var,
                         value="file").pack(side="left")

        self._recursive_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frm, text="Recursive (subdirectories)", variable=self._recursive_var
        ).grid(row=3, column=1, columnspan=2, sticky="w", **pad)

        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=4, column=0, columnspan=3, pady=(8, 0))
        ttk.Button(btn_frame, text="Add",    command=self._save).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=4)

        frm.columnconfigure(1, weight=1)

    def _browse(self) -> None:
        if self._type_var.get() == "directory":
            path = filedialog.askdirectory(parent=self, title="Select Directory to Watch")
        else:
            path = filedialog.askopenfilename(parent=self, title="Select File to Watch")
        if path:
            self._path_var.set(path)
            if not self._label_var.get():
                self._label_var.set(os.path.basename(path) or path)

    def _save(self) -> None:
        label = self._label_var.get().strip()
        path  = self._path_var.get().strip()
        if not label:
            messagebox.showwarning("Validation", "Label is required.", parent=self)
            return
        if not path:
            messagebox.showwarning("Validation", "Path is required.", parent=self)
            return
        if not os.path.exists(path):
            if not messagebox.askyesno(
                "Path not found",
                f"'{path}' does not currently exist.\nAdd it anyway?",
                parent=self,
            ):
                return
        self.result = (label, path, self._type_var.get(), self._recursive_var.get())
        self.destroy()
