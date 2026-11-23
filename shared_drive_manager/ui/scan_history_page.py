"""Scan History page — admin and secret_admin only."""
from __future__ import annotations

import tkinter as tk
import tkinter.messagebox as messagebox
import tkinter.ttk as ttk
from typing import TYPE_CHECKING

from shared_drive_manager.core.path_utils import format_bytes
from shared_drive_manager.ui.theme import Theme

if TYPE_CHECKING:
    from shared_drive_manager.app import Application

_STATUS_COLORS = {
    "completed": Theme.GREEN,
    "running":   Theme.CYAN,
    "canceled":  Theme.AMBER,
    "failed":    Theme.RED,
    "pending":   Theme.MUTED,
}


class ScanHistoryPage(ttk.Frame):
    def __init__(self, parent: tk.Widget, app: "Application") -> None:
        super().__init__(parent)
        self.app = app
        self._build()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self) -> None:
        header = tk.Frame(self, bg=Theme.PANEL)
        header.pack(fill="x", padx=20, pady=(16, 8))

        tk.Label(header, text="● ● ●", bg=Theme.PANEL,
                 fg=Theme.MUTED, font=("Consolas", 9)).pack(side="left")
        tk.Label(header, text="  SCAN HISTORY", bg=Theme.PANEL,
                 fg=Theme.TEXT, font=("Segoe UI Semibold", 11)).pack(side="left")

        tk.Button(
            header, text="↺  Refresh",
            bg=Theme.PANEL_2, fg=Theme.MUTED, font=("Segoe UI", 9),
            relief="flat", padx=10, pady=3, cursor="hand2",
            activebackground=Theme.PANEL_3, activeforeground=Theme.TEXT,
            command=self._load,
        ).pack(side="right")

        tk.Frame(self, bg=Theme.BORDER, height=1).pack(fill="x", padx=20)

        # Treeview
        tree_frame = tk.Frame(self, bg=Theme.BG)
        tree_frame.pack(fill="both", expand=True, padx=20, pady=12)

        cols = ("run_id", "run_type", "status", "started", "ended",
                "files", "size", "violations", "errors")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                  selectmode="browse")

        self._tree.heading("run_id",     text="Run #")
        self._tree.heading("run_type",   text="Type")
        self._tree.heading("status",     text="Status")
        self._tree.heading("started",    text="Started (UTC)")
        self._tree.heading("ended",      text="Ended (UTC)")
        self._tree.heading("files",      text="Files")
        self._tree.heading("size",       text="Size")
        self._tree.heading("violations", text="Violations")
        self._tree.heading("errors",     text="Errors")

        self._tree.column("run_id",     width=60,  minwidth=40,  anchor="e")
        self._tree.column("run_type",   width=100, minwidth=70,  anchor="w")
        self._tree.column("status",     width=100, minwidth=70,  anchor="w")
        self._tree.column("started",    width=160, minwidth=110, anchor="w")
        self._tree.column("ended",      width=160, minwidth=110, anchor="w")
        self._tree.column("files",      width=90,  minwidth=60,  anchor="e")
        self._tree.column("size",       width=90,  minwidth=60,  anchor="e")
        self._tree.column("violations", width=90,  minwidth=60,  anchor="e")
        self._tree.column("errors",     width=70,  minwidth=50,  anchor="e")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree.pack(fill="both", expand=True)
        self._tree.tag_configure("empty", foreground=Theme.MUTED)

        for status, color in _STATUS_COLORS.items():
            self._tree.tag_configure(status, foreground=color)

        # Bottom action bar
        bottom = tk.Frame(self, bg=Theme.BG)
        bottom.pack(fill="x", padx=20, pady=(0, 14))

        tk.Button(
            bottom, text="Delete Selected Run",
            bg=Theme.PANEL_2, fg=Theme.RED, font=("Segoe UI", 9),
            relief="flat", padx=12, pady=4, cursor="hand2",
            activebackground=Theme.PANEL_3, activeforeground=Theme.TEXT,
            command=self._delete_selected,
        ).pack(side="left")

        self._status_var = tk.StringVar()
        tk.Label(bottom, textvariable=self._status_var, bg=Theme.BG,
                 fg=Theme.RED, font=("Segoe UI", 9)).pack(side="left", padx=12)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _load(self) -> None:
        self._tree.delete(*self._tree.get_children())
        self._status_var.set("")

        conn = self.app.get_db()
        runs = self.app.scan_run_repo.list_all(conn)

        for run in runs:
            status = run.get("status", "")
            tag = status if status in _STATUS_COLORS else ""
            self._tree.insert(
                "", "end",
                iid=str(run["run_id"]),
                values=(
                    run["run_id"],
                    run.get("run_type", ""),
                    status,
                    (run.get("started_at_utc") or "")[:16],
                    (run.get("ended_at_utc") or "")[:16],
                    f"{run.get('files_seen', 0):,}",
                    format_bytes(run.get("bytes_seen", 0)),
                    f"{run.get('violations_seen', 0):,}",
                    run.get("errors_seen", 0),
                ),
                tags=(tag,) if tag else (),
            )

        if not runs:
            self._tree.insert("", "end",
                              values=("(no scan runs)", "", "", "", "",
                                      "", "", "", ""),
                              tags=("empty",))

    def on_tab_activate(self) -> None:
        self._load()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _delete_selected(self) -> None:
        sel = self._tree.selection()
        if not sel:
            self._status_var.set("Select a run to delete.")
            return

        try:
            run_id = int(sel[0])
        except ValueError:
            return

        vals = self._tree.item(sel[0], "values")
        status = vals[2] if len(vals) > 2 else ""

        if status == "running":
            self._status_var.set("Cannot delete a run that is currently running.")
            return

        started = vals[3] or "unknown"
        files   = vals[5]
        viols   = vals[7]

        if not messagebox.askyesno(
            "Delete Scan Run",
            f"Permanently delete run #{run_id}?\n\n"
            f"  Started:    {started}\n"
            f"  Files:      {files}\n"
            f"  Violations: {viols}\n\n"
            "This will remove all violations, errors, and directory records "
            "for this run. File inventory entries only seen in this run will "
            "also be removed. This cannot be undone.",
            parent=self,
        ):
            return

        conn = self.app.get_db()
        try:
            self.app.scan_run_repo.delete(conn, run_id)
        except Exception as exc:
            self._status_var.set(f"Error: {exc}")
            return

        self._load()
