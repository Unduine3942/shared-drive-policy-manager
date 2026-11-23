"""Hidden Files page — secret_admin only."""
from __future__ import annotations

import tkinter as tk
import tkinter.messagebox as messagebox
import tkinter.ttk as ttk
from typing import TYPE_CHECKING

from shared_drive_manager.core.hidden_files import get_patterns, save_patterns
from shared_drive_manager.ui.theme import Theme

if TYPE_CHECKING:
    from shared_drive_manager.app import Application


class HiddenFilesPage(ttk.Frame):
    def __init__(self, parent: tk.Widget, app: "Application") -> None:
        super().__init__(parent)
        self.app = app
        self._build()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self) -> None:
        # Header
        header = tk.Frame(self, bg=Theme.PANEL)
        header.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(header, text="● ● ●", bg=Theme.PANEL,
                 fg=Theme.MUTED, font=("Consolas", 9)).pack(side="left")
        tk.Label(header, text="  HIDDEN FILES", bg=Theme.PANEL,
                 fg=Theme.TEXT, font=("Segoe UI Semibold", 11)).pack(side="left")

        tk.Frame(self, bg=Theme.BORDER, height=1).pack(fill="x", padx=20)

        # Add-pattern row
        add_frame = tk.Frame(self, bg=Theme.BG)
        add_frame.pack(fill="x", padx=20, pady=(12, 6))

        tk.Label(add_frame, text="Pattern:", bg=Theme.BG,
                 fg=Theme.MUTED, font=("Segoe UI", 9)).pack(side="left", padx=(0, 8))

        self._pattern_var = tk.StringVar()
        entry = tk.Entry(
            add_frame, textvariable=self._pattern_var,
            bg=Theme.ENTRY_BG, fg=Theme.TEXT, insertbackground=Theme.TEXT,
            relief="flat", font=("Segoe UI", 9), width=52,
        )
        entry.pack(side="left", padx=(0, 8))
        entry.bind("<Return>", lambda e: self._add_pattern())

        tk.Button(
            add_frame, text="+ Add",
            bg=Theme.CYAN, fg=Theme.BG, font=("Segoe UI Semibold", 9),
            relief="flat", padx=10, pady=3, cursor="hand2",
            activebackground=Theme.BLUE, activeforeground=Theme.TEXT,
            command=self._add_pattern,
        ).pack(side="left")

        # Status label
        self._status_var = tk.StringVar()
        tk.Label(self, textvariable=self._status_var, bg=Theme.BG,
                 fg=Theme.RED, font=("Segoe UI", 9)).pack(anchor="w", padx=20)

        # Treeview
        tree_frame = tk.Frame(self, bg=Theme.BG)
        tree_frame.pack(fill="both", expand=True, padx=20, pady=(4, 0))

        self._tree = ttk.Treeview(tree_frame, columns=("pattern",),
                                  show="headings", selectmode="browse")
        self._tree.heading("pattern", text="Hidden Pattern")
        self._tree.column("pattern", width=600, minwidth=200)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                            command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree.pack(fill="both", expand=True)
        self._tree.tag_configure("empty", foreground=Theme.MUTED)

        # Remove button + hint
        bottom = tk.Frame(self, bg=Theme.BG)
        bottom.pack(fill="x", padx=20, pady=(8, 12))

        tk.Button(
            bottom, text="Remove Selected",
            bg=Theme.PANEL_2, fg=Theme.AMBER, font=("Segoe UI", 9),
            relief="flat", padx=12, pady=4, cursor="hand2",
            activebackground=Theme.PANEL_3, activeforeground=Theme.TEXT,
            command=self._remove_selected,
        ).pack(side="left", padx=(0, 16))

        tk.Label(
            bottom,
            text="Patterns use fnmatch glob syntax — matched against full path and filename.",
            bg=Theme.BG, fg=Theme.DIM, font=("Segoe UI", 8),
        ).pack(side="left")

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _load(self) -> None:
        self._tree.delete(*self._tree.get_children())
        patterns = get_patterns()
        for pat in patterns:
            self._tree.insert("", "end", values=(pat,))
        if not patterns:
            self._tree.insert("", "end", values=("(no patterns defined)",), tags=("empty",))

    def on_tab_activate(self) -> None:
        self._load()
        self._status_var.set("")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _add_pattern(self) -> None:
        pat = self._pattern_var.get().strip()
        if not pat:
            self._status_var.set("Enter a pattern first.")
            return

        current = get_patterns()
        if pat in current:
            self._status_var.set("Pattern already in the list.")
            return

        try:
            save_patterns(current + [pat])
        except Exception as exc:
            self._status_var.set(f"Save failed: {exc}")
            return

        self._pattern_var.set("")
        self._status_var.set("")
        self._load()

    def _remove_selected(self) -> None:
        sel = self._tree.selection()
        if not sel:
            self._status_var.set("Select a pattern to remove.")
            return

        pat = self._tree.item(sel[0], "values")[0]
        current = get_patterns()
        updated = [p for p in current if p != pat]

        try:
            save_patterns(updated)
        except Exception as exc:
            self._status_var.set(f"Save failed: {exc}")
            return

        self._status_var.set("")
        self._load()
