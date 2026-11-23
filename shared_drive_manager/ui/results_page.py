"""Results browser — filter, review, and export policy violations."""
from __future__ import annotations

import logging
import math
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING

from shared_drive_manager.core import reports as rpt
from shared_drive_manager.core.path_utils import format_bytes
from shared_drive_manager.core.reports import export_violations_csv
from shared_drive_manager.ui.theme import Theme

if TYPE_CHECKING:
    from shared_drive_manager.app import Application

log = logging.getLogger(__name__)

_PAGE_SIZE = 100
_SEV_TAG = {"critical": "crit", "warning": "warn", "info": "info_tag"}


class ResultsPage(ttk.Frame):
    def __init__(self, parent: tk.Widget, app: "Application") -> None:
        super().__init__(parent)
        self.app = app
        self._current_page = 0
        self._total_count = 0
        self._rows: list[dict] = []
        self._run_id_map: dict[str, int] = {}
        self._policy_id_map: dict[str, int] = {}

        self._build_filter_bar()
        self._build_toolbar()
        self._build_severity_strip()
        self._build_table()
        self._build_pager()
        self._build_detail()

    def on_tab_activate(self) -> None:
        self._refresh_filter_options()
        self._load_page()

    # ------------------------------------------------------------------ #
    # Layout builders                                                      #
    # ------------------------------------------------------------------ #

    def _build_filter_bar(self) -> None:
        frm = ttk.LabelFrame(self, text="Filters", padding=4)
        frm.pack(fill="x", padx=4, pady=(4, 2))

        r1 = ttk.Frame(frm)
        r1.pack(fill="x")

        ttk.Label(r1, text="Run:").pack(side="left")
        self._run_var = tk.StringVar(value="All")
        self._run_combo = ttk.Combobox(
            r1, textvariable=self._run_var, width=26, state="readonly"
        )
        self._run_combo.pack(side="left", padx=(2, 10))

        ttk.Label(r1, text="Policy:").pack(side="left")
        self._policy_var = tk.StringVar(value="All")
        self._policy_combo = ttk.Combobox(
            r1, textvariable=self._policy_var, width=22, state="readonly"
        )
        self._policy_combo.pack(side="left", padx=(2, 10))

        ttk.Label(r1, text="Severity:").pack(side="left")
        self._severity_var = tk.StringVar(value="All")
        ttk.Combobox(
            r1,
            textvariable=self._severity_var,
            width=10,
            state="readonly",
            values=["All", "critical", "warning", "info"],
        ).pack(side="left", padx=(2, 10))

        ttk.Label(r1, text="Section:").pack(side="left")
        self._section_var = tk.StringVar(value="All")
        self._section_combo = ttk.Combobox(
            r1, textvariable=self._section_var, width=18, state="readonly"
        )
        self._section_combo.pack(side="left", padx=(2, 10))

        ttk.Label(r1, text="Status:").pack(side="left")
        self._status_var = tk.StringVar(value="All")
        ttk.Combobox(
            r1,
            textvariable=self._status_var,
            width=12,
            state="readonly",
            values=["All", "open", "reviewed", "ignored", "resolved"],
        ).pack(side="left", padx=(2, 0))

        r2 = ttk.Frame(frm)
        r2.pack(fill="x", pady=(4, 0))

        ttk.Label(r2, text="Owner:").pack(side="left")
        self._owner_var = tk.StringVar()
        ttk.Entry(r2, textvariable=self._owner_var, width=16).pack(
            side="left", padx=(2, 10)
        )

        ttk.Label(r2, text="Ext:").pack(side="left")
        self._ext_var = tk.StringVar()
        ttk.Entry(r2, textvariable=self._ext_var, width=8).pack(
            side="left", padx=(2, 10)
        )

        ttk.Label(r2, text="Path contains:").pack(side="left")
        self._path_var = tk.StringVar()
        ttk.Entry(r2, textvariable=self._path_var, width=24).pack(
            side="left", padx=(2, 10)
        )

        ttk.Label(r2, text="Min size (B):").pack(side="left")
        self._minsize_var = tk.StringVar()
        ttk.Entry(r2, textvariable=self._minsize_var, width=12).pack(
            side="left", padx=(2, 10)
        )

        ttk.Label(r2, text="Mtime from:").pack(side="left")
        self._mtime_from_var = tk.StringVar()
        ttk.Entry(r2, textvariable=self._mtime_from_var, width=12).pack(
            side="left", padx=(2, 4)
        )
        ttk.Label(r2, text="to:").pack(side="left")
        self._mtime_to_var = tk.StringVar()
        ttk.Entry(r2, textvariable=self._mtime_to_var, width=12).pack(
            side="left", padx=(2, 10)
        )

        ttk.Button(r2, text="Apply", command=self._apply_filters).pack(
            side="left", padx=(0, 4)
        )
        ttk.Button(r2, text="Clear", command=self._clear_filters).pack(side="left")

    def _build_toolbar(self) -> None:
        tb = ttk.Frame(self, padding=(4, 2))
        tb.pack(fill="x")
        ttk.Button(tb, text="Open Folder", command=self._open_folder).pack(
            side="left", padx=2
        )
        ttk.Button(tb, text="Copy Path", command=self._copy_path).pack(
            side="left", padx=2
        )
        ttk.Separator(tb, orient="vertical").pack(side="left", padx=6, fill="y")
        ttk.Button(
            tb, text="Mark Reviewed", command=lambda: self._open_action_dialog("reviewed")
        ).pack(side="left", padx=2)
        ttk.Button(
            tb, text="Mark Ignored", command=lambda: self._open_action_dialog("ignored")
        ).pack(side="left", padx=2)
        ttk.Button(
            tb, text="Mark Resolved", command=lambda: self._open_action_dialog("resolved")
        ).pack(side="left", padx=2)
        ttk.Button(tb, text="Add Note", command=self._add_note).pack(
            side="left", padx=2
        )
        ttk.Button(tb, text="View History", command=self._view_history).pack(
            side="left", padx=2
        )
        ttk.Separator(tb, orient="vertical").pack(side="left", padx=6, fill="y")
        ttk.Button(tb, text="Export CSV", command=self._export_csv).pack(
            side="left", padx=2
        )

    def _build_severity_strip(self) -> None:
        strip = tk.Frame(self, bg=Theme.PANEL, height=28)
        strip.pack(fill="x", padx=4, pady=(0, 2))
        strip.pack_propagate(False)

        inner = tk.Frame(strip, bg=Theme.PANEL)
        inner.pack(side="left", padx=Theme.PAD_MD, pady=4)

        def _dot_label(parent: tk.Widget, color: str) -> tk.Label:
            return tk.Label(parent, text="⬤", fg=color, bg=Theme.PANEL,
                            font=("Consolas", 8))

        def _count_label(parent: tk.Widget) -> tk.Label:
            return tk.Label(parent, text="—", fg=Theme.TEXT, bg=Theme.PANEL,
                            font=Theme.FONT_CAPTION)

        _dot_label(inner, Theme.RED).pack(side="left", padx=(0, 2))
        tk.Label(inner, text="CRITICAL", fg=Theme.MUTED, bg=Theme.PANEL,
                 font=Theme.FONT_CAPTION).pack(side="left")
        self._sev_crit_lbl = _count_label(inner)
        self._sev_crit_lbl.pack(side="left", padx=(3, 12))

        _dot_label(inner, Theme.AMBER).pack(side="left", padx=(0, 2))
        tk.Label(inner, text="WARNING", fg=Theme.MUTED, bg=Theme.PANEL,
                 font=Theme.FONT_CAPTION).pack(side="left")
        self._sev_warn_lbl = _count_label(inner)
        self._sev_warn_lbl.pack(side="left", padx=(3, 12))

        _dot_label(inner, Theme.BLUE).pack(side="left", padx=(0, 2))
        tk.Label(inner, text="INFO", fg=Theme.MUTED, bg=Theme.PANEL,
                 font=Theme.FONT_CAPTION).pack(side="left")
        self._sev_info_lbl = _count_label(inner)
        self._sev_info_lbl.pack(side="left", padx=(3, 16))

        tk.Label(inner, text="TOTAL", fg=Theme.MUTED, bg=Theme.PANEL,
                 font=Theme.FONT_CAPTION).pack(side="left")
        self._sev_total_lbl = _count_label(inner)
        self._sev_total_lbl.pack(side="left", padx=(3, 0))

    def _refresh_severity_strip(self) -> None:
        try:
            kwargs = self._get_filter_kwargs()
            run_id = kwargs.get("run_id")
            rows = rpt.summary_by_severity(self.app.conn, run_id)
            counts: dict[str, int] = {r["severity"]: r["violation_count"] for r in rows}
        except Exception:
            counts = {}
        crit = counts.get("critical", 0)
        warn = counts.get("warning", 0)
        info = counts.get("info", 0)
        total = crit + warn + info
        self._sev_crit_lbl.configure(text=f"{crit:,}",
                                     fg=Theme.RED if crit else Theme.MUTED)
        self._sev_warn_lbl.configure(text=f"{warn:,}",
                                     fg=Theme.AMBER if warn else Theme.MUTED)
        self._sev_info_lbl.configure(text=f"{info:,}",
                                     fg=Theme.BLUE if info else Theme.MUTED)
        self._sev_total_lbl.configure(text=f"{total:,}")

    def _build_table(self) -> None:
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=4)

        cols = (
            "sev", "policy", "name", "owner",
            "size", "modified", "section", "status", "run",
        )
        self._tree = ttk.Treeview(
            frame, columns=cols, show="headings", selectmode="extended"
        )

        headings = {
            "sev": "Sev",
            "policy": "Policy",
            "name": "File Name",
            "owner": "Owner / Creator Proxy",
            "size": "Size",
            "modified": "Modified (UTC)",
            "section": "Section",
            "status": "Status",
            "run": "Run",
        }
        widths = {
            "sev": 55, "policy": 155, "name": 190, "owner": 145,
            "size": 80, "modified": 125, "section": 115, "status": 75, "run": 50,
        }
        anchors = {"size": "e", "run": "e"}

        for col, heading in headings.items():
            self._tree.heading(col, text=heading)
            self._tree.column(
                col,
                width=widths[col],
                stretch=(col == "name"),
                anchor=anchors.get(col, "w"),
            )

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self._tree.pack(fill="both", expand=True)

        self._tree.tag_configure("crit", foreground=Theme.RED)
        self._tree.tag_configure("warn", foreground=Theme.AMBER)
        self._tree.tag_configure("info_tag", foreground=Theme.BLUE)
        self._tree.tag_configure("empty", foreground=Theme.MUTED)

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.bind("<Double-1>", lambda _e: self._open_folder())
        self._tree.bind("<Button-3>", self._on_right_click)

        self._ctx_menu = tk.Menu(self, tearoff=0)
        self._ctx_menu.add_command(
            label="Mark Reviewed", command=lambda: self._open_action_dialog("reviewed"))
        self._ctx_menu.add_command(
            label="Mark Ignored", command=lambda: self._open_action_dialog("ignored"))
        self._ctx_menu.add_command(
            label="Mark Resolved", command=lambda: self._open_action_dialog("resolved"))
        self._ctx_menu.add_separator()
        self._ctx_menu.add_command(label="Add Note", command=self._add_note)
        self._ctx_menu.add_separator()
        self._ctx_menu.add_command(label="Copy Path", command=self._copy_path)
        self._ctx_menu.add_command(label="Open Folder", command=self._open_folder)
        self._ctx_menu.add_separator()
        self._ctx_menu.add_command(label="View History", command=self._view_history)

    def _build_pager(self) -> None:
        pager = ttk.Frame(self, padding=(4, 2))
        pager.pack(fill="x")

        self._btn_first = ttk.Button(
            pager, text="|<", width=3, command=self._page_first
        )
        self._btn_first.pack(side="left", padx=2)
        self._btn_prev = ttk.Button(
            pager, text="<", width=3, command=self._page_prev
        )
        self._btn_prev.pack(side="left", padx=2)

        self._page_label = ttk.Label(pager, text="Page 0 of 0  (0 results)")
        self._page_label.pack(side="left", padx=10)

        self._btn_next = ttk.Button(
            pager, text=">", width=3, command=self._page_next
        )
        self._btn_next.pack(side="left", padx=2)
        self._btn_last = ttk.Button(
            pager, text=">|", width=3, command=self._page_last
        )
        self._btn_last.pack(side="left", padx=2)

    def _build_detail(self) -> None:
        frm = ttk.LabelFrame(self, text="Selected Violation", padding=4)
        frm.pack(fill="x", padx=4, pady=(2, 4))

        self._detail_path = ttk.Label(frm, text="Path: —", anchor="w", wraplength=1000)
        self._detail_path.pack(fill="x")
        self._detail_reason = ttk.Label(
            frm, text="Reason: —", anchor="w", wraplength=1000
        )
        self._detail_reason.pack(fill="x")
        self._detail_note = ttk.Label(frm, text="Note: —", anchor="w", wraplength=1000)
        self._detail_note.pack(fill="x")

    # ------------------------------------------------------------------ #
    # Filter helpers                                                       #
    # ------------------------------------------------------------------ #

    def _get_filter_kwargs(self) -> dict:
        kwargs: dict = {}

        run_val = self._run_var.get()
        if run_val and run_val != "All" and run_val in self._run_id_map:
            kwargs["run_id"] = self._run_id_map[run_val]

        pol_val = self._policy_var.get()
        if pol_val and pol_val != "All" and pol_val in self._policy_id_map:
            kwargs["policy_id"] = self._policy_id_map[pol_val]

        sev = self._severity_var.get()
        if sev and sev != "All":
            kwargs["severity"] = sev

        section = self._section_var.get()
        if section and section != "All":
            kwargs["section"] = section

        status = self._status_var.get()
        if status and status != "All":
            kwargs["status"] = status

        owner = self._owner_var.get().strip()
        if owner:
            kwargs["owner_contains"] = owner

        ext = self._ext_var.get().strip()
        if ext:
            kwargs["extension"] = ext

        path = self._path_var.get().strip()
        if path:
            kwargs["path_contains"] = path

        minsize = self._minsize_var.get().strip()
        if minsize:
            try:
                kwargs["min_size"] = int(minsize)
            except ValueError:
                pass

        mtime_from = self._mtime_from_var.get().strip()
        if mtime_from:
            kwargs["mtime_from"] = mtime_from

        mtime_to = self._mtime_to_var.get().strip()
        if mtime_to:
            kwargs["mtime_to"] = mtime_to

        return kwargs

    def _apply_filters(self) -> None:
        self._current_page = 0
        self._load_page()

    def _clear_filters(self) -> None:
        self._run_var.set("All")
        self._policy_var.set("All")
        self._severity_var.set("All")
        self._section_var.set("All")
        self._status_var.set("All")
        self._owner_var.set("")
        self._ext_var.set("")
        self._path_var.set("")
        self._minsize_var.set("")
        self._mtime_from_var.set("")
        self._mtime_to_var.set("")
        self._current_page = 0
        self._load_page()

    def _refresh_filter_options(self) -> None:
        conn = self.app.conn

        runs = self.app.scan_run_repo.list_all(conn)
        self._run_id_map = {}
        run_labels = ["All"]
        for r in runs:
            label = (
                f"Run #{r['run_id']} — "
                f"{(r.get('started_at_utc') or '')[:10]} "
                f"{r.get('status', '')}"
            )
            run_labels.append(label)
            self._run_id_map[label] = r["run_id"]
        self._run_combo["values"] = run_labels
        if self._run_var.get() not in run_labels:
            self._run_var.set("All")

        policies = self.app.policy_repo.list_all(conn)
        self._policy_id_map = {}
        pol_labels = ["All"]
        for p in policies:
            pol_labels.append(p["name"])
            self._policy_id_map[p["name"]] = p["policy_id"]
        self._policy_combo["values"] = pol_labels
        if self._policy_var.get() not in pol_labels:
            self._policy_var.set("All")

        sections = self.app.violation_repo.distinct_sections(conn)
        sec_labels = ["All"] + sections
        self._section_combo["values"] = sec_labels
        if self._section_var.get() not in sec_labels:
            self._section_var.set("All")

    # ------------------------------------------------------------------ #
    # Data loading and rendering                                           #
    # ------------------------------------------------------------------ #

    def _load_page(self) -> None:
        kwargs = self._get_filter_kwargs()
        conn = self.app.conn
        try:
            self._total_count = self.app.violation_repo.count_full(conn, **kwargs)
            self._rows = self.app.violation_repo.query_full(
                conn,
                limit=_PAGE_SIZE,
                offset=self._current_page * _PAGE_SIZE,
                **kwargs,
            )
        except Exception as exc:
            log.exception("Failed to load violations page")
            messagebox.showerror("Query Error", str(exc), parent=self)
            return
        self._render_table()
        self._update_pager()
        self._refresh_severity_strip()

    def _render_table(self) -> None:
        self._tree.delete(*self._tree.get_children())
        for row in self._rows:
            sev = row.get("severity", "")
            tag = _SEV_TAG.get(sev, "")
            values = (
                sev.upper()[:4],
                row.get("policy_name", ""),
                row.get("file_name", ""),
                row.get("owner_name") or row.get("owner_sid") or row.get("doc_creator") or row.get("doc_modifier") or "(unknown)",
                format_bytes(row.get("size_bytes") or 0),
                (row.get("mtime_utc") or "")[:10],
                row.get("section_name") or "",
                row.get("status", ""),
                str(row.get("run_id", "")),
            )
            self._tree.insert(
                "", "end", iid=str(row["violation_id"]), values=values, tags=(tag,)
            )
        if not self._rows:
            self._tree.insert("", "end",
                              values=("", "(no violations)", "", "", "", "", "", "", ""),
                              tags=("empty",))

    def _update_pager(self) -> None:
        total_pages = max(1, math.ceil(self._total_count / _PAGE_SIZE))
        current = self._current_page + 1
        self._page_label.config(
            text=f"Page {current} of {total_pages}  ({self._total_count:,} results)"
        )
        at_start = self._current_page == 0
        at_end = self._current_page >= total_pages - 1
        for btn in (self._btn_first, self._btn_prev):
            btn.state(["disabled"] if at_start else ["!disabled"])
        for btn in (self._btn_next, self._btn_last):
            btn.state(["disabled"] if at_end else ["!disabled"])

    # ------------------------------------------------------------------ #
    # Paging                                                               #
    # ------------------------------------------------------------------ #

    def _page_first(self) -> None:
        self._current_page = 0
        self._load_page()

    def _page_prev(self) -> None:
        if self._current_page > 0:
            self._current_page -= 1
            self._load_page()

    def _page_next(self) -> None:
        total_pages = max(1, math.ceil(self._total_count / _PAGE_SIZE))
        if self._current_page < total_pages - 1:
            self._current_page += 1
            self._load_page()

    def _page_last(self) -> None:
        total_pages = max(1, math.ceil(self._total_count / _PAGE_SIZE))
        self._current_page = total_pages - 1
        self._load_page()

    # ------------------------------------------------------------------ #
    # Selection                                                            #
    # ------------------------------------------------------------------ #

    def _selected_row(self) -> dict | None:
        sel = self._tree.selection()
        if not sel:
            return None
        vid = int(sel[0])
        for row in self._rows:
            if row["violation_id"] == vid:
                return row
        return None

    def _selected_rows(self) -> list[dict]:
        ids = {int(s) for s in self._tree.selection()}
        return [r for r in self._rows if r["violation_id"] in ids]

    def _on_select(self, _event=None) -> None:
        row = self._selected_row()
        if row is None:
            self._detail_path.config(text="Path: —")
            self._detail_reason.config(text="Reason: —")
            self._detail_note.config(text="Note: —")
            return
        self._detail_path.config(text=f"Path: {row.get('full_path', '')}")
        self._detail_reason.config(text=f"Reason: {row.get('reason', '')}")
        note = row.get("review_note") or ""
        reviewer = row.get("reviewer") or ""
        reviewed = (row.get("reviewed_at_utc") or "")[:16]
        if note or reviewer:
            parts = [f"Note: {note}"] if note else ["Note: —"]
            if reviewer:
                parts.append(f"  reviewed by {reviewer} at {reviewed}")
            self._detail_note.config(text="".join(parts))
        else:
            self._detail_note.config(text="Note: —")

    # ------------------------------------------------------------------ #
    # Actions                                                              #
    # ------------------------------------------------------------------ #

    def _open_folder(self) -> None:
        row = self._selected_row()
        if not row:
            messagebox.showinfo("No selection", "Select a violation first.", parent=self)
            return
        folder = os.path.dirname(row.get("full_path", ""))
        if not folder:
            messagebox.showwarning("No path", "Cannot determine containing folder.", parent=self)
            return
        try:
            os.startfile(folder)
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self)

    def _copy_path(self) -> None:
        row = self._selected_row()
        if not row:
            messagebox.showinfo("No selection", "Select a violation first.", parent=self)
            return
        path = row.get("full_path", "")
        self.clipboard_clear()
        self.clipboard_append(path)
        messagebox.showinfo("Copied", f"Copied to clipboard:\n{path}", parent=self)

    def _set_status(self, status: str) -> None:
        rows = self._selected_rows()
        if not rows:
            messagebox.showinfo("No selection", "Select one or more violations first.", parent=self)
            return
        conn = self.app.conn
        for row in rows:
            self.app.violation_repo.update_status(conn, row["violation_id"], status)
            self.app.review_repo.insert(
                conn, row["violation_id"], action_type=status, actor="user"
            )
        self._load_page()

    def _add_note(self) -> None:
        row = self._selected_row()
        if not row:
            messagebox.showinfo("No selection", "Select a violation first.", parent=self)
            return
        dialog = _NoteDialog(self, current_note=row.get("review_note") or "")
        note = dialog.result
        if note is None:
            return
        conn = self.app.conn
        self.app.violation_repo.update_status(
            conn,
            row["violation_id"],
            row.get("status", "open"),
            note=note,
        )
        self.app.review_repo.insert(
            conn, row["violation_id"], action_type="note", actor="user", note=note
        )
        self._load_page()

    def _on_right_click(self, event: tk.Event) -> None:
        item = self._tree.identify_row(event.y)
        if item:
            self._tree.selection_set(item)
            self._ctx_menu.tk_popup(event.x_root, event.y_root)

    def _open_action_dialog(self, status: str) -> None:
        rows = self._selected_rows()
        if not rows:
            messagebox.showinfo("No selection", "Select one or more violations first.", parent=self)
            return
        dlg = _ActionDialog(self, status=status, count=len(rows))
        if dlg.reason is None:
            return
        actor = (self.app.authenticated_user or {}).get("username", "user")
        conn = self.app.conn
        for row in rows:
            self.app.violation_repo.update_status(
                conn, row["violation_id"], status,
                reviewer=actor, note=dlg.reason,
            )
            self.app.review_repo.insert(
                conn, row["violation_id"], action_type=status,
                actor=actor, note=dlg.reason,
            )
        self._load_page()

    def _view_history(self) -> None:
        row = self._selected_row()
        if not row:
            messagebox.showinfo("No selection", "Select a violation first.", parent=self)
            return
        _ActionHistoryDialog(self, app=self.app, violation=row)

    def _export_csv(self) -> None:
        kwargs = self._get_filter_kwargs()
        conn = self.app.conn
        try:
            rows = self.app.violation_repo.query_full(
                conn, limit=100_000, offset=0, **kwargs
            )
        except Exception as exc:
            log.exception("Failed to export violations")
            messagebox.showerror("Query Error", str(exc), parent=self)
            return
        default_dir = self.app.get_setting("export_folder", "")
        dest = filedialog.asksaveasfilename(
            parent=self,
            title="Export Violations to CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialdir=default_dir or None,
        )
        if not dest:
            return
        try:
            count = export_violations_csv(rows, dest)
            messagebox.showinfo(
                "Exported", f"Exported {count:,} rows to:\n{dest}", parent=self
            )
        except Exception as exc:
            messagebox.showerror("Export Error", str(exc), parent=self)


