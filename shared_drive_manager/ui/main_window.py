"""Main application window — sidebar navigation with stacked page frames."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from shared_drive_manager import config
from shared_drive_manager.ui.dashboard_page import DashboardPage
from shared_drive_manager.ui.duplicate_page import DuplicatePage
from shared_drive_manager.ui.hidden_files_page import HiddenFilesPage
from shared_drive_manager.ui.manage_users_page import ManageUsersPage
from shared_drive_manager.ui.monitor_page import MonitorPage
from shared_drive_manager.ui.owner_accountability_page import OwnerAccountabilityPage
from shared_drive_manager.ui.policy_page import PolicyPage
from shared_drive_manager.ui.reports_page import ReportsPage
from shared_drive_manager.ui.results_page import ResultsPage
from shared_drive_manager.ui.scan_page import ScanPage
from shared_drive_manager.ui.scan_history_page import ScanHistoryPage
from shared_drive_manager.ui.sections_page import SectionsPage
from shared_drive_manager.ui.settings_page import SettingsPage
from shared_drive_manager.ui.theme import Theme
from shared_drive_manager.ui.widgets import StatusBar

if TYPE_CHECKING:
    from shared_drive_manager.app import Application

_NAV_ITEMS = [
    ("DASHBOARD",    "dashboard"),
    ("SCAN SETUP",   "scan"),
    ("POLICY RULES", "policy"),
    ("VIOLATIONS",   "results"),
    ("REPORTS",      "reports"),
    ("LIVE MONITOR", "monitor"),
    ("SCAN HISTORY", "scan_history"),
    ("SECTION MAP",  "sections"),
    ("DUPLICATES",   "duplicates"),
    ("OWNER INDEX",  "owner_index"),
    ("MANAGE USERS", "manage_users"),
    ("HIDDEN FILES", "hidden_files"),
]

# Settings is pinned at the bottom of the sidebar, not in the main nav list.
_SETTINGS_LABEL = "SETTINGS"
_SETTINGS_KEY   = "settings"

_ROLE_PAGES: dict[str, set[str]] = {
    "viewer":       {"dashboard", "results", "reports"},
    "admin":        {"dashboard", "scan", "policy", "results", "reports", "settings", "sections", "scan_history", "duplicates", "owner_index"},
    "secret_admin": {"dashboard", "scan", "policy", "results", "reports", "settings", "monitor", "sections", "scan_history", "manage_users", "hidden_files", "duplicates", "owner_index"},
}


class MainWindow:
    def __init__(self, root: tk.Tk, app: "Application") -> None:
        self.root = root
        self.app = app
        self._nav_labels: dict[str, tk.Label] = {}
        self._nav_text: dict[str, str] = {key: label for label, key in _NAV_ITEMS}
        self._nav_text[_SETTINGS_KEY] = _SETTINGS_LABEL
        self._pages: dict[str, ttk.Frame] = {}
        self._active_key: str = ""

        self._configure_root()
        self._build_layout()
        self._build_status_bar()
        self._bind_events()

        self._navigate("dashboard")

    def _configure_root(self) -> None:
        self.root.title(f"Shared Drive Policy Manager v{config.APP_VERSION}")
        self.root.geometry("1500x900")
        self.root.minsize(1250, 760)
        self.root.configure(bg=Theme.BG)
        try:
            self.root.state("zoomed")
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Layout construction
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        # Top-level: sidebar | content
        outer = tk.Frame(self.root, bg=Theme.BG)
        outer.pack(fill="both", expand=True)

        self._build_sidebar(outer)
        self._build_content(outer)

    def _build_sidebar(self, parent: tk.Frame) -> None:
        sidebar = tk.Frame(parent, bg=Theme.SIDEBAR, width=230)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # Logo / title block
        logo_frame = tk.Frame(sidebar, bg=Theme.SIDEBAR)
        logo_frame.pack(fill="x", pady=(18, 8))
        tk.Label(logo_frame, text="SHARED DRIVE", bg=Theme.SIDEBAR, fg=Theme.CYAN,
                 font=("Segoe UI Semibold", 11)).pack(anchor="w", padx=18)
        tk.Label(logo_frame, text=f"POLICY MANAGER  v{config.APP_VERSION}",
                 bg=Theme.SIDEBAR, fg=Theme.MUTED,
                 font=("Segoe UI", 8)).pack(anchor="w", padx=18)

        # Divider
        tk.Frame(sidebar, bg=Theme.BORDER, height=1).pack(fill="x", padx=12, pady=(4, 12))

        # Navigation items — only show pages allowed for this role
        nav_frame = tk.Frame(sidebar, bg=Theme.SIDEBAR)
        nav_frame.pack(fill="x")

        role = self.app.authenticated_user["role"] if self.app.authenticated_user else "viewer"
        allowed = _ROLE_PAGES.get(role, set())

        for label_text, key in _NAV_ITEMS:
            if key not in allowed:
                continue
            lbl = tk.Label(nav_frame, text=f"   {label_text}", bg=Theme.SIDEBAR,
                           fg=Theme.MUTED, font=("Segoe UI", 9), anchor="w",
                           pady=8, padx=6, cursor="hand2")
            lbl.pack(fill="x")
            lbl.bind("<Button-1>", lambda e, k=key: self._navigate(k))
            lbl.bind("<Enter>", lambda e, w=lbl, k=key: self._on_hover(w, k))
            lbl.bind("<Leave>", lambda e, w=lbl, k=key: self._on_leave(w, k))
            self._nav_labels[key] = lbl

        # Bottom posture indicator
        tk.Frame(sidebar, bg=Theme.BORDER, height=1).pack(fill="x", padx=12, pady=(12, 0), side="bottom")
        tk.Label(sidebar, text="● SYSTEM POSTURE: NORMAL", bg=Theme.SIDEBAR,
                 fg=Theme.GREEN, font=("Consolas", 8), anchor="w", padx=18, pady=8).pack(
            side="bottom", fill="x")

        # Pinned Settings item above posture indicator
        if _SETTINGS_KEY in allowed:
            tk.Frame(sidebar, bg=Theme.BORDER, height=1).pack(fill="x", padx=12, side="bottom")
            settings_lbl = tk.Label(
                sidebar, text=f"   {_SETTINGS_LABEL}",
                bg=Theme.SIDEBAR, fg=Theme.MUTED,
                font=("Segoe UI", 9), anchor="w",
                pady=8, padx=6, cursor="hand2",
            )
            settings_lbl.pack(side="bottom", fill="x")
            settings_lbl.bind("<Button-1>", lambda e: self._navigate(_SETTINGS_KEY))
            settings_lbl.bind("<Enter>", lambda e: self._on_hover(settings_lbl, _SETTINGS_KEY))
            settings_lbl.bind("<Leave>", lambda e: self._on_leave(settings_lbl, _SETTINGS_KEY))
            self._nav_labels[_SETTINGS_KEY] = settings_lbl

    def _build_content(self, parent: tk.Frame) -> None:
        content_wrapper = tk.Frame(parent, bg=Theme.BG)
        content_wrapper.pack(side="left", fill="both", expand=True)

        self._build_header(content_wrapper)

        # Content area — all pages stacked here
        content = tk.Frame(content_wrapper, bg=Theme.BG)
        content.pack(fill="both", expand=True, padx=0, pady=0)
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)
        self._content_frame = content

        # Instantiate pages allowed for this role
        role = self.app.authenticated_user["role"] if self.app.authenticated_user else "viewer"
        allowed = _ROLE_PAGES.get(role, set())

        self.dashboard = DashboardPage(content, self.app)
        self.scan      = ScanPage(content, self.app)
        self.policy    = PolicyPage(content, self.app)
        self.results   = ResultsPage(content, self.app)
        self.reports   = ReportsPage(content, self.app)
        self.settings  = SettingsPage(content, self.app)
        self.monitor   = MonitorPage(content, self.app)

        page_pairs = [
            ("dashboard", self.dashboard),
            ("scan",      self.scan),
            ("policy",    self.policy),
            ("results",   self.results),
            ("reports",   self.reports),
            ("settings",  self.settings),
            ("monitor",   self.monitor),
        ]

        if "scan_history" in allowed:
            self.scan_history = ScanHistoryPage(content, self.app)
            page_pairs.append(("scan_history", self.scan_history))

        if "sections" in allowed:
            self.sections = SectionsPage(content, self.app)
            page_pairs.append(("sections", self.sections))

        if "duplicates" in allowed:
            self.duplicates = DuplicatePage(content, self.app)
            page_pairs.append(("duplicates", self.duplicates))

        if "owner_index" in allowed:
            self.owner_index = OwnerAccountabilityPage(content, self.app)
            page_pairs.append(("owner_index", self.owner_index))

        if "manage_users" in allowed:
            self.manage_users = ManageUsersPage(content, self.app)
            page_pairs.append(("manage_users", self.manage_users))

        if "hidden_files" in allowed:
            self.hidden_files = HiddenFilesPage(content, self.app)
            page_pairs.append(("hidden_files", self.hidden_files))

        for key, page in page_pairs:
            page.grid(row=0, column=0, sticky="nsew")
            self._pages[key] = page

    def _build_header(self, parent: tk.Frame) -> None:
        header = tk.Frame(parent, bg=Theme.PANEL, height=48)
        header.pack(fill="x")
        header.pack_propagate(False)

        # Border bottom
        tk.Frame(parent, bg=Theme.BORDER, height=1).pack(fill="x")

        self._page_title_var = tk.StringVar(value="DASHBOARD")
        tk.Label(header, textvariable=self._page_title_var, bg=Theme.PANEL,
                 fg=Theme.TEXT, font=("Segoe UI Semibold", 12), anchor="w",
                 padx=16).pack(side="left", fill="y")

        # Quick-action buttons on right
        btn_frame = tk.Frame(header, bg=Theme.PANEL)
        btn_frame.pack(side="right", padx=12, pady=8)
        ttk.Button(btn_frame, text="Settings",
                   command=lambda: self._navigate("settings")).pack(side="right", padx=2)
        ttk.Button(btn_frame, text="Refresh",
                   command=self._refresh_dashboard).pack(side="right", padx=2)

    def _build_status_bar(self) -> None:
        self.status_bar = StatusBar(self.root)
        self.status_bar.pack(side="bottom", fill="x")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _navigate(self, key: str) -> None:
        role = self.app.authenticated_user["role"] if self.app.authenticated_user else "viewer"
        if key not in _ROLE_PAGES.get(role, set()):
            return
        if key not in self._pages:
            return

        # Deactivate previous
        if self._active_key and self._active_key in self._nav_labels:
            prev_text = self._nav_text[self._active_key]
            self._nav_labels[self._active_key].configure(
                bg=Theme.SIDEBAR, fg=Theme.MUTED, text=f"   {prev_text}"
            )

        # Activate new
        self._active_key = key
        label_text = self._nav_text[key]
        self._nav_labels[key].configure(
            bg=Theme.PANEL_2, fg=Theme.CYAN, text=f"▌ {label_text}"
        )

        self._page_title_var.set(label_text)
        self._pages[key].tkraise()

        # Page-specific activation hooks
        if key == "dashboard":
            self.dashboard.refresh()
        elif key == "results":
            self.results.on_tab_activate()
        elif key == "reports":
            self.reports.on_tab_activate()
        elif key == "monitor":
            self.monitor.on_tab_activate()
        elif key == "scan_history":
            self.scan_history.on_tab_activate()
        elif key == "sections":
            self.sections.on_tab_activate()
        elif key == "duplicates":
            self.duplicates.on_tab_activate()
        elif key == "owner_index":
            self.owner_index.on_tab_activate()
        elif key == "manage_users":
            self.manage_users.on_tab_activate()
        elif key == "hidden_files":
            self.hidden_files.on_tab_activate()

    def _on_hover(self, widget: tk.Label, key: str) -> None:
        if key != self._active_key:
            widget.configure(fg=Theme.TEXT)

    def _on_leave(self, widget: tk.Label, key: str) -> None:
        if key != self._active_key:
            widget.configure(fg=Theme.MUTED)

    def _bind_events(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def _go_settings(self) -> None:
        self._navigate("settings")

    def _refresh_dashboard(self) -> None:
        self.dashboard.refresh()

    def set_status(self, text: str) -> None:
        self.status_bar.set(text)
