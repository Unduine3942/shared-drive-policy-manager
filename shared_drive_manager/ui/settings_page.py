"""Settings page — persists all application settings to app_settings table."""
from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING

log = logging.getLogger(__name__)

from shared_drive_manager import config
from shared_drive_manager.core.owner_resolver import is_available as _owner_available
from shared_drive_manager.logging_config import setup_logging
from shared_drive_manager.ui.theme import Theme
from shared_drive_manager.ui.widgets import (
    LabeledCheckbutton,
    LabeledEntry,
    LabeledSpinbox,
    panel,
)

if TYPE_CHECKING:
    from shared_drive_manager.app import Application

_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]
_WIN32_AVAILABLE = _owner_available()
_WIN32_STATUS = (
    "win32security: available"
    if _WIN32_AVAILABLE
    else "win32security: NOT available — owner will be blank"
)
_WIN32_COLOR = Theme.GREEN if _WIN32_AVAILABLE else Theme.RED


class SettingsPage(ttk.Frame):
    def __init__(self, parent: tk.Widget, app: "Application") -> None:
        super().__init__(parent)
        self.app = app
        self._build()
        self._load()

    def _build(self) -> None:
        canvas = tk.Canvas(self, highlightthickness=0, bg=Theme.BG)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=Theme.BG)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_resize(event):
            canvas.itemconfig(win, width=event.width)

        inner.bind("<Configure>", _on_configure)
        canvas.bind("<Configure>", _on_resize)

        # --- Database ---
        db_outer, db_body = panel(inner, "DATABASE")
        db_outer.pack(fill="x", padx=Theme.PAD_LG, pady=(Theme.PAD_LG, Theme.PAD_MD))
        db_row = tk.Frame(db_body, bg=Theme.PANEL)
        db_row.pack(anchor="w", fill="x", padx=Theme.PAD_LG, pady=Theme.PAD_MD)
        tk.Label(db_row, text="DB File Path:", width=22, anchor="w",
                 bg=Theme.PANEL, fg=Theme.MUTED, font=Theme.FONT_BODY).pack(side="left")
        self._db_path_var = tk.StringVar()
        ttk.Entry(db_row, textvariable=self._db_path_var, width=52).pack(side="left", padx=(0, 4))
        ttk.Button(db_row, text="Browse…", command=self._browse_db).pack(side="left")

        # --- Exports ---
        exp_outer, exp_body = panel(inner, "EXPORTS")
        exp_outer.pack(fill="x", padx=Theme.PAD_LG, pady=(0, Theme.PAD_MD))
        exp_row = tk.Frame(exp_body, bg=Theme.PANEL)
        exp_row.pack(anchor="w", fill="x", padx=Theme.PAD_LG, pady=Theme.PAD_MD)
        tk.Label(exp_row, text="Default Export Folder:", width=22, anchor="w",
                 bg=Theme.PANEL, fg=Theme.MUTED, font=Theme.FONT_BODY).pack(side="left")
        self._export_var = tk.StringVar()
        ttk.Entry(exp_row, textvariable=self._export_var, width=52).pack(side="left", padx=(0, 4))
        ttk.Button(exp_row, text="Browse…", command=self._browse_export).pack(side="left")

        # --- Scanner ---
        sc_outer, sc_body = panel(inner, "SCANNER")
        sc_outer.pack(fill="x", padx=Theme.PAD_LG, pady=(0, Theme.PAD_MD))
        sc_inner = tk.Frame(sc_body, bg=Theme.PANEL)
        sc_inner.pack(anchor="w", fill="x", padx=Theme.PAD_LG, pady=Theme.PAD_MD)
        self._workers = LabeledSpinbox(sc_inner, "Max Workers:", from_=1, to=16)
        self._workers.pack(anchor="w", pady=2)
        self._batch_size = LabeledSpinbox(sc_inner, "Batch Size:", from_=100, to=5000)
        self._batch_size.pack(anchor="w", pady=2)
        self._long_path = LabeledSpinbox(sc_inner, "Long Path Threshold:", from_=50, to=32767)
        self._long_path.pack(anchor="w", pady=2)
        self._max_errors = LabeledSpinbox(sc_inner, "Max Errors (0 = unlimited):", from_=0, to=100000)
        self._max_errors.pack(anchor="w", pady=2)
        owner_row = tk.Frame(sc_inner, bg=Theme.PANEL)
        owner_row.pack(anchor="w", pady=2)
        self._collect_owner = LabeledCheckbutton(owner_row, "Collect owner / creator proxy")
        self._collect_owner.pack(side="left")
        tk.Label(owner_row, text=f"  ({_WIN32_STATUS})", fg=_WIN32_COLOR,
                 bg=Theme.PANEL, font=Theme.FONT_CAPTION).pack(side="left")
        self._collect_acl = LabeledCheckbutton(sc_inner, "Collect ACL info  (disabled in MVP)")
        self._collect_acl.pack(anchor="w", pady=2)
        self._collect_acl.configure_state("disabled")
        self._collect_doc_props = LabeledCheckbutton(
            sc_inner, "Read embedded doc properties (creator/modifier from .docx/.xlsx/.pptx)"
        )
        self._collect_doc_props.pack(anchor="w", pady=2)

        # --- Logging ---
        log_outer, log_body = panel(inner, "LOGGING")
        log_outer.pack(fill="x", padx=Theme.PAD_LG, pady=(0, Theme.PAD_MD))
        log_row = tk.Frame(log_body, bg=Theme.PANEL)
        log_row.pack(anchor="w", padx=Theme.PAD_LG, pady=Theme.PAD_MD)
        tk.Label(log_row, text="Log Level:", width=22, anchor="w",
                 bg=Theme.PANEL, fg=Theme.MUTED, font=Theme.FONT_BODY).pack(side="left")
        self._log_level_var = tk.StringVar()
        ttk.Combobox(
            log_row, textvariable=self._log_level_var,
            values=_LOG_LEVELS, state="readonly", width=10,
        ).pack(side="left")

        # --- Maintenance ---
        maint_outer, maint_body = panel(inner, "MAINTENANCE")
        maint_outer.pack(fill="x", padx=Theme.PAD_LG, pady=(0, Theme.PAD_MD))
        maint_inner = tk.Frame(maint_body, bg=Theme.PANEL)
        maint_inner.pack(anchor="w", padx=Theme.PAD_LG, pady=Theme.PAD_MD)
        ttk.Button(maint_inner, text="Vacuum Database", command=self._vacuum).pack(anchor="w")

        # --- Save ---
        save_frame = tk.Frame(inner, bg=Theme.BG)
        save_frame.pack(fill="x", padx=Theme.PAD_LG, pady=(0, Theme.PAD_LG))
        ttk.Button(
            save_frame, text="Save Settings",
            command=self._save, style="Accent.TButton",
        ).pack(anchor="w")

    def _load(self) -> None:
        s = self.app.settings
        self._db_path_var.set(s.get("db_path", str(config.DB_DEFAULT_PATH)))
        self._export_var.set(s.get("export_folder", config.DEFAULT_EXPORT_FOLDER))
        self._workers.set(s.get("max_workers", config.DEFAULT_WORKERS))
        self._batch_size.set(s.get("batch_size", config.DEFAULT_BATCH_SIZE))
        self._long_path.set(s.get("long_path_threshold", config.LONG_PATH_THRESHOLD))
        self._max_errors.set(s.get("max_error_threshold", config.MAX_ERROR_THRESHOLD))
        self._collect_owner.set(s.get("collect_owner", config.DEFAULT_COLLECT_OWNER))
        self._collect_doc_props.set(s.get("collect_doc_props", True))
        self._log_level_var.set(s.get("log_level", config.DEFAULT_LOG_LEVEL))

    def _browse_db(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Choose database file location",
            defaultextension=".sqlite3",
            filetypes=[("SQLite database", "*.sqlite3"), ("All files", "*.*")],
            initialfile="shared_drive_manager.sqlite3",
        )
        if path:
            self._db_path_var.set(path)

    def _browse_export(self) -> None:
        path = filedialog.askdirectory(title="Choose default export folder")
        if path:
            self._export_var.set(path)

    def _save(self) -> None:
        repo = self.app.settings_repo
        conn = self.app.conn

        new_db_path = self._db_path_var.get().strip()
        old_db_path = self.app.settings.get("db_path", str(config.DB_DEFAULT_PATH))

        updates = {
            "db_path": new_db_path,
            "export_folder": self._export_var.get().strip(),
            "max_workers": self._workers.get(),
            "batch_size": self._batch_size.get(),
            "long_path_threshold": self._long_path.get(),
            "max_error_threshold": self._max_errors.get(),
            "collect_owner": self._collect_owner.get(),
            "collect_doc_props": self._collect_doc_props.get(),
            "collect_acl": False,
            "log_level": self._log_level_var.get(),
        }

        for key, value in updates.items():
            repo.set(conn, key, value)

        self.app.settings.update(updates)

        new_level = updates["log_level"]
        setup_logging(config.LOG_DIR, new_level)

        if new_db_path != old_db_path:
            # db_path is a bootstrapping setting: _boot() always reads it from the
            # default DB first, so if the active DB is an override we must also
            # write the new path there so the next restart picks it up.
            default_path = Path(config.DB_DEFAULT_PATH)
            if self.app.db_path.resolve() != default_path.resolve():
                try:
                    from shared_drive_manager.db.connection import open_connection as _oc
                    _dc = _oc(default_path)
                    try:
                        repo.set(_dc, "db_path", new_db_path)
                    finally:
                        _dc.close()
                except Exception as exc:
                    log.warning("Could not write db_path to default DB: %s", exc)
            messagebox.showinfo(
                "Restart Required",
                "The database path has changed. Please restart the application "
                "for the new path to take effect.",
            )

        messagebox.showinfo("Settings Saved", "Settings have been saved successfully.")

    def _vacuum(self) -> None:
        try:
            self.app.conn.execute("VACUUM")
            self.app.conn.execute("ANALYZE")
            messagebox.showinfo("Maintenance", "Database VACUUM and ANALYZE completed.")
        except Exception as exc:
            messagebox.showerror("Error", f"Maintenance failed:\n{exc}")
