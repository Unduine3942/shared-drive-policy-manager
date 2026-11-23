"""Reports page — summary views and CSV/XLSX export."""
from __future__ import annotations

import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING

from ..core import reports as rpt
from ..db.repositories import ScanRunRepo, ViolationRepo
from .theme import Theme
from .widgets import DonutChart, MiniHBarChart

if TYPE_CHECKING:
    from ..app import App

log = logging.getLogger(__name__)

_XLSX_LABEL = "Export XLSX" if rpt.XLSX_AVAILABLE else "Export XLSX (unavailable)"


def _make_scrolled_tree(
    parent: tk.Widget, columns: list[tuple[str, str, int, str]]
) -> ttk.Treeview:
    """Return a Treeview with vertical + horizontal scrollbars.

    columns: list of (col_id, heading, width, anchor)
    """
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True, padx=4, pady=4)

    vsb = ttk.Scrollbar(frame, orient="vertical")
    hsb = ttk.Scrollbar(frame, orient="horizontal")

    col_ids = [c[0] for c in columns]
    tree = ttk.Treeview(
        frame,
        columns=col_ids,
        show="headings",
        yscrollcommand=vsb.set,
        xscrollcommand=hsb.set,
        selectmode="browse",
    )
    vsb.config(command=tree.yview)
    hsb.config(command=tree.xview)

    for col_id, heading, width, anchor in columns:
        tree.heading(col_id, text=heading)
        tree.column(col_id, width=width, anchor=anchor, stretch=(anchor == "w"))

    vsb.pack(side="right", fill="y")
    hsb.pack(side="bottom", fill="x")
    tree.pack(fill="both", expand=True)
    return tree


