"""Sections page — admin and secret_admin only."""
from __future__ import annotations

import tkinter as tk
import tkinter.messagebox as messagebox
import tkinter.ttk as ttk
from typing import TYPE_CHECKING

from shared_drive_manager.ui.theme import Theme

if TYPE_CHECKING:
    from shared_drive_manager.app import Application


class SectionsPage(ttk.Frame):
    def __init__(self, parent: tk.Widget, app: "Application") -> None:
        super().__init__(parent)
        self.app = app
        self._selected_id: int | None = None
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
        tk.Label(header, text="  SECTION MAP", bg=Theme.PANEL,
                 fg=Theme.TEXT, font=("Segoe UI Semibold", 11)).pack(side="left")

        tk.Frame(self, bg=Theme.BORDER, height=1).pack(fill="x", padx=20)

        # Hint text
        tk.Label(
            self,
            text=(
                "Map path prefixes to named sections. During a scan each file is assigned "
                "the section whose prefix is the longest match for its path."
            ),
            bg=Theme.BG, fg=Theme.DIM, font=("Segoe UI", 8),
        ).pack(anchor="w", padx=20, pady=(8, 0))

        # Two-pane layout: list on left, form on right
        body = tk.Frame(self, bg=Theme.BG)
        body.pack(fill="both", expand=True, padx=20, pady=12)

        self._build_list(body)
        self._build_form(body)

    def _build_list(self, parent: tk.Frame) -> None:
        left = tk.Frame(parent, bg=Theme.BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))

        tk.Label(left, text="DEFINED SECTIONS", bg=Theme.BG, fg=Theme.MUTED,
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(0, 4))

        tree_frame = tk.Frame(left, bg=Theme.BG)
        tree_frame.pack(fill="both", expand=True)

        cols = ("section_name", "path_prefix", "business_owner")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                  selectmode="browse")
        self._tree.heading("section_name",    text="Section Name")
        self._tree.heading("path_prefix",     text="Path Prefix")
        self._tree.heading("business_owner",  text="Section Owner")

        self._tree.column("section_name",   width=160, minwidth=100)
        self._tree.column("path_prefix",    width=280, minwidth=160)
        self._tree.column("business_owner", width=160, minwidth=80)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree.pack(fill="both", expand=True)
        self._tree.tag_configure("empty", foreground=Theme.MUTED)
        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        # Buttons below list
        btn_row = tk.Frame(left, bg=Theme.BG)
        btn_row.pack(fill="x", pady=(8, 0))

        tk.Button(
            btn_row, text="+ New Section",
            bg=Theme.CYAN, fg=Theme.BG, font=("Segoe UI Semibold", 9),
            relief="flat", padx=12, pady=4, cursor="hand2",
            activebackground=Theme.BLUE, activeforeground=Theme.TEXT,
            command=self._clear_form,
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            btn_row, text="Remove Selected",
            bg=Theme.PANEL_2, fg=Theme.AMBER, font=("Segoe UI", 9),
            relief="flat", padx=12, pady=4, cursor="hand2",
            activebackground=Theme.PANEL_3, activeforeground=Theme.TEXT,
            command=self._remove_selected,
        ).pack(side="left")

    def _build_form(self, parent: tk.Frame) -> None:
        right = tk.Frame(parent, bg=Theme.PANEL_2, padx=20, pady=16)
        right.pack(side="left", fill="y", ipadx=4)

        tk.Label(right, text="SECTION DETAILS", bg=Theme.PANEL_2, fg=Theme.MUTED,
                 font=("Segoe UI", 8)).grid(row=0, column=0, columnspan=2,
                                            sticky="w", pady=(0, 10))

        def lbl(row: int, text: str) -> None:
            tk.Label(right, text=text, bg=Theme.PANEL_2, fg=Theme.MUTED,
                     font=("Segoe UI", 9)).grid(row=row, column=0, sticky="w",
                                                pady=(0, 6), padx=(0, 12))

        def entry_var(row: int) -> tuple[tk.Entry, tk.StringVar]:
            var = tk.StringVar()
            e = tk.Entry(right, textvariable=var,
                         bg=Theme.ENTRY_BG, fg=Theme.TEXT,
                         insertbackground=Theme.TEXT, relief="flat",
                         font=("Segoe UI", 9), width=30)
            e.grid(row=row, column=1, sticky="ew", pady=(0, 6))
            return e, var

        lbl(1, "Section Name:")
        _, self._name_var = entry_var(1)

        lbl(2, "Path Prefix:")
        _, self._prefix_var = entry_var(2)

        lbl(3, "Section Owner:")
        _, self._owner_var = entry_var(3)

        lbl(4, "Notes:")
        self._notes_var = tk.StringVar()
        notes_entry = tk.Text(right, bg=Theme.ENTRY_BG, fg=Theme.TEXT,
                              insertbackground=Theme.TEXT, relief="flat",
                              font=("Segoe UI", 9), width=30, height=4,
                              wrap="word")
        notes_entry.grid(row=4, column=1, sticky="ew", pady=(0, 6))
        self._notes_widget = notes_entry

        self._status_var = tk.StringVar()
        tk.Label(right, textvariable=self._status_var, bg=Theme.PANEL_2,
                 fg=Theme.RED, font=("Segoe UI", 9), wraplength=240).grid(
            row=5, column=0, columnspan=2, pady=(4, 0), sticky="w")

        tk.Button(
            right, text="Save",
            bg=Theme.CYAN, fg=Theme.BG, font=("Segoe UI Semibold", 9),
            relief="flat", padx=14, pady=5, cursor="hand2",
            activebackground=Theme.BLUE, activeforeground=Theme.TEXT,
            command=self._save,
        ).grid(row=6, column=0, columnspan=2, pady=(12, 0), sticky="w")

        right.columnconfigure(1, weight=1)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _load(self) -> None:
        self._tree.delete(*self._tree.get_children())
        conn = self.app.get_db()
        rows = self.app.section_repo.list_active(conn)
        for row in rows:
            self._tree.insert("", "end",
                              iid=str(row["section_id"]),
                              values=(
                                  row["section_name"],
                                  row["path_prefix"],
                                  row.get("business_owner") or "",
                              ))
        if not rows:
            self._tree.insert("", "end",
                              values=("(no sections defined)", "", ""),
                              tags=("empty",))

    def on_tab_activate(self) -> None:
        self._selected_id = None
        self._clear_form()
        self._load()

    # ------------------------------------------------------------------
    # Interactions
    # ------------------------------------------------------------------

    def _on_select(self, _event=None) -> None:
        sel = self._tree.selection()
        if not sel:
            return
        iid = sel[0]
        # empty-state row has no integer iid
        try:
            section_id = int(iid)
        except ValueError:
            return

        self._selected_id = section_id
        vals = self._tree.item(iid, "values")
        self._name_var.set(vals[0])
        self._prefix_var.set(vals[1])
        self._owner_var.set(vals[2])

        # load notes from db
        conn = self.app.get_db()
        rows = conn.execute(
            "SELECT notes FROM section_map WHERE section_id = ?", (section_id,)
        ).fetchone()
        self._notes_widget.delete("1.0", "end")
        if rows and rows[0]:
            self._notes_widget.insert("1.0", rows[0])
        self._status_var.set("")

    def _clear_form(self) -> None:
        self._selected_id = None
        self._name_var.set("")
        self._prefix_var.set("")
        self._owner_var.set("")
        self._notes_widget.delete("1.0", "end")
        self._status_var.set("")
        self._tree.selection_remove(*self._tree.selection())

    def _save(self) -> None:
        name   = self._name_var.get().strip()
        prefix = self._prefix_var.get().strip()
        owner  = self._owner_var.get().strip() or None
        notes  = self._notes_widget.get("1.0", "end").strip() or None

        if not name:
            self._status_var.set("Section name is required.")
            return
        if not prefix:
            self._status_var.set("Path prefix is required.")
            return

        conn = self.app.get_db()
        try:
            if self._selected_id is None:
                self.app.section_repo.create(conn, name, prefix, owner, notes)
            else:
                self.app.section_repo.update(
                    conn, self._selected_id, name, prefix, owner, notes
                )
        except Exception as exc:
            self._status_var.set(f"Error: {exc}")
            return

        self._clear_form()
        self._load()

    def _remove_selected(self) -> None:
        sel = self._tree.selection()
        if not sel:
            self._status_var.set("Select a section to remove.")
            return
        try:
            section_id = int(sel[0])
        except ValueError:
            return

        name = self._tree.item(sel[0], "values")[0]
        if not messagebox.askyesno(
            "Remove Section",
            f"Remove section '{name}'?\n\nExisting file records will keep their "
            "section label until the next scan.",
            parent=self,
        ):
            return

        conn = self.app.get_db()
        try:
            self.app.section_repo.delete(conn, section_id)
        except Exception as exc:
            self._status_var.set(f"Error: {exc}")
            return

        self._clear_form()
        self._load()
