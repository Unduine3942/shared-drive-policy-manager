"""Owner/Creator Accountability Index — ranked violations by owner with contact info."""
from __future__ import annotations

import csv
import logging
from pathlib import Path
from tkinter import filedialog, messagebox
import tkinter as tk
from tkinter import ttk

from shared_drive_manager.ui.theme import Theme

log = logging.getLogger(__name__)


class OwnerAccountabilityPage(tk.Frame):
    def __init__(self, parent: tk.Widget, app) -> None:
        super().__init__(parent, bg=Theme.BG)
        self._app = app
        self._rows: list[dict] = []
        self._build()

    # ── Layout ──────────────────────────────────────────────────────────

    def _build(self) -> None:
        # Header
        hdr = tk.Frame(self, bg=Theme.PANEL, pady=Theme.PAD_MD)
        hdr.pack(fill="x", padx=Theme.PAD_LG, pady=(Theme.PAD_LG, 0))
        tk.Label(
            hdr, text="OWNER / CREATOR ACCOUNTABILITY INDEX",
            font=Theme.FONT_H2, fg=Theme.CYAN, bg=Theme.PANEL,
        ).pack(side="left", padx=Theme.PAD_LG)

        tk.Button(
            hdr, text="Refresh", font=Theme.FONT_BODY_SB,
            bg=Theme.PANEL_3, fg=Theme.TEXT, relief="flat", padx=8,
            command=self._load,
        ).pack(side="right", padx=Theme.PAD_LG)

        tk.Button(
            hdr, text="Export CSV", font=Theme.FONT_BODY_SB,
            bg=Theme.PANEL_3, fg=Theme.TEXT, relief="flat", padx=8,
            command=self._export_csv,
        ).pack(side="right", padx=(0, 4))

        # Summary metrics bar
        metrics = tk.Frame(self, bg=Theme.PANEL_2, pady=6)
        metrics.pack(fill="x", padx=Theme.PAD_LG, pady=(2, 0))
        self._metric_owners   = self._metric_label(metrics, "Owners with violations", "0")
        self._metric_open     = self._metric_label(metrics, "Open violations", "0")
        self._metric_critical = self._metric_label(metrics, "Critical violations", "0")
        self._metric_bytes    = self._metric_label(metrics, "Total flagged data", "0 B")

        # Contact editor panel (collapsible)
        self._editor_visible = False
        self._editor_frame = tk.LabelFrame(
            self, text="Edit Contact Info",
            fg=Theme.MUTED, bg=Theme.PANEL_2,
            font=Theme.FONT_CAPTION,
        )
        self._build_contact_editor(self._editor_frame)

        # Ranked treeview
        tree_frame = tk.Frame(self, bg=Theme.BG)
        tree_frame.pack(fill="both", expand=True, padx=Theme.PAD_LG, pady=Theme.PAD_MD)

        cols = ("rank", "owner", "display", "email", "dept",
                "open", "total", "critical", "total_bytes")
        self._tree = ttk.Treeview(
            tree_frame, columns=cols, show="headings", selectmode="browse",
        )
        headings = {
            "rank":        ("#", 35),
            "owner":       ("Owner / SID", 180),
            "display":     ("Display Name", 140),
            "email":       ("Email", 180),
            "dept":        ("Department", 120),
            "open":        ("Open", 65),
            "total":       ("Total", 65),
            "critical":    ("Critical", 70),
            "total_bytes": ("Flagged Data", 110),
        }
        for col, (label, width) in headings.items():
            self._tree.heading(col, text=label,
                               command=lambda c=col: self._sort_by(c))
            self._tree.column(col, width=width, minwidth=40)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                            command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.bind("<Double-1>", self._on_double_click)

        # Status bar
        self._status_var = tk.StringVar(value="")
        tk.Label(
            self, textvariable=self._status_var,
            fg=Theme.MUTED, bg=Theme.BG, font=Theme.FONT_CAPTION, anchor="w",
        ).pack(fill="x", padx=Theme.PAD_LG, pady=(0, Theme.PAD_SM))

    def _metric_label(self, parent: tk.Frame, title: str, value: str) -> tk.Label:
        frame = tk.Frame(parent, bg=Theme.PANEL_2)
        frame.pack(side="left", padx=Theme.PAD_LG, pady=4)
        tk.Label(frame, text=title, fg=Theme.DIM, bg=Theme.PANEL_2,
                 font=Theme.FONT_CAPTION).pack()
        lbl = tk.Label(frame, text=value, fg=Theme.TEXT, bg=Theme.PANEL_2,
                       font=Theme.FONT_H3)
        lbl.pack()
        return lbl

    def _build_contact_editor(self, parent: tk.Frame) -> None:
        parent.configure(padx=Theme.PAD_MD, pady=Theme.PAD_SM, bg=Theme.PANEL_2)
        grid = tk.Frame(parent, bg=Theme.PANEL_2)
        grid.pack(fill="x")

        fields = [
            ("Owner (key):", "_ef_owner"),
            ("Display Name:", "_ef_display"),
            ("Email:", "_ef_email"),
            ("Department:", "_ef_dept"),
            ("Notes:", "_ef_notes"),
        ]
        for row, (label, attr) in enumerate(fields):
            tk.Label(grid, text=label, fg=Theme.MUTED, bg=Theme.PANEL_2,
                     font=Theme.FONT_BODY, anchor="e", width=14).grid(
                row=row, column=0, sticky="e", pady=2, padx=(0, 4))
            var = tk.StringVar()
            entry = ttk.Entry(grid, textvariable=var, width=40)
            entry.grid(row=row, column=1, sticky="w", pady=2)
            setattr(self, attr, var)

        self._ef_owner_widget = None  # the Entry for owner is read-only after selection

        btn_row = tk.Frame(parent, bg=Theme.PANEL_2)
        btn_row.pack(fill="x", pady=(4, 0))
        tk.Button(
            btn_row, text="Save Contact", font=Theme.FONT_BODY_SB,
            bg=Theme.GREEN, fg=Theme.BG, relief="flat", padx=8,
            command=self._save_contact,
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            btn_row, text="Clear / Hide", font=Theme.FONT_BODY_SB,
            bg=Theme.PANEL_3, fg=Theme.TEXT, relief="flat", padx=8,
            command=self._hide_editor,
        ).pack(side="left")

    # ── Data loading ─────────────────────────────────────────────────────

    def on_tab_activate(self) -> None:
        self._load()

    def _load(self) -> None:
        conn = self._app.get_db()
        self._rows = self._app.owner_contact_repo.get_violation_summary(conn)
        self._populate()

    def _populate(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)

        total_open = total_crit = total_bytes_sum = 0

        for rank, row in enumerate(self._rows, 1):
            open_v = row.get("open_violations") or 0
            crit_v = row.get("critical_violations") or 0
            total_v = row.get("total_violations") or 0
            tb = row.get("total_bytes") or 0
            total_open += open_v
            total_crit += crit_v
            total_bytes_sum += tb

            tag = "critical_row" if crit_v > 0 else ("warn_row" if open_v > 0 else "")
            self._tree.insert(
                "", "end",
                values=(
                    rank,
                    row.get("owner_name") or "(unknown)",
                    row.get("display_name") or "",
                    row.get("email") or "",
                    row.get("department") or "",
                    open_v,
                    total_v,
                    crit_v,
                    _fmt_size(tb),
                ),
                tags=(tag,),
            )

        self._tree.tag_configure("critical_row", foreground=Theme.RED)
        self._tree.tag_configure("warn_row",     foreground=Theme.AMBER)

        self._metric_owners.configure(text=str(len(self._rows)))
        self._metric_open.configure(text=str(total_open))
        self._metric_critical.configure(text=str(total_crit))
        self._metric_bytes.configure(text=_fmt_size(total_bytes_sum))
        self._status_var.set(
            f"{len(self._rows)} owner(s) — double-click a row to edit contact info"
        )

    # ── Selection / editor ───────────────────────────────────────────────

    def _on_select(self, _event=None) -> None:
        pass

    def _on_double_click(self, _event=None) -> None:
        sel = self._tree.selection()
        if not sel:
            return
        values = self._tree.item(sel[0], "values")
        owner = values[1]

        conn = self._app.get_db()
        existing = self._app.owner_contact_repo.get_by_owner(conn, owner)

        self._ef_owner.set(owner)
        self._ef_display.set(existing.get("display_name") or "" if existing else "")
        self._ef_email.set(existing.get("email") or "" if existing else "")
        self._ef_dept.set(existing.get("department") or "" if existing else "")
        self._ef_notes.set(existing.get("notes") or "" if existing else "")

        if not self._editor_visible:
            self._editor_frame.pack(
                fill="x", padx=Theme.PAD_LG, pady=(4, 0), before=self._tree.master,
            )
            self._editor_visible = True

    def _hide_editor(self) -> None:
        self._editor_frame.pack_forget()
        self._editor_visible = False

    def _save_contact(self) -> None:
        owner = self._ef_owner.get().strip()
        if not owner:
            messagebox.showwarning("Validation", "Owner name cannot be empty.")
            return
        conn = self._app.get_db()
        self._app.owner_contact_repo.upsert(
            conn,
            owner_name=owner,
            display_name=self._ef_display.get().strip() or None,
            email=self._ef_email.get().strip() or None,
            department=self._ef_dept.get().strip() or None,
            notes=self._ef_notes.get().strip() or None,
        )
        self._hide_editor()
        self._load()
        self._status_var.set(f"Contact info saved for: {owner}")

    # ── Sort ─────────────────────────────────────────────────────────────

    def _sort_by(self, col: str) -> None:
        numeric = {"rank", "open", "total", "critical"}
        data = [(self._tree.set(c, col), c) for c in self._tree.get_children("")]
        try:
            if col in numeric:
                data.sort(key=lambda t: int(t[0]) if t[0] else 0, reverse=True)
            else:
                data.sort(key=lambda t: t[0].lower())
        except Exception:
            data.sort(key=lambda t: t[0].lower())
        for idx, (_, item) in enumerate(data):
            self._tree.move(item, "", idx)

    # ── Export ───────────────────────────────────────────────────────────

    def _export_csv(self) -> None:
        if not self._rows:
            messagebox.showinfo("Nothing to export", "Run a scan first.")
            return
        default_dir = self._app.get_setting("export_folder", str(Path.home()))
        path = filedialog.asksaveasfilename(
            title="Export Owner Index",
            initialdir=default_dir,
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow([
                    "Rank", "Owner", "Display Name", "Email", "Department",
                    "Open Violations", "Total Violations", "Critical Violations",
                    "Total Flagged Bytes",
                ])
                for rank, row in enumerate(self._rows, 1):
                    writer.writerow([
                        rank,
                        row.get("owner_name") or "",
                        row.get("display_name") or "",
                        row.get("email") or "",
                        row.get("department") or "",
                        row.get("open_violations") or 0,
                        row.get("total_violations") or 0,
                        row.get("critical_violations") or 0,
                        row.get("total_bytes") or 0,
                    ])
            messagebox.showinfo("Export Complete", f"Saved to:\n{path}")
        except Exception as exc:
            messagebox.showerror("Export Failed", str(exc))


def _fmt_size(n: int | None) -> str:
    if not n:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"