# ---------------------------------------------------------------------------
# Note dialog
# ---------------------------------------------------------------------------

class _NoteDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, current_note: str = "") -> None:
        super().__init__(parent)
        self.title("Add / Edit Note")
        self.resizable(False, False)
        self.grab_set()
        self.result: str | None = None

        ttk.Label(self, text="Note:").pack(padx=8, pady=(8, 2), anchor="w")
        from shared_drive_manager.ui.theme import Theme
        self._text = tk.Text(self, width=52, height=5, wrap="word",
                             bg=Theme.ENTRY_BG, fg=Theme.TEXT,
                             insertbackground=Theme.CYAN,
                             selectbackground=Theme.SELECT, relief="flat")
        self._text.pack(padx=8, pady=2)
        if current_note:
            self._text.insert("1.0", current_note)

        btn_frm = ttk.Frame(self)
        btn_frm.pack(pady=8)
        ttk.Button(
            btn_frm, text="OK", command=self._ok, style="Accent.TButton"
        ).pack(side="left", padx=4)
        ttk.Button(btn_frm, text="Cancel", command=self.destroy).pack(
            side="left", padx=4
        )
        self.wait_window()

    def _ok(self) -> None:
        self.result = self._text.get("1.0", "end-1c").strip()
        self.destroy()


