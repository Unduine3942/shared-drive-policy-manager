"""Scan setup and progress page."""
from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING

from shared_drive_manager import config
from shared_drive_manager.core.models import ProgressEvent
from shared_drive_manager.core.path_utils import format_bytes
from shared_drive_manager.ui.theme import Theme
from shared_drive_manager.ui.widgets import ScrolledText, SparkLine, StatCard, section_header, separator

if TYPE_CHECKING:
    from shared_drive_manager.app import Application

_POLL_MS = 400


# ---------------------------------------------------------------------------
# Add-root dialog
# ---------------------------------------------------------------------------

class AddRootDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, on_save) -> None:
        super().__init__(parent)
        self.title("Add Scan Root")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self._on_save = on_save
        self._build()
        self.wait_window(self)

    def _build(self) -> None:
        pad = {"padx": 8, "pady": 4}

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Label:").grid(row=0, column=0, sticky="e", **pad)
        self._label_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self._label_var, width=40).grid(
            row=0, column=1, columnspan=2, sticky="ew", **pad
        )

        ttk.Label(frm, text="Path:").grid(row=1, column=0, sticky="e", **pad)
        self._path_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self._path_var, width=40).grid(
            row=1, column=1, sticky="ew", **pad
        )
        ttk.Button(frm, text="Browse…", command=self._browse).grid(
            row=1, column=2, **pad
        )

        ttk.Label(frm, text="Exclude globs:").grid(row=2, column=0, sticky="ne", **pad)
        self._excl_var = tk.StringVar(value=", ".join(config.DEFAULT_EXCLUDE_GLOBS))
        ttk.Entry(frm, textvariable=self._excl_var, width=40).grid(
            row=2, column=1, columnspan=2, sticky="ew", **pad
        )
        ttk.Label(frm, text="(comma-separated, e.g. ~$*, *.tmp)", foreground="grey").grid(
            row=3, column=1, columnspan=2, sticky="w", padx=8
        )

        ttk.Label(frm, text="Max depth:").grid(row=4, column=0, sticky="e", **pad)
        self._depth_var = tk.StringVar(value="")
        ttk.Entry(frm, textvariable=self._depth_var, width=10).grid(
            row=4, column=1, sticky="w", **pad
        )
        ttk.Label(frm, text="(blank = unlimited)", foreground="grey").grid(
            row=4, column=2, sticky="w"
        )

        self._symlinks_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="Follow symbolic links", variable=self._symlinks_var).grid(
            row=5, column=1, columnspan=2, sticky="w", **pad
        )

        frm.columnconfigure(1, weight=1)

        btn_frm = ttk.Frame(self, padding=(12, 0, 12, 12))
        btn_frm.pack(fill="x")
        ttk.Button(btn_frm, text="Cancel", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btn_frm, text="Add Root", style="Accent.TButton", command=self._save).pack(
            side="right"
        )

    def _browse(self) -> None:
        path = filedialog.askdirectory(title="Select scan root folder", mustexist=True)
        if path:
            self._path_var.set(path)
            if not self._label_var.get():
                self._label_var.set(os.path.basename(path) or path)

    def _save(self) -> None:
        label = self._label_var.get().strip()
        root_path = self._path_var.get().strip()
        if not label:
            messagebox.showerror("Validation", "Label is required.", parent=self)
            return
        if not root_path:
            messagebox.showerror("Validation", "Path is required.", parent=self)
            return

        excl_raw = self._excl_var.get()
        exclude_globs = [g.strip() for g in excl_raw.split(",") if g.strip()]

        max_depth: int | None = None
        depth_str = self._depth_var.get().strip()
        if depth_str:
            try:
                max_depth = int(depth_str)
                if max_depth < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Validation", "Max depth must be a positive integer.", parent=self)
                return

        self._on_save({
            "label": label,
            "root_path": root_path,
            "exclude_globs": exclude_globs,
            "max_depth": max_depth,
            "follow_symlinks": self._symlinks_var.get(),
        })
        self.destroy()


# ---------------------------------------------------------------------------
# Resume scan dialog
# ---------------------------------------------------------------------------