class ReportsPage(ttk.Frame):
    def __init__(self, parent: tk.Widget, app: "App") -> None:
        super().__init__(parent)
        self.app = app

        self._run_var = tk.StringVar(value="All Runs")
        self._run_map: dict[str, int | None] = {"All Runs": None}

        self._build_header()
        self._build_notebook()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_header(self) -> None:
        hdr = ttk.Frame(self)
        hdr.pack(fill="x", padx=8, pady=(8, 2))

        ttk.Label(hdr, text="Scan Run:").pack(side="left")
        self._run_combo = ttk.Combobox(
            hdr, textvariable=self._run_var, state="readonly", width=38
        )
        self._run_combo.pack(side="left", padx=(4, 16))
        self._run_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_all())

        ttk.Button(hdr, text="Refresh", command=self._refresh_all).pack(side="left", padx=4)
        ttk.Button(hdr, text="Export CSV", command=self._export_csv).pack(side="left", padx=4)

        xlsx_btn = ttk.Button(
            hdr,
            text=_XLSX_LABEL,
            command=self._export_xlsx,
            state="normal" if rpt.XLSX_AVAILABLE else "disabled",
        )
        xlsx_btn.pack(side="left", padx=4)

        self._status_var = tk.StringVar()
        ttk.Label(hdr, textvariable=self._status_var, foreground=Theme.MUTED).pack(
            side="right", padx=8
        )

    def _build_notebook(self) -> None:
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=8, pady=(2, 8))

        self._tab_overview = ttk.Frame(self._nb)
        self._tab_severity = ttk.Frame(self._nb)
        self._tab_section = ttk.Frame(self._nb)
        self._tab_owner = ttk.Frame(self._nb)
        self._tab_extension = ttk.Frame(self._nb)
        self._tab_stale = ttk.Frame(self._nb)
        self._tab_largest = ttk.Frame(self._nb)
        self._tab_errors = ttk.Frame(self._nb)

        self._nb.add(self._tab_overview, text="Overview")
        self._nb.add(self._tab_severity, text="By Severity")
        self._nb.add(self._tab_section, text="By Section")
        self._nb.add(self._tab_owner, text="By Owner / Creator")
        self._nb.add(self._tab_extension, text="By Extension")
        self._nb.add(self._tab_stale, text="Stale by Section")
        self._nb.add(self._tab_largest, text="Largest Flagged Files")
        self._nb.add(self._tab_errors, text="Scan Errors")

        self._build_overview_tab()

        self._tree_severity = _make_scrolled_tree(
            self._tab_severity,
            [
                ("severity", "Severity", 100, "w"),
                ("violation_count", "Violations", 110, "e"),
                ("file_count", "Files", 100, "e"),
            ],
        )
        self._tree_section = _make_scrolled_tree(
            self._tab_section,
            [
                ("section_name", "Section", 240, "w"),
                ("violation_count", "Violations", 110, "e"),
                ("file_count", "Files", 100, "e"),
                ("critical_count", "Critical", 90, "e"),
            ],
        )
        self._tree_owner = _make_scrolled_tree(
            self._tab_owner,
            [
                ("owner_name", "Owner / Creator Proxy", 280, "w"),
                ("violation_count", "Violations", 110, "e"),
                ("file_count", "Files", 100, "e"),
            ],
        )
        self._tree_extension = _make_scrolled_tree(
            self._tab_extension,
            [
                ("extension", "Extension", 130, "w"),
                ("violation_count", "Violations", 110, "e"),
                ("file_count", "Files", 100, "e"),
            ],
        )
        self._tree_stale = _make_scrolled_tree(
            self._tab_stale,
            [
                ("section_name", "Section", 240, "w"),
                ("stale_count", "Stale Files", 110, "e"),
                ("total_bytes", "Total Size (bytes)", 150, "e"),
            ],
        )
        self._tree_largest = _make_scrolled_tree(
            self._tab_largest,
            [
                ("name", "File Name", 210, "w"),
                ("size_bytes", "Size (bytes)", 120, "e"),
                ("owner_name", "Owner / Creator Proxy", 190, "w"),
                ("section_name", "Section", 160, "w"),
                ("mtime_utc", "Modified (UTC)", 155, "w"),
                ("full_path", "Full Path", 420, "w"),
            ],
        )
        self._tree_errors = _make_scrolled_tree(
            self._tab_errors,
            [
                ("path", "Path", 360, "w"),
                ("operation", "Operation", 110, "w"),
                ("error_type", "Error Type", 170, "w"),
                ("error_message", "Message", 360, "w"),
                ("root_path", "Root", 200, "w"),
                ("created_at_utc", "Timestamp (UTC)", 155, "w"),
            ],
        )

        for _t in (self._tree_severity, self._tree_section, self._tree_owner,
                   self._tree_extension, self._tree_stale, self._tree_largest,
                   self._tree_errors):
            _t.tag_configure("empty", foreground=Theme.MUTED)

    def _build_overview_tab(self) -> None:
        canvas = tk.Canvas(self._tab_overview, bg=Theme.BG, highlightthickness=0)
        vsb = ttk.Scrollbar(self._tab_overview, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)

        inner = tk.Frame(canvas, bg=Theme.BG)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _resize(e):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _canvas_resize(e):
            canvas.itemconfig(win, width=e.width)

        inner.bind("<Configure>", _resize)
        canvas.bind("<Configure>", _canvas_resize)

        # Top row: donut (severity) + bar (sections)
        row1 = tk.Frame(inner, bg=Theme.BG)
        row1.pack(fill="x", padx=Theme.PAD_LG, pady=(Theme.PAD_LG, Theme.PAD_MD))
        row1.columnconfigure(0, weight=2)
        row1.columnconfigure(1, weight=3)

        lo, lb = self._make_panel(row1, "SEVERITY BREAKDOWN")
        lo.grid(row=0, column=0, sticky="nsew", padx=(0, Theme.PAD_MD // 2))
        self._ov_donut = DonutChart(lb, colors=[Theme.RED, Theme.AMBER, Theme.BLUE])
        self._ov_donut.pack(padx=Theme.PAD_LG, pady=Theme.PAD_LG)

        ro, rb = self._make_panel(row1, "TOP SECTIONS")
        ro.grid(row=0, column=1, sticky="nsew", padx=(Theme.PAD_MD // 2, 0))
        self._ov_bar_sections = MiniHBarChart(rb, width=380)
        self._ov_bar_sections.pack(padx=Theme.PAD_LG, pady=Theme.PAD_LG, anchor="w")

        # Bottom row: extensions + owners
        row2 = tk.Frame(inner, bg=Theme.BG)
        row2.pack(fill="x", padx=Theme.PAD_LG, pady=(0, Theme.PAD_LG))
        row2.columnconfigure(0, weight=1)
        row2.columnconfigure(1, weight=1)

        leo, leb = self._make_panel(row2, "TOP EXTENSIONS")
        leo.grid(row=0, column=0, sticky="nsew", padx=(0, Theme.PAD_MD // 2))
        self._ov_bar_ext = MiniHBarChart(leb, width=300)
        self._ov_bar_ext.pack(padx=Theme.PAD_LG, pady=Theme.PAD_LG, anchor="w")

        roo, rob = self._make_panel(row2, "TOP OWNERS / CREATORS")
        roo.grid(row=0, column=1, sticky="nsew", padx=(Theme.PAD_MD // 2, 0))
        self._ov_bar_owners = MiniHBarChart(rob, width=300)
        self._ov_bar_owners.pack(padx=Theme.PAD_LG, pady=Theme.PAD_LG, anchor="w")

    @staticmethod
    def _make_panel(parent: tk.Widget, title: str):
        from .widgets import panel
        return panel(parent, title)

    def _load_overview(self, conn, run_id: int | None) -> None:
        sev_rows = rpt.summary_by_severity(conn, run_id)
        sev_data = {r["severity"].capitalize(): r["violation_count"] for r in sev_rows}
        self._ov_donut.update_data(
            sev_data or {"(no data)": 1},
            colors=[Theme.RED, Theme.AMBER, Theme.BLUE] if sev_data else [Theme.DIM],
        )

        sec_rows = rpt.summary_by_section(conn, run_id)
        sec_data = {r["section_name"]: r["violation_count"] for r in sec_rows[:8]}
        self._ov_bar_sections.update_data(sec_data or {"(no data)": 0})

        ext_rows = rpt.summary_by_extension(conn, run_id, limit=8)
        ext_data = {r["extension"]: r["violation_count"] for r in ext_rows}
        self._ov_bar_ext.update_data(ext_data or {"(no data)": 0})

        own_rows = rpt.summary_by_owner(conn, run_id, limit=6)
        own_data = {r["owner_name"]: r["violation_count"] for r in own_rows}
        self._ov_bar_owners.update_data(own_data or {"(no data)": 0})

    # ------------------------------------------------------------------
    # Tab activation
    # ------------------------------------------------------------------

    def on_tab_activate(self) -> None:
        self._refresh_run_combo()
        self._refresh_all()

    # ------------------------------------------------------------------
    # Run selector
    # ------------------------------------------------------------------

    def _refresh_run_combo(self) -> None:
        try:
            conn = self.app.get_db()
            runs = ScanRunRepo().list_all(conn)
        except Exception as exc:
            log.error("Failed to populate run selector: %s", exc)
            return

        values = ["All Runs"]
        self._run_map = {"All Runs": None}
        for r in runs:
            label = (
                f"Run #{r['run_id']}  {r.get('run_type', '?')}  "
                f"{(r.get('started_at_utc') or '')[:16]}  [{r.get('status', '')}]"
            )
            values.append(label)
            self._run_map[label] = r["run_id"]

        self._run_combo["values"] = values
        if self._run_var.get() not in self._run_map:
            self._run_var.set("All Runs")

    def _selected_run_id(self) -> int | None:
        return self._run_map.get(self._run_var.get())

    # ------------------------------------------------------------------
    # Load / refresh
    # ------------------------------------------------------------------

    def _refresh_all(self) -> None:
        try:
            conn = self.app.get_db()
            run_id = self._selected_run_id()
            self._load_overview(conn, run_id)
            self._load_severity(conn, run_id)
            self._load_section(conn, run_id)
            self._load_owner(conn, run_id)
            self._load_extension(conn, run_id)
            self._load_stale(conn, run_id)
            self._load_largest(conn, run_id)
            self._load_errors(conn, run_id)
            self._status_var.set("Reports loaded.")
        except Exception as exc:
            self._status_var.set(f"Error: {exc}")

    @staticmethod
    def _clear(tree: ttk.Treeview) -> None:
        tree.delete(*tree.get_children())

    def _load_severity(self, conn, run_id: int | None) -> None:
        rows = rpt.summary_by_severity(conn, run_id)
        self._clear(self._tree_severity)
        for r in rows:
            self._tree_severity.insert("", "end", values=(
                r.get("severity", ""),
                r.get("violation_count", 0),
                r.get("file_count", 0),
            ))
        if not rows:
            self._tree_severity.insert("", "end", values=("(no violations)", "", ""), tags=("empty",))

    def _load_section(self, conn, run_id: int | None) -> None:
        rows = rpt.summary_by_section(conn, run_id)
        self._clear(self._tree_section)
        for r in rows:
            self._tree_section.insert("", "end", values=(
                r.get("section_name", ""),
                r.get("violation_count", 0),
                r.get("file_count", 0),
                r.get("critical_count", 0),
            ))
        if not rows:
            self._tree_section.insert("", "end", values=("(no data)", "", "", ""), tags=("empty",))

    def _load_owner(self, conn, run_id: int | None) -> None:
        rows = rpt.summary_by_owner(conn, run_id)
        self._clear(self._tree_owner)
        for r in rows:
            self._tree_owner.insert("", "end", values=(
                r.get("owner_name", ""),
                r.get("violation_count", 0),
                r.get("file_count", 0),
            ))
        if not rows:
            self._tree_owner.insert("", "end", values=("(no data)", "", ""), tags=("empty",))

    def _load_extension(self, conn, run_id: int | None) -> None:
        rows = rpt.summary_by_extension(conn, run_id)
        self._clear(self._tree_extension)
        for r in rows:
            self._tree_extension.insert("", "end", values=(
                r.get("extension", ""),
                r.get("violation_count", 0),
                r.get("file_count", 0),
            ))
        if not rows:
            self._tree_extension.insert("", "end", values=("(no data)", "", ""), tags=("empty",))

    def _load_stale(self, conn, run_id: int | None) -> None:
        rows = rpt.stale_by_section(conn, run_id)
        self._clear(self._tree_stale)
        for r in rows:
            self._tree_stale.insert("", "end", values=(
                r.get("section_name", ""),
                r.get("stale_count", 0),
                r.get("total_bytes", 0),
            ))
        if not rows:
            self._tree_stale.insert("", "end", values=("(no data)", "", ""), tags=("empty",))

    def _load_largest(self, conn, run_id: int | None) -> None:
        rows = rpt.largest_flagged_files(conn, run_id)
        self._clear(self._tree_largest)
        for r in rows:
            self._tree_largest.insert("", "end", values=(
                r.get("name", ""),
                r.get("size_bytes", 0),
                r.get("owner_name", ""),
                r.get("section_name", ""),
                r.get("mtime_utc", ""),
                r.get("full_path", ""),
            ))
        if not rows:
            self._tree_largest.insert("", "end",
                                      values=("(no data)", "", "", "", "", ""),
                                      tags=("empty",))

    def _load_errors(self, conn, run_id: int | None) -> None:
        self._clear(self._tree_errors)
        effective_run_id = run_id
        if effective_run_id is None:
            try:
                all_runs = ScanRunRepo().list_all(conn)
                if not all_runs:
                    self._tree_errors.insert("", "end",
                                             values=("(no errors)", "", "", "", "", ""),
                                             tags=("empty",))
                    return
                effective_run_id = all_runs[0]["run_id"]
            except Exception as exc:
                log.error("Failed to resolve run ID for errors report: %s", exc)
                return
        rows = rpt.scan_errors_for_run(conn, effective_run_id)
        for r in rows:
            self._tree_errors.insert("", "end", values=(
                r.get("path", ""),
                r.get("operation", ""),
                r.get("error_type", ""),
                r.get("error_message", ""),
                r.get("root_path", ""),
                r.get("created_at_utc", ""),
            ))
        if not rows:
            self._tree_errors.insert("", "end",
                                     values=("(no errors)", "", "", "", "", ""),
                                     tags=("empty",))

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _get_violation_rows(self) -> list[dict]:
        try:
            conn = self.app.get_db()
            run_id = self._selected_run_id()
            return ViolationRepo().query_full(conn, run_id=run_id, limit=100_000, offset=0)
        except Exception as exc:
            messagebox.showerror("Export Error", f"Could not load violations:\n{exc}", parent=self)
            return []

    def _export_csv(self) -> None:
        rows = self._get_violation_rows()
        if not rows:
            messagebox.showinfo("Export CSV", "No violations to export.", parent=self)
            return
        dest = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save violations as CSV",
        )
        if not dest:
            return
        try:
            count = rpt.export_violations_csv(rows, dest)
            self._status_var.set(f"Exported {count} rows to CSV.")
        except Exception as exc:
            messagebox.showerror("Export Error", str(exc), parent=self)

    def _export_xlsx(self) -> None:
        if not rpt.XLSX_AVAILABLE:
            messagebox.showwarning(
                "XLSX Unavailable",
                "openpyxl is not available in this environment.\nUse CSV export instead.",
                parent=self,
            )
            return
        rows = self._get_violation_rows()
        if not rows:
            messagebox.showinfo("Export XLSX", "No violations to export.", parent=self)
            return
        dest = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            title="Save violations as XLSX",
        )
        if not dest:
            return
        try:
            count = rpt.export_violations_xlsx(rows, dest)
            self._status_var.set(f"Exported {count} rows to XLSX.")
        except Exception as exc:
            messagebox.showerror("Export Error", str(exc), parent=self)
