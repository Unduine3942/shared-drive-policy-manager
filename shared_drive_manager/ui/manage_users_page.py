"""Manage Users page — secret_admin only."""
from __future__ import annotations

import tkinter as tk
import tkinter.messagebox as messagebox
import tkinter.ttk as ttk
from typing import TYPE_CHECKING

from shared_drive_manager.core.auth import generate_salt, hash_password
from shared_drive_manager.ui.theme import Theme

if TYPE_CHECKING:
    from shared_drive_manager.app import Application

_REDACTED = "████████"   # display mask for the secret admin username


def _mask_creator(username: str | None) -> str:
    if username == "BigBrother":
        return _REDACTED
    return username or ""


class ManageUsersPage(ttk.Frame):
    def __init__(self, parent: tk.Widget, app: "Application") -> None:
        super().__init__(parent)
        self.app = app
        if not app.authenticated_user or app.authenticated_user.get("role") != "secret_admin":
            raise PermissionError("ManageUsersPage requires secret_admin role")
        self._build()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self) -> None:
        # Header row
        header = tk.Frame(self, bg=Theme.PANEL)
        header.pack(fill="x", padx=20, pady=(16, 8))

        tk.Label(header, text="● ● ●", bg=Theme.PANEL,
                 fg=Theme.MUTED, font=("Consolas", 9)).pack(side="left")
        tk.Label(header, text="  MANAGE USERS", bg=Theme.PANEL,
                 fg=Theme.TEXT, font=("Segoe UI Semibold", 11)).pack(side="left")

        tk.Button(
            header, text="+ Add Admin Account",
            bg=Theme.CYAN, fg=Theme.BG,
            font=("Segoe UI Semibold", 9), relief="flat",
            padx=12, pady=4, cursor="hand2",
            activebackground=Theme.BLUE, activeforeground=Theme.TEXT,
            command=self._open_add_dialog,
        ).pack(side="right")

        # Divider
        tk.Frame(self, bg=Theme.BORDER, height=1).pack(fill="x", padx=20)

        # Treeview
        tree_frame = tk.Frame(self, bg=Theme.BG)
        tree_frame.pack(fill="both", expand=True, padx=20, pady=12)

        cols = ("username", "role", "created_by", "created_at_utc")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                  selectmode="browse")
        self._tree.heading("username",       text="Username")
        self._tree.heading("role",           text="Role")
        self._tree.heading("created_by",     text="Created By")
        self._tree.heading("created_at_utc", text="Created At (UTC)")

        self._tree.column("username",       width=200, minwidth=120)
        self._tree.column("role",           width=120, minwidth=80)
        self._tree.column("created_by",     width=160, minwidth=100)
        self._tree.column("created_at_utc", width=200, minwidth=140)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                            command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree.pack(fill="both", expand=True)
        self._tree.tag_configure("empty", foreground=Theme.MUTED)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _load_users(self) -> None:
        self._tree.delete(*self._tree.get_children())
        conn = self.app.get_db()
        rows = self.app.user_repo.list_non_secret(conn)
        for row in rows:
            self._tree.insert("", "end", values=(
                row["username"],
                row["role"],
                _mask_creator(row.get("created_by")),
                row.get("created_at_utc", ""),
            ))
        if not rows:
            self._tree.insert("", "end", values=("(no users)", "", "", ""), tags=("empty",))

    def on_tab_activate(self) -> None:
        self._load_users()

    # ------------------------------------------------------------------
    # Add admin dialog
    # ------------------------------------------------------------------

    def _open_add_dialog(self) -> None:
        AddAdminDialog(self, self.app, on_success=self._load_users)


class AddAdminDialog:
    def __init__(
        self,
        parent: ManageUsersPage,
        app: "Application",
        on_success,
    ) -> None:
        self.app = app
        self.on_success = on_success

        dlg = tk.Toplevel(parent)
        self.dlg = dlg
        dlg.title("Add Admin Account")
        dlg.configure(bg=Theme.BG)
        dlg.resizable(False, False)
        dlg.grab_set()

        w, h = 360, 260
        dlg.update_idletasks()
        sw = dlg.winfo_screenwidth()
        sh = dlg.winfo_screenheight()
        dlg.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        self._build(dlg)

    def _build(self, dlg: tk.Toplevel) -> None:
        form = tk.Frame(dlg, bg=Theme.BG, padx=32, pady=24)
        form.pack(fill="both", expand=True)

        def lbl(row: int, text: str) -> None:
            tk.Label(form, text=text, bg=Theme.BG, fg=Theme.MUTED,
                     font=("Segoe UI", 9)).grid(
                row=row, column=0, sticky="w", pady=(0, 6))

        def entry(row: int, show: str = "") -> tk.Entry:
            var = tk.StringVar()
            e = tk.Entry(form, textvariable=var, show=show,
                         bg=Theme.ENTRY_BG, fg=Theme.TEXT,
                         insertbackground=Theme.TEXT, relief="flat",
                         font=("Segoe UI", 9), width=24)
            e.grid(row=row, column=1, sticky="ew", pady=(0, 6))
            return e

        lbl(0, "Username:")
        self._username_entry = entry(0)
        self._username_var = self._username_entry.cget("textvariable")

        lbl(1, "Password:")
        self._pw_entry = entry(1, show="*")
        self._pw_var = self._pw_entry.cget("textvariable")

        lbl(2, "Confirm:")
        self._pw2_entry = entry(2, show="*")
        self._pw2_var = self._pw2_entry.cget("textvariable")

        self._status_var = tk.StringVar()
        tk.Label(form, textvariable=self._status_var, bg=Theme.BG,
                 fg=Theme.RED, font=("Segoe UI", 9)).grid(
            row=3, column=0, columnspan=2, pady=(4, 0))

        btn_frame = tk.Frame(form, bg=Theme.BG)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=(12, 0))

        tk.Button(
            btn_frame, text="Create Account",
            bg=Theme.CYAN, fg=Theme.BG, font=("Segoe UI Semibold", 9),
            relief="flat", padx=14, pady=5, cursor="hand2",
            activebackground=Theme.BLUE, activeforeground=Theme.TEXT,
            command=self._submit,
        ).pack(side="left", padx=4)

        tk.Button(
            btn_frame, text="Cancel",
            bg=Theme.PANEL_2, fg=Theme.MUTED, font=("Segoe UI", 9),
            relief="flat", padx=14, pady=5, cursor="hand2",
            command=self.dlg.destroy,
        ).pack(side="left", padx=4)

        form.columnconfigure(1, weight=1)
        dlg.bind("<Return>", lambda e: self._submit())

    def _submit(self) -> None:
        # Retrieve current values directly from the widgets
        username = self._username_entry.get().strip()
        password = self._pw_entry.get()
        confirm  = self._pw2_entry.get()

        if not username:
            self._status_var.set("Username is required.")
            return
        if len(password) < 8:
            self._status_var.set("Password must be at least 8 characters.")
            return
        if password != confirm:
            self._status_var.set("Passwords do not match.")
            return

        creator = self.app.authenticated_user["username"]
        salt    = generate_salt()
        pw_hash = hash_password(password, salt)
        conn    = self.app.get_db()

        try:
            self.app.user_repo.create_user(
                conn, username, pw_hash, salt, "admin", creator
            )
        except Exception as exc:
            self._status_var.set(f"Error: {exc}")
            return

        self.dlg.destroy()
        self.on_success()