# ---------------------------------------------------------------------------
# Action dialog — status change with mandatory reason
# ---------------------------------------------------------------------------

class _ActionDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, status: str, count: int) -> None:
        super().__init__(parent)
        self.title(f"Confirm — Mark as {status.capitalize()}")
        self.resizable(False, False)
        self.grab_set()
        self.reason: str | None = None

        ttk.Label(
            self,
            text=f"Mark {count} violation(s) as '{status}'.\nA reason is required:",
        ).pack(padx=12, pady=(12, 4), anchor="w")

        self._text = tk.Text(
            self, width=52, height=4, wrap="word",
            bg=Theme.ENTRY_BG, fg=Theme.TEXT,
            insertbackground=Theme.CYAN,
            selectbackground=Theme.SELECT, relief="flat",
        )
        self._text.pack(padx=12, pady=4)
        self._text.bind("<KeyRelease>", self._on_key)

        self._warn_lbl = ttk.Label(self, text="Reason cannot be empty.", foreground=Theme.RED)
        self._warn_lbl.pack(padx=12, anchor="w")

        btn_frm = ttk.Frame(self)
        btn_frm.pack(pady=(4, 12))
        self._ok_btn = ttk.Button(
            btn_frm, text="Confirm", command=self._ok,
            style="Accent.TButton", state="disabled",
        )
        self._ok_btn.pack(side="left", padx=4)
        ttk.Button(btn_frm, text="Cancel", command=self.destroy).pack(side="left", padx=4)

        self.wait_window()

    def _on_key(self, _event=None) -> None:
        if self._text.get("1.0", "end-1c").strip():
            self._ok_btn.state(["!disabled"])
            self._warn_lbl.configure(text="")
        else:
            self._ok_btn.state(["disabled"])
            self._warn_lbl.configure(text="Reason cannot be empty.")

    def _ok(self) -> None:
        text = self._text.get("1.0", "end-1c").strip()
        if not text:
            return
        self.reason = text
        self.destroy()


