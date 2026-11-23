"""Login gate — shown before the main window is constructed."""
from __future__ import annotations

import sys
import tkinter as tk
import tkinter.ttk as ttk
from typing import TYPE_CHECKING

from shared_drive_manager.core.auth import verify_password
from shared_drive_manager.ui.theme import Theme

if TYPE_CHECKING:
    from shared_drive_manager.app import Application

_VISIBLE_ROLES = ["Basic Viewer", "Administrator"]
_SECRET_ROLE   = "SECRET ACCESS"

_CLICK_WINDOW_MS = 500    # ms to complete triple-click (tight window reduces accidental activation)
_CLICK_RESET_MS  = 5000   # ms before counter resets after last click

_MAX_FAILED_ATTEMPTS = 5  # attempts before temporary lockout
_LOCKOUT_SECONDS     = 30 # seconds to lock login after too many failures


class LoginWindow:
    def __init__(self, root: tk.Tk, app: "Application") -> None:
        self.app = app
        self._click_count = 0
        self._click_reset_id: str | None = None
        self._secret_revealed = False
        self._failed_attempts = 0
        self._lockout_until = 0.0

        self.dialog = tk.Toplevel(root)
        self._build(root)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self, root: tk.Tk) -> None:
        dlg = self.dialog
        dlg.title("Shared Drive Policy Manager")
        dlg.configure(bg=Theme.BG)
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.protocol("WM_DELETE_WINDOW", lambda: sys.exit(0))

        # Center on screen
        dlg.update_idletasks()
        w, h = 420, 320
        sw = dlg.winfo_screenwidth()
        sh = dlg.winfo_screenheight()
        dlg.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        # ── Title block ──────────────────────────────────────────────
        title_frame = tk.Frame(dlg, bg=Theme.SIDEBAR, pady=20)
        title_frame.pack(fill="x")

        self._title_lbl = tk.Label(
            title_frame, text="SHARED DRIVE", bg=Theme.SIDEBAR,
            fg=Theme.CYAN, font=("Segoe UI Semibold", 14),
        )
        self._title_lbl.pack()
        tk.Label(
            title_frame, text="POLICY MANAGER", bg=Theme.SIDEBAR,
            fg=Theme.MUTED, font=("Segoe UI", 9),
        ).pack()

        # Triple-click on title activates hidden mode
        self._title_lbl.bind("<Button-1>", self._on_title_click)

        # ── Form ─────────────────────────────────────────────────────
        form = tk.Frame(dlg, bg=Theme.BG, padx=40, pady=24)
        form.pack(fill="both", expand=True)

        # Account type
        tk.Label(form, text="Account Type:", bg=Theme.BG,
                 fg=Theme.MUTED, font=("Segoe UI", 9)).grid(
            row=0, column=0, sticky="w", pady=(0, 6))

        self._role_var = tk.StringVar(value=_VISIBLE_ROLES[0])
        self._role_combo = ttk.Combobox(
            form, textvariable=self._role_var,
            values=_VISIBLE_ROLES, state="readonly", width=22,
        )
        self._role_combo.grid(row=0, column=1, sticky="ew", pady=(0, 6))
        self._role_combo.bind("<<ComboboxSelected>>", self._on_role_change)

        # Username (hidden until secret mode)
        self._username_label = tk.Label(
            form, text="Username:", bg=Theme.BG,
            fg=Theme.MUTED, font=("Segoe UI", 9),
        )
        self._username_var = tk.StringVar()
        self._username_entry = tk.Entry(
            form, textvariable=self._username_var,
            bg=Theme.ENTRY_BG, fg=Theme.TEXT, insertbackground=Theme.TEXT,
            relief="flat", font=("Segoe UI", 9), width=25,
        )

        # Password
        self._pw_label = tk.Label(
            form, text="Password:", bg=Theme.BG,
            fg=Theme.MUTED, font=("Segoe UI", 9),
        )
        self._pw_var = tk.StringVar()
        self._pw_entry = tk.Entry(
            form, textvariable=self._pw_var, show="*",
            bg=Theme.ENTRY_BG, fg=Theme.TEXT, insertbackground=Theme.TEXT,
            relief="flat", font=("Segoe UI", 9), width=25,
        )
        self._pw_label.grid(row=1, column=0, sticky="w", pady=(0, 6))
        self._pw_entry.grid(row=1, column=1, sticky="ew", pady=(0, 6))

        # Initially hide password for Viewer
        self._pw_label.grid_remove()
        self._pw_entry.grid_remove()

        # Login button
        self._login_btn = tk.Button(
            form, text="LOGIN", bg=Theme.CYAN, fg=Theme.BG,
            font=("Segoe UI Semibold", 10), relief="flat",
            padx=24, pady=6, cursor="hand2",
            activebackground=Theme.BLUE, activeforeground=Theme.TEXT,
            command=self._attempt_login,
        )
        self._login_btn.grid(row=3, column=0, columnspan=2, pady=(12, 4))

        # Status label — row tracks login_btn row + 1
        self._status_var = tk.StringVar()
        self._status_label = tk.Label(
            form, textvariable=self._status_var,
            bg=Theme.BG, fg=Theme.RED, font=("Segoe UI", 9),
        )
        self._status_label.grid(row=4, column=0, columnspan=2)

        form.columnconfigure(1, weight=1)

        # Bind Enter key
        dlg.bind("<Return>", lambda e: self._attempt_login())

    # ------------------------------------------------------------------
    # Hidden mode — triple-click title
    # ------------------------------------------------------------------

    def _on_title_click(self, _event: tk.Event) -> None:
        self._click_count += 1

        if self._click_reset_id:
            self.dialog.after_cancel(self._click_reset_id)
        self._click_reset_id = self.dialog.after(_CLICK_RESET_MS, self._reset_clicks)

        if self._click_count >= 3 and not self._secret_revealed:
            self._reveal_secret_mode()

    def _reset_clicks(self) -> None:
        self._click_count = 0
        self._click_reset_id = None

    def _reveal_secret_mode(self) -> None:
        self._secret_revealed = True
        new_values = _VISIBLE_ROLES + [_SECRET_ROLE]
        self._role_combo.configure(values=new_values)

        # Show username field above password
        self._username_label.grid(row=1, column=0, sticky="w", pady=(0, 6))
        self._username_entry.grid(row=1, column=1, sticky="ew", pady=(0, 6))

        # Push password down one row
        self._pw_label.grid(row=2, column=0, sticky="w", pady=(0, 6))
        self._pw_entry.grid(row=2, column=1, sticky="ew", pady=(0, 6))

        # Move login button and status label down to make room
        self._login_btn.grid(row=4, column=0, columnspan=2, pady=(12, 4))
        self._status_label.grid(row=5, column=0, columnspan=2)

        # Select secret role automatically
        self._role_var.set(_SECRET_ROLE)
        self._on_role_change(None)

    # ------------------------------------------------------------------
    # Role combobox change
    # ------------------------------------------------------------------

    def _on_role_change(self, _event) -> None:
        role = self._role_var.get()
        if role == "Basic Viewer":
            self._pw_label.grid_remove()
            self._pw_entry.grid_remove()
        elif role == "Administrator":
            self._pw_label.grid()
            self._pw_entry.grid()
        else:  # SECRET ACCESS
            self._pw_label.grid()
            self._pw_entry.grid()

    # ------------------------------------------------------------------
    # Auth logic
    # ------------------------------------------------------------------

    def _attempt_login(self) -> None:
        import time
        if time.time() < self._lockout_until:
            remaining = int(self._lockout_until - time.time()) + 1
            self._status_var.set(f"TOO MANY ATTEMPTS — WAIT {remaining}s")
            return

        role_choice = self._role_var.get()
        conn = self.app.get_db()
        user_repo = self.app.user_repo

        if role_choice == "Basic Viewer":
            user = user_repo.get_by_username(conn, "viewer")
            if user:
                self.app.authenticated_user = user
                self.dialog.destroy()
                return
            self._set_error("INVALID CREDENTIALS")

        elif role_choice == "Administrator":
            password = self._pw_var.get()
            user = user_repo.get_by_username(conn, "admin")
            if user and verify_password(password, user["password_hash"], user["salt"]):
                self.app.authenticated_user = user
                self.dialog.destroy()
                return
            self._set_error("INVALID CREDENTIALS")

        else:  # SECRET ACCESS
            username = self._username_var.get().strip()
            password = self._pw_var.get()
            user = user_repo.get_by_username(conn, username)
            if (
                user
                and user["role"] == "secret_admin"
                and verify_password(password, user["password_hash"], user["salt"])
            ):
                self.app.authenticated_user = user
                self.dialog.destroy()
                return
            self._set_error("INVALID CREDENTIALS")

    def _set_error(self, message: str) -> None:
        import time
        self._failed_attempts += 1
        if self._failed_attempts >= _MAX_FAILED_ATTEMPTS:
            self._lockout_until = time.time() + _LOCKOUT_SECONDS
            self._failed_attempts = 0
            self._status_var.set(f"TOO MANY ATTEMPTS — LOCKED FOR {_LOCKOUT_SECONDS}s")
        else:
            self._status_var.set(message)
        self._pw_var.set("")