class ResumeScanDialog(tk.Toplevel):
    """Pick an interrupted scan run to resume."""

    def __init__(self, parent: tk.Widget, runs: list[dict], on_resume) -> None:
        super().__init__(parent)
        self.title("Resume Interrupted Scan")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self._runs = runs
        self._on_resume = on_resume
        self._build()
        self.wait_window(self)

    def _build(self) -> None:
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(
            frm,
            text="Select an interrupted scan run to resume:",
        ).pack(anchor="w", pady=(0, 6))

        cols = ("run_id", "run_type", "started", "dirs", "files", "errors")
        self._tree = ttk.Treeview(
            frm, columns=cols, show="headings", height=8, selectmode="browse"
        )
        self._tree.heading("run_id",   text="Run #")
        self._tree.heading("run_type", text="Type")
        self._tree.heading("started",  text="Started (UTC)")
        self._tree.heading("dirs",     text="Dirs")
        self._tree.heading("files",    text="Files")
        self._tree.heading("errors",   text="Errors")
        self._tree.column("run_id",   width=60,  anchor="e")
        self._tree.column("run_type", width=90,  anchor="w")
        self._tree.column("started",  width=145, anchor="w")
        self._tree.column("dirs",     width=70,  anchor="e")
        self._tree.column("files",    width=80,  anchor="e")
        self._tree.column("errors",   width=70,  anchor="e")

        vsb = ttk.Scrollbar(frm, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        for r in self._runs:
            self._tree.insert(
                "", "end",
                iid=str(r["run_id"]),
                values=(
                    r["run_id"],
                    r.get("run_type", ""),
                    (r.get("started_at_utc") or "")[:16],
                    r.get("directories_seen", 0),
                    r.get("files_seen", 0),
                    r.get("errors_seen", 0),
                ),
            )

        if self._runs:
            first_iid = str(self._runs[0]["run_id"])
            self._tree.selection_set(first_iid)
            self._tree.focus(first_iid)

        btn_frm = ttk.Frame(self, padding=(12, 0, 12, 12))
        btn_frm.pack(fill="x")
        ttk.Button(btn_frm, text="Cancel", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(
            btn_frm, text="Resume Selected", style="Accent.TButton", command=self._resume
        ).pack(side="right")

    def _resume(self) -> None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Select Run", "Please select a run to resume.", parent=self)
            return
        run_id = int(sel[0])
        self.destroy()
        self._on_resume(run_id)


# ---------------------------------------------------------------------------
# Scan page
# ---------------------------------------------------------------------------

class ScanPage(ttk.Frame):
    def __init__(self, parent: tk.Widget, app: "Application") -> None:
        super().__init__(parent)
        self.app = app
        self._polling = False

        # Running totals for progress display
        self._total_files = 0
        self._total_bytes = 0
        self._total_violations = 0
        self._total_errors = 0
        self._total_dirs = 0

        self._build()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=8)
        outer.pack(fill="both", expand=True)

        # ---- Scan Roots ------------------------------------------------
        section_header(outer, "Scan Roots").pack(fill="x", pady=(0, 2))

        roots_frm = ttk.Frame(outer)
        roots_frm.pack(fill="x")

        cols = ("label", "path", "depth", "symlinks")
        self._roots_tree = ttk.Treeview(
            roots_frm,
            columns=cols,
            show="headings",
            height=5,
            selectmode="browse",
        )
        self._roots_tree.heading("label", text="Label")
        self._roots_tree.heading("path", text="Path")
        self._roots_tree.heading("depth", text="Max Depth")
        self._roots_tree.heading("symlinks", text="Follow Links")
        self._roots_tree.column("label", width=140, minwidth=80)
        self._roots_tree.column("path", width=340, minwidth=120)
        self._roots_tree.column("depth", width=80, minwidth=60, anchor="center")
        self._roots_tree.column("symlinks", width=90, minwidth=60, anchor="center")

        sb = ttk.Scrollbar(roots_frm, orient="vertical", command=self._roots_tree.yview)
        self._roots_tree.configure(yscrollcommand=sb.set)
        self._roots_tree.pack(side="left", fill="x", expand=True)
        sb.pack(side="left", fill="y")
        self._roots_tree.tag_configure("empty", foreground=Theme.MUTED)

        root_btn_frm = ttk.Frame(outer)
        root_btn_frm.pack(fill="x", pady=4)
        ttk.Button(root_btn_frm, text="Add Root…", command=self._add_root).pack(side="left", padx=(0, 4))
        ttk.Button(root_btn_frm, text="Remove Root", command=self._remove_root).pack(side="left", padx=4)
        ttk.Button(root_btn_frm, text="Validate Access", command=self._validate_access).pack(side="left", padx=4)

        separator(outer).pack(fill="x", pady=6)

        # ---- Scan Options -----------------------------------------------
        section_header(outer, "Scan Options").pack(fill="x", pady=(0, 2))

        opts_frm = ttk.Frame(outer)
        opts_frm.pack(fill="x")

        ttk.Label(opts_frm, text="Workers:").grid(row=0, column=0, sticky="e", padx=4, pady=3)
        self._workers_var = tk.StringVar()
        ttk.Spinbox(
            opts_frm, textvariable=self._workers_var,
            from_=1, to=config.MAX_WORKERS, width=5
        ).grid(row=0, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(opts_frm, text="Batch size:").grid(row=0, column=2, sticky="e", padx=8, pady=3)
        self._batch_var = tk.StringVar()
        ttk.Spinbox(
            opts_frm, textvariable=self._batch_var,
            from_=100, to=10000, increment=100, width=7
        ).grid(row=0, column=3, sticky="w", padx=4, pady=3)

        ttk.Label(opts_frm, text="(saved in Settings)", foreground="grey").grid(
            row=0, column=4, sticky="w", padx=4
        )

        separator(outer).pack(fill="x", pady=6)

        # ---- Action buttons ---------------------------------------------
        action_frm = ttk.Frame(outer)
        action_frm.pack(fill="x", pady=4)

        self._btn_full = ttk.Button(
            action_frm, text="Start Full Scan", style="Accent.TButton",
            command=self._start_full
        )
        self._btn_full.pack(side="left", padx=(0, 4))

        self._btn_incr = ttk.Button(
            action_frm, text="Start Incremental Scan",
            command=self._start_incremental
        )
        self._btn_incr.pack(side="left", padx=4)

        self._btn_resume = ttk.Button(
            action_frm, text="Resume Interrupted Scan…",
            command=self._resume_scan
        )
        self._btn_resume.pack(side="left", padx=4)

        self._btn_cancel = ttk.Button(
            action_frm, text="Cancel Scan", state="disabled",
            command=self._cancel_scan
        )
        self._btn_cancel.pack(side="left", padx=4)

        separator(outer).pack(fill="x", pady=6)

        # ---- Progress ---------------------------------------------------
        section_header(outer, "Progress").pack(fill="x", pady=(0, 2))

        self._progress_bar = ttk.Progressbar(outer, mode="indeterminate", length=400)
        self._progress_bar.pack(fill="x", pady=(0, 2))

        self._sparkline = SparkLine(outer, height=36, color=Theme.CYAN)
        self._sparkline.pack(fill="x", pady=(0, 6))

        stats_frm = tk.Frame(outer, bg=Theme.BG)
        stats_frm.pack(fill="x", pady=(0, 6))
        for i in range(5):
            stats_frm.columnconfigure(i, weight=1, uniform="sc")

        self._card_files = StatCard(stats_frm, "FILES", "0", Theme.CYAN)
        self._card_files.grid(row=0, column=0, sticky="ew", padx=2)
        self._card_size = StatCard(stats_frm, "SIZE", "0 B", Theme.BLUE)
        self._card_size.grid(row=0, column=1, sticky="ew", padx=2)
        self._card_dirs = StatCard(stats_frm, "DIRS", "0", Theme.MUTED)
        self._card_dirs.grid(row=0, column=2, sticky="ew", padx=2)
        self._card_violations = StatCard(stats_frm, "VIOLATIONS", "0", Theme.AMBER)
        self._card_violations.grid(row=0, column=3, sticky="ew", padx=2)
        self._card_errors = StatCard(stats_frm, "ERRORS", "0", Theme.RED)
        self._card_errors.grid(row=0, column=4, sticky="ew", padx=2)

        self._log = ScrolledText(outer, height=10, state="disabled", wrap="none")
        self._log.pack(fill="both", expand=True, pady=(4, 0))

        self._refresh_roots()
        self._sync_settings_from_app()

    # ------------------------------------------------------------------
    # Roots management
    # ------------------------------------------------------------------

    def _refresh_roots(self) -> None:
        for iid in self._roots_tree.get_children():
            self._roots_tree.delete(iid)
        roots = self.app.scan_root_repo.list_active(self.app.conn)
        for r in roots:
            depth_str = str(r["max_depth"]) if r["max_depth"] is not None else "unlimited"
            sym_str = "Yes" if r["follow_symlinks"] else "No"
            self._roots_tree.insert(
                "", "end",
                iid=str(r["root_id"]),
                values=(r["label"], r["root_path"], depth_str, sym_str),
            )
        if not roots:
            self._roots_tree.insert("", "end",
                                    values=("(no scan roots defined)", "", "", ""),
                                    tags=("empty",))

    def _add_root(self) -> None:
        def on_save(data: dict) -> None:
            try:
                self.app.scan_root_repo.create(
                    self.app.conn,
                    label=data["label"],
                    root_path=data["root_path"],
                    exclude_globs=data["exclude_globs"],
                    max_depth=data["max_depth"],
                    follow_symlinks=data["follow_symlinks"],
                )
            except Exception as exc:
                messagebox.showerror("Error", f"Could not save root:\n{exc}", parent=self)
                return
            self._refresh_roots()
            self._log_append(f"Root added: {data['root_path']}")

        AddRootDialog(self, on_save)

    def _remove_root(self) -> None:
        sel = self._roots_tree.selection()
        if not sel:
            messagebox.showinfo("Remove Root", "Select a root to remove.", parent=self)
            return
        root_id = int(sel[0])
        item = self._roots_tree.item(sel[0])
        path = item["values"][1]
        if not messagebox.askyesno(
            "Remove Root",
            f"Deactivate scan root?\n\n{path}\n\n"
            "Existing file records are kept. You can re-add the root later.",
            parent=self,
        ):
            return
        self.app.scan_root_repo.deactivate(self.app.conn, root_id)
        self._refresh_roots()
        self._log_append(f"Root removed: {path}")

    def _validate_access(self) -> None:
        sel = self._roots_tree.selection()
        if not sel:
            messagebox.showinfo("Validate Access", "Select a root to validate.", parent=self)
            return
        item = self._roots_tree.item(sel[0])
        path = item["values"][1]
        try:
            entries = list(os.scandir(path))
            messagebox.showinfo(
                "Validate Access",
                f"Access OK.\n\nPath: {path}\nTop-level entries: {len(entries)}",
                parent=self,
            )
        except Exception as exc:
            messagebox.showerror(
                "Validate Access",
                f"Cannot access path:\n{path}\n\n{exc}",
                parent=self,
            )

    # ------------------------------------------------------------------
    # Scan actions
    # ------------------------------------------------------------------

    def _sync_settings_from_app(self) -> None:
        self._workers_var.set(str(self.app.get_setting("max_workers", config.DEFAULT_WORKERS)))
        self._batch_var.set(str(self.app.get_setting("batch_size", config.DEFAULT_BATCH_SIZE)))

    def _start_full(self) -> None:
        self._start_scan("full")

    def _start_incremental(self) -> None:
        self._start_scan("incremental")

    def _start_scan(self, run_type: str) -> None:
        if self.app.scan_controller.is_running():
            messagebox.showinfo("Scan Running", "A scan is already running.", parent=self)
            return

        roots = self.app.scan_root_repo.list_active(self.app.conn)
        if not roots:
            messagebox.showwarning(
                "No Roots", "Add at least one scan root before starting.", parent=self
            )
            return

        # Persist workers/batch changes to settings
        try:
            workers = int(self._workers_var.get())
            batch = int(self._batch_var.get())
            self.app.save_setting("max_workers", workers)
            self.app.save_setting("batch_size", batch)
        except ValueError:
            pass

        # Reset progress display
        self._total_files = self._total_bytes = self._total_violations = 0
        self._total_errors = self._total_dirs = 0
        self._sparkline._points.clear()
        self._update_stats_labels()
        self._clear_log()

        root_ids = [r["root_id"] for r in roots]
        self.app.scan_controller.start(root_ids, run_type)

        self._btn_full.config(state="disabled")
        self._btn_incr.config(state="disabled")
        self._btn_resume.config(state="disabled")
        self._btn_cancel.config(state="normal")
        self._progress_bar.start(12)

        self._log_append(f"Starting {run_type} scan of {len(roots)} root(s)…")

        if not self._polling:
            self._polling = True
            self.after(_POLL_MS, self._poll)

    def _resume_scan(self) -> None:
        if self.app.scan_controller.is_running():
            messagebox.showinfo("Scan Running", "A scan is already running.", parent=self)
            return

        try:
            resumable = self.app.scan_run_repo.list_resumable(self.app.conn)
        except Exception as exc:
            messagebox.showerror("Error", f"Could not load interrupted runs:\n{exc}", parent=self)
            return

        if not resumable:
            messagebox.showinfo(
                "No Interrupted Scans",
                "There are no interrupted scans available to resume.\n\n"
                "An interrupted scan must have been left in 'running' status "
                "(e.g., the application crashed or was force-closed during a scan).",
                parent=self,
            )
            return

        ResumeScanDialog(self, resumable, self._do_resume_run)

    def _do_resume_run(self, run_id: int) -> None:
        self._total_files = self._total_bytes = self._total_violations = 0
        self._total_errors = self._total_dirs = 0
        self._sparkline._points.clear()
        self._update_stats_labels()
        self._clear_log()

        self.app.scan_controller.resume(run_id)

        self._btn_full.config(state="disabled")
        self._btn_incr.config(state="disabled")
        self._btn_resume.config(state="disabled")
        self._btn_cancel.config(state="normal")
        self._progress_bar.start(12)

        self._log_append(f"Resuming interrupted scan run #{run_id}…")

        if not self._polling:
            self._polling = True
            self.after(_POLL_MS, self._poll)

    def _cancel_scan(self) -> None:
        self.app.scan_controller.cancel()
        self._log_append("Cancel requested — stopping after current directory batch…")

    # ------------------------------------------------------------------
    # Progress polling (called from Tkinter main thread via root.after)
    # ------------------------------------------------------------------

    def _poll(self) -> None:
        events = self.app.scan_controller.drain_progress()
        finished = False
        for ev in events:
            self._apply_event(ev)
            if ev.finished:
                finished = True

        if finished or not self.app.scan_controller.is_running():
            # One final drain to catch anything queued after is_running went False
            if not finished:
                for ev in self.app.scan_controller.drain_progress():
                    self._apply_event(ev)
            self._progress_bar.stop()
            self._btn_full.config(state="normal")
            self._btn_incr.config(state="normal")
            self._btn_resume.config(state="normal")
            self._btn_cancel.config(state="disabled")
            self._polling = False
            return

        self.after(_POLL_MS, self._poll)

    def _apply_event(self, ev: ProgressEvent) -> None:
        self._total_files += ev.files_delta
        self._total_bytes += ev.bytes_delta
        self._total_violations += ev.violations_delta
        self._total_errors += ev.errors_delta
        self._total_dirs += ev.dirs_delta
        self._update_stats_labels()

        if ev.current_path:
            self._log_append(ev.current_path)
        if ev.status:
            self._log_append(f">>> {ev.status}")

    def _update_stats_labels(self) -> None:
        self._card_files.update_value(f"{self._total_files:,}")
        self._card_size.update_value(format_bytes(self._total_bytes))
        self._card_dirs.update_value(f"{self._total_dirs:,}")
        self._card_violations.update_value(f"{self._total_violations:,}")
        self._card_errors.update_value(f"{self._total_errors:,}")
        self._sparkline.append_point(float(self._total_files))

    # ------------------------------------------------------------------
    # Log helpers
    # ------------------------------------------------------------------

    def _log_append(self, msg: str) -> None:
        self._log.append(msg + "\n")

    def _clear_log(self) -> None:
        self._log.clear()

    # ------------------------------------------------------------------
    # Tab activation hook (called by MainWindow on tab switch)
    # ------------------------------------------------------------------

    def on_tab_activate(self) -> None:
        self._refresh_roots()
        self._sync_settings_from_app()