# ---------------------------------------------------------------------------
# Action history dialog
# ---------------------------------------------------------------------------

class _ActionHistoryDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, app, violation: dict) -> None:
        super().__init__(parent)
        vid = violation["violation_id"]
        self.title(f"Action History — Violation #{vid}")
        self.geometry("700x360")
        self.grab_set()

        ttk.Label(
            self,
            text=f"File: {violation.get('file_name', '')}",
            anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 2))
        ttk.Label(
            self,
            text=(
                f"Policy: {violation.get('policy_name', '')} "
                f"| Severity: {violation.get('severity', '')} "
                f"| Current status: {violation.get('status', '')}"
            ),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 6))

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=12, pady=(0, 4))

        cols = ("timestamp", "action", "actor", "note")
        tree = ttk.Treeview(frm, columns=cols, show="headings", selectmode="browse")
        headings = {
            "timestamp": ("Timestamp (UTC)", 145),
            "action":    ("Action", 100),
            "actor":     ("Actor", 120),
            "note":      ("Note / Reason", 290),
        }
        for col, (label, width) in headings.items():
            tree.heading(col, text=label)
            tree.column(col, width=width, minwidth=50)

        vsb = ttk.Scrollbar(frm, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        actions = app.review_repo.list_for_violation(app.get_db(), vid)
        for act in actions:
            tree.insert(
                "", "end",
                values=(
                    (act.get("created_at_utc") or "")[:19],
                    act.get("action_type", ""),
                    act.get("actor", ""),
                    act.get("note") or "",
                ),
            )
        if not actions:
            tree.insert("", "end", values=("—", "(no history yet)", "", ""))

        ttk.Button(self, text="Close", command=self.destroy).pack(pady=(0, 10))
        self.wait_window()
