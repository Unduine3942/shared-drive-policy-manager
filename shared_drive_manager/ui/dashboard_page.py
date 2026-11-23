"""Dashboard page — stat cards, charts, scan summary, environment status."""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from shared_drive_manager.core.path_utils import format_bytes
from shared_drive_manager.core import reports as rpt
from shared_drive_manager.ui.theme import Theme
from shared_drive_manager.ui.widgets import (
    DonutChart,
    MiniHBarChart,
    ScrolledText,
    StatCard,
    panel,
    section_header,
    separator,
)

if TYPE_CHECKING:
    from shared_drive_manager.app import Application


_OPTIONAL_PACKAGES = [
    ("win32security", "win32security"),
    ("openpyxl", "openpyxl"),
    ("pandas", "pandas"),
    ("arcpy", "arcpy"),
    ("psutil", "psutil"),
]


def _check_import(module: str) -> bool:
    try:
        __import__(module)
        return True
    except ImportError:
        return False


class DashboardPage(ttk.Frame):
    def __init__(self, parent: tk.Widget, app: "Application") -> None:
        super().__init__(parent)
        self.configure(style="TFrame")
        self.app = app

        self._card_files: StatCard | None = None
        self._card_size: StatCard | None = None
        self._card_open: StatCard | None = None
        self._card_crit: StatCard | None = None
        self._donut: DonutChart | None = None
        self._bar_sections: MiniHBarChart | None = None

        self._build()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

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

        def _on_canvas_resize(event):
            canvas.itemconfig(win, width=event.width)

        inner.bind("<Configure>", _on_configure)
        canvas.bind("<Configure>", _on_canvas_resize)

        self._build_stat_row(inner)
        self._build_middle_row(inner)
        self._build_bottom_row(inner)

    def _build_stat_row(self, parent: tk.Widget) -> None:
        outer, body = panel(parent, "OVERVIEW")
        outer.pack(fill="x", padx=Theme.PAD_LG, pady=(Theme.PAD_LG, Theme.PAD_MD))

        row = tk.Frame(body, bg=Theme.PANEL)
        row.pack(fill="x", padx=Theme.PAD_LG, pady=Theme.PAD_LG)
        for i in range(4):
            row.columnconfigure(i, weight=1, uniform="card")

        files_val, size_val, open_val, crit_val = self._load_totals()

        self._card_files = StatCard(row, "FILES INVENTORIED", files_val, Theme.CYAN)
        self._card_files.grid(row=0, column=0, sticky="ew", padx=Theme.PAD_SM)

        self._card_size = StatCard(row, "TOTAL SIZE", size_val, Theme.BLUE)
        self._card_size.grid(row=0, column=1, sticky="ew", padx=Theme.PAD_SM)

        self._card_open = StatCard(row, "OPEN VIOLATIONS", open_val, Theme.AMBER)
        self._card_open.grid(row=0, column=2, sticky="ew", padx=Theme.PAD_SM)

        self._card_crit = StatCard(row, "CRITICAL", crit_val, Theme.RED)
        self._card_crit.grid(row=0, column=3, sticky="ew", padx=Theme.PAD_SM)

    def _build_middle_row(self, parent: tk.Widget) -> None:
        row = tk.Frame(parent, bg=Theme.BG)
        row.pack(fill="x", padx=Theme.PAD_LG, pady=(0, Theme.PAD_MD))
        row.columnconfigure(0, weight=3)
        row.columnconfigure(1, weight=2)

        # Left: Latest scan
        lo, lb = panel(row, "LATEST SCAN")
        lo.grid(row=0, column=0, sticky="nsew", padx=(0, Theme.PAD_MD // 2))
        self._build_scan_info(lb)

        # Right: severity donut
        ro, rb = panel(row, "VIOLATIONS BY SEVERITY")
        ro.grid(row=0, column=1, sticky="nsew", padx=(Theme.PAD_MD // 2, 0))

        sev_data = self._load_severity_data()
        sev_colors = [Theme.RED, Theme.AMBER, Theme.BLUE]
        self._donut = DonutChart(rb, data=sev_data if sev_data else None,
                                 colors=sev_colors)
        self._donut.pack(padx=Theme.PAD_LG, pady=Theme.PAD_LG)

    def _build_bottom_row(self, parent: tk.Widget) -> None:
        row = tk.Frame(parent, bg=Theme.BG)
        row.pack(fill="x", padx=Theme.PAD_LG, pady=(0, Theme.PAD_LG))
        row.columnconfigure(0, weight=3)
        row.columnconfigure(1, weight=2)

        # Left: top sections bar chart
        lo, lb = panel(row, "TOP SECTIONS BY VIOLATIONS")
        lo.grid(row=0, column=0, sticky="nsew", padx=(0, Theme.PAD_MD // 2))

        section_data = self._load_section_data()
        self._bar_sections = MiniHBarChart(lb, data=section_data if section_data else None)
        self._bar_sections.pack(padx=Theme.PAD_LG, pady=Theme.PAD_LG, anchor="w")

        # Right: environment
        ro, rb = panel(row, "ENVIRONMENT STATUS")
        ro.grid(row=0, column=1, sticky="nsew", padx=(Theme.PAD_MD // 2, 0))
        self._build_env_grid(rb)

    # ------------------------------------------------------------------
    # Sub-builders
    # ------------------------------------------------------------------

    def _build_scan_info(self, parent: tk.Widget) -> None:
        run = self.app.scan_run_repo.get_latest(self.app.conn)
        if run is None:
            tk.Label(parent, text="No scans have been run yet.",
                     bg=Theme.PANEL, fg=Theme.MUTED,
                     font=Theme.FONT_BODY).pack(
                padx=Theme.PAD_LG, pady=Theme.PAD_LG, anchor="w")
            return

        status = run.get("status", "—")
        status_color = {
            "completed": Theme.GREEN,
            "running": Theme.CYAN,
            "canceled": Theme.AMBER,
            "failed": Theme.RED,
        }.get(status, Theme.MUTED)

        rows = [
            ("Run #", str(run.get("run_id", "—")), None),
            ("Status", status.upper(), status_color),
            ("Started", run.get("started_at_utc") or "—", None),
            ("Ended", run.get("ended_at_utc") or "—", None),
            ("Files seen", f"{run.get('files_seen', 0):,}", None),
            ("Bytes seen", format_bytes(run.get("bytes_seen", 0)), None),
            ("Violations", f"{run.get('violations_seen', 0):,}", None),
            ("Errors", f"{run.get('errors_seen', 0):,}", None),
        ]

        grid = tk.Frame(parent, bg=Theme.PANEL)
        grid.pack(fill="x", padx=Theme.PAD_LG, pady=Theme.PAD_LG)

        for i, (label, value, color) in enumerate(rows):
            tk.Label(grid, text=label, bg=Theme.PANEL, fg=Theme.MUTED,
                     font=Theme.FONT_BODY, anchor="w", width=14).grid(
                row=i, column=0, sticky="w", pady=1)
            tk.Label(grid, text=value, bg=Theme.PANEL,
                     fg=color or Theme.TEXT,
                     font=Theme.FONT_BODY_SB, anchor="w").grid(
                row=i, column=1, sticky="w", padx=(Theme.PAD_SM, 0))

    def _build_env_grid(self, parent: tk.Widget) -> None:
        checks = self._collect_env_checks()
        grid = tk.Frame(parent, bg=Theme.PANEL)
        grid.pack(fill="x", padx=Theme.PAD_MD, pady=Theme.PAD_MD)

        for i, (label, ok, note) in enumerate(checks):
            icon = "●"
            color = Theme.GREEN if ok else Theme.RED
            tk.Label(grid, text=icon, bg=Theme.PANEL, fg=color,
                     font=("Consolas", 9)).grid(row=i, column=0, sticky="w", padx=(0, 4))
            tip = label
            if note:
                tip += f"  ({note})"
            tk.Label(grid, text=tip, bg=Theme.PANEL,
                     fg=Theme.TEXT if ok else Theme.MUTED,
                     font=Theme.FONT_CAPTION, anchor="w").grid(
                row=i, column=1, sticky="w", pady=1)

    # ------------------------------------------------------------------
    # Data loaders
    # ------------------------------------------------------------------

    def _load_totals(self) -> tuple[str, str, str, str]:
        try:
            total_files = self.app.file_repo.count(self.app.conn)
            total_bytes = self.app.file_repo.total_bytes(self.app.conn)
            open_v = self.app.violation_repo.count_open(self.app.conn)
            crit = self.app.violation_repo.count_critical_open(self.app.conn)
            return (
                f"{total_files:,}",
                format_bytes(total_bytes),
                f"{open_v:,}",
                f"{crit:,}",
            )
        except Exception:
            return ("—", "—", "—", "—")

    def _load_severity_data(self) -> dict[str, int]:
        try:
            rows = rpt.summary_by_severity(self.app.conn)
            return {r["severity"].capitalize(): r["violation_count"] for r in rows}
        except Exception:
            return {}

    def _load_section_data(self, limit: int = 8) -> dict[str, int]:
        try:
            rows = rpt.summary_by_section(self.app.conn)
            return {
                r["section_name"]: r["violation_count"]
                for r in rows[:limit]
            }
        except Exception:
            return {}

    def _collect_env_checks(self) -> list[tuple[str, bool, str]]:
        checks: list[tuple[str, bool, str]] = []

        vi = sys.version_info
        py_ok = vi.major == 3 and vi.minor == 11
        checks.append((
            f"Python {vi.major}.{vi.minor}.{vi.micro}",
            py_ok,
            "" if py_ok else "expected 3.11",
        ))
        checks.append(("sqlite3", True, ""))
        checks.append(("tkinter", True, ""))

        db_ok = self._check_db_writable()
        checks.append(("Database", db_ok, "" if db_ok else "check path"))

        for label, mod in _OPTIONAL_PACKAGES:
            avail = _check_import(mod)
            checks.append((label, avail, "" if avail else "optional"))

        return checks

    def _check_db_writable(self) -> bool:
        try:
            self.app.conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        files_val, size_val, open_val, crit_val = self._load_totals()

        if self._card_files:
            self._card_files.update_value(files_val)
        if self._card_size:
            self._card_size.update_value(size_val)
        if self._card_open:
            self._card_open.update_value(open_val)
        if self._card_crit:
            self._card_crit.update_value(crit_val)

        if self._donut:
            sev_data = self._load_severity_data()
            self._donut.update_data(
                sev_data or {"(no data)": 1},
                colors=[Theme.RED, Theme.AMBER, Theme.BLUE] if sev_data
                       else [Theme.DIM],
            )

        if self._bar_sections:
            section_data = self._load_section_data()
            if section_data:
                self._bar_sections.update_data(section_data)
