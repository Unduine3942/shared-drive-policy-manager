"""Duplicate File Detection page — scan, group, and export duplicate files."""
from __future__ import annotations

import csv
import logging
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
import tkinter as tk
from tkinter import ttk

from shared_drive_manager.ui.theme import Theme

log = logging.getLogger(__name__)

_HASH_LABELS = {
    "name_size": "Name + Size (instant)",
    "partial":   "Partial Content — first 4 MB (fast)",
    "full":      "Full Content SHA-256 (accurate)",
}


class DuplicatePage(tk.Frame):
    def __init__(self, parent: tk.Widget, app) -> None:
        super().__init__(parent, bg=Theme.BG)
        self._app = app
        self._cancel_event = threading.Event()
        self._job_thread: threading.Thread | None = None
        self._groups: list[list[dict]] = []
        self._build()

    # ── Layout ──────────────────────────────────────────────────────────

    def _build(self) -> None:
        # Header
        hdr = tk.Frame(self, bg=Theme.PANEL, pady=Theme.PAD_MD)
        hdr.pack(fill="x", padx=Theme.PAD_LG, pady=(Theme.PAD_LG, 0))
        tk.Label(
            hdr, text="DUPLICATE FILE DETECTION",
            font=Theme.FONT_H2, fg=Theme.CYAN, bg=Theme.PANEL,
        ).pack(side="left", padx=Theme.PAD_LG)

        # Controls bar
        ctrl = tk.Frame(self, bg=Theme.PANEL_2, pady=Theme.PAD_MD)
        ctrl.pack(fill="x", padx=Theme.PAD_LG, pady=(2, 0))

        tk.Label(ctrl, text="Hash mode:", fg=Theme.MUTED, bg=Theme.PANEL_2,
                 font=Theme.FONT_BODY).pack(side="left", padx=(Theme.PAD_LG, 4))
        self._hash_var = tk.StringVar(value="name_size")
        combo = ttk.Combobox(
            ctrl, textvariable=self._hash_var, state="readonly", width=34,
            values=list(_HASH_LABELS.values()),
        )
        combo.pack(side="left", padx=(0, Theme.PAD_LG))
        combo.set(_HASH_LABELS["name_size"])

        tk.Label(ctrl, text="Scope:", fg=Theme.MUTED, bg=Theme.PANEL_2,
                 font=Theme.FONT_BODY).pack(side="left", padx=(0, 4))
        self._scope_var = tk.StringVar(value="All roots")
        self._scope_combo = ttk.Combobox(
            ctrl, textvariable=self._scope_var, state="readonly", width=22,
        )
        self._scope_combo.pack(side="left", padx=(0, Theme.PAD_LG))

        self._scan_btn = tk.Button(
            ctrl, text="Find Duplicates", font=Theme.FONT_BODY_SB,
            bg=Theme.CYAN, fg=Theme.BG, relief="flat", padx=10,
            command=self._start_scan,
        )
        self._scan_btn.pack(side="left", padx=(0, Theme.PAD_MD))

        self._cancel_btn = tk.Button(
            ctrl, text="Cancel", font=Theme.FONT_BODY_SB,
            bg=Theme.AMBER, fg=Theme.BG, relief="flat", padx=10,
            state="disabled", command=self._cancel_scan,
        )
        self._cancel_btn.pack(side="left", padx=(0, Theme.PAD_LG))

        self._export_btn = tk.Button(
            ctrl, text="Export CSV", font=Theme.FONT_BODY_SB,
            bg=Theme.PANEL_3, fg=Theme.TEXT, relief="flat", padx=10,
            state="disabled", command=self._export_csv,
        )
        self._export_btn.pack(side="right", padx=Theme.PAD_LG)

        # Progress bar + status
        prog_frame = tk.Frame(self, bg=Theme.BG)
        prog_frame.pack(fill="x", padx=Theme.PAD_LG, pady=(4, 0))
        self._progress = ttk.Progressbar(prog_frame, mode="determinate")
        self._progress.pack(fill="x", side="left", expand=True, padx=(0, Theme.PAD_MD))
        self._status_label = tk.Label(
            prog_frame, text="", fg=Theme.MUTED, bg=Theme.BG,
            font=Theme.FONT_CAPTION, width=30, anchor="w",
        )
        self._status_label.pack(side="left")

        # Summary bar
        self._summary_var = tk.StringVar(value="No scan run yet.")
        tk.Label(
            self, textvariable=self._summary_var,
            fg=Theme.MUTED, bg=Theme.BG, font=Theme.FONT_CAPTION,
            anchor="w",
        ).pack(fill="x", padx=Theme.PAD_LG, pady=(2, 0))

        # Results treeview
        tree_frame = tk.Frame(self, bg=Theme.BG)
        tree_frame.pack(fill="both", expand=True, padx=Theme.PAD_LG, pady=Theme.PAD_MD)

        cols = ("group", "path", "size", "owner", "section", "computed_at")
        self._tree = ttk.Treeview(
            tree_frame, columns=cols, show="headings", selectmode="extended",
        )
        headings = {
            "group":       ("Group", 60),
            "path":        ("Full Path", 480),
            "size":        ("Size", 90),
            "owner":       ("Owner", 140),
            "section":     ("Section", 120),
            "computed_at": ("Hash Computed", 140),
        }
        for col, (label, width) in headings.items():
            self._tree.heading(col, text=label,
                               command=lambda c=col: self._sort_by(c))
            self._tree.column(col, width=width, minwidth=50)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                            command=self._tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal",
                            command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self._tree.tag_configure("group_a", background=Theme.PANEL)
        self._tree.tag_configure("group_b", background=Theme.PANEL_2)

        self._tree.bind("<Button-3>", self._on_right_click)

        self._ctx_menu = tk.Menu(self, tearoff=0, bg=Theme.PANEL,
                                 fg=Theme.TEXT, activebackground=Theme.SELECT)
        self._ctx_menu.add_command(label="Copy Path", command=self._copy_path)
        self._ctx_menu.add_command(label="Open Folder", command=self._open_folder)

    def on_tab_activate(self) -> None:
        self._refresh_scope_combo()

    # ── Scope combo ──────────────────────────────────────────────────────

    def _refresh_scope_combo(self) -> None:
        conn = self._app.get_db()
        roots = self._app.scan_root_repo.list_active(conn)
        options = ["All roots"] + [r["label"] or r["root_path"] for r in roots]
        self._scope_combo["values"] = options
        if self._scope_var.get() not in options:
            self._scope_var.set("All roots")
        self._roots = {(r["label"] or r["root_path"]): r["root_id"] for r in roots}

    # ── Scanning ─────────────────────────────────────────────────────────

    def _resolve_hash_type(self) -> str:
        label = self._hash_var.get()
        for k, v in _HASH_LABELS.items():
            if v == label:
                return k
        return "name_size"

    def _start_scan(self) -> None:
        if self._job_thread and self._job_thread.is_alive():
            return
        self._cancel_event.clear()
        self._scan_btn.configure(state="disabled")
        self._cancel_btn.configure(state="normal")
        self._export_btn.configure(state="disabled")
        self._progress["value"] = 0
        self._status_label.configure(text="Querying files…")
        self._summary_var.set("")
        for item in self._tree.get_children():
            self._tree.delete(item)

        hash_type = self._resolve_hash_type()
        scope = self._scope_var.get()
        root_id: int | None = None
        if scope != "All roots":
            root_id = self._roots.get(scope)

        self._job_thread = threading.Thread(
            target=self._scan_worker,
            args=(hash_type, root_id),
            daemon=True,
        )
        self._job_thread.start()

    def _scan_worker(self, hash_type: str, root_id: int | None) -> None:
        from shared_drive_manager.core.hasher import run_hash_job

        conn = self._app.get_db()

        # Fetch candidate files (skip zero-byte for partial/full)
        query = "SELECT file_id, full_path, name, size_bytes FROM file_inventory WHERE is_deleted = 0"
        params: list = []
        if root_id is not None:
            query += " AND root_id = ?"
            params.append(root_id)
        if hash_type in ("partial", "full"):
            query += " AND size_bytes > 0"

        rows = conn.execute(query, params).fetchall()
        rows = [dict(r) for r in rows]
        total = len(rows)
        self._after(lambda: self._status_label.configure(
            text=f"Hashing {total:,} files…"))

        def progress(done: int, tot: int) -> None:
            pct = int(done / tot * 100) if tot else 0
            self._after(lambda p=pct, d=done, t=tot: (
                self._progress.__setitem__("value", p),
                self._status_label.configure(text=f"{d:,} / {t:,}"),
            ))

        results = run_hash_job(rows, hash_type, progress_cb=progress,
                               cancel_event=self._cancel_event)

        if self._cancel_event.is_set():
            self._after(self._scan_done_cancelled)
            return

        # Persist hashes in batches
        self._after(lambda: self._status_label.configure(text="Saving hashes…"))
        BATCH = 500
        for i in range(0, len(results), BATCH):
            batch = results[i: i + BATCH]
            for file_id, ht, hv in batch:
                self._app.file_hash_repo.upsert(conn, file_id, ht, hv)
            conn.commit()

        # Load duplicates
        root_ids = [root_id] if root_id else None
        dups = self._app.file_hash_repo.get_duplicates(conn, hash_type, root_ids)
        self._after(lambda d=dups: self._populate_results(d, hash_type, total))

    def _scan_done_cancelled(self) -> None:
        self._scan_btn.configure(state="normal")
        self._cancel_btn.configure(state="disabled")
        self._status_label.configure(text="Cancelled.")

    def _cancel_scan(self) -> None:
        self._cancel_event.set()
        self._cancel_btn.configure(state="disabled")

    # ── Results ──────────────────────────────────────────────────────────

    def _populate_results(self, rows: list[dict], hash_type: str, total_files: int) -> None:
        self._scan_btn.configure(state="normal")
        self._cancel_btn.configure(state="disabled")
        self._status_label.configure(text="Done.")

        for item in self._tree.get_children():
            self._tree.delete(item)
        self._groups = []

        # Group rows by hash_value
        groups: dict[str, list[dict]] = {}
        for row in rows:
            groups.setdefault(row["hash_value"], []).append(row)

        dup_groups = [g for g in groups.values() if len(g) > 1]
        dup_groups.sort(key=lambda g: -g[0]["size_bytes"])
        self._groups = dup_groups

        total_wasted = sum(
            g[0]["size_bytes"] * (len(g) - 1) for g in dup_groups
        )

        tag_cycle = ("group_a", "group_b")
        for g_idx, group in enumerate(dup_groups):
            tag = tag_cycle[g_idx % 2]
            for row in group:
                self._tree.insert(
                    "", "end",
                    values=(
                        f"G{g_idx + 1}",
                        row["full_path"],
                        _fmt_size(row["size_bytes"]),
                        row["owner_name"] or "",
                        row["section_name"] or "",
                        row["computed_at"][:16] if row.get("computed_at") else "",
                    ),
                    tags=(tag,),
                )

        self._summary_var.set(
            f"{len(dup_groups)} duplicate group(s) across {sum(len(g) for g in dup_groups)} files "
            f"— approx {_fmt_size(total_wasted)} reclaimable | {total_files:,} files scanned"
        )
        if dup_groups:
            self._export_btn.configure(state="normal")

    # ── Context menu ─────────────────────────────────────────────────────

    def _on_right_click(self, event: tk.Event) -> None:
        item = self._tree.identify_row(event.y)
        if item:
            self._tree.selection_set(item)
            self._ctx_menu.tk_popup(event.x_root, event.y_root)

    def _selected_path(self) -> str | None:
        sel = self._tree.selection()
        if not sel:
            return None
        return self._tree.item(sel[0], "values")[1]

    def _copy_path(self) -> None:
        path = self._selected_path()
        if path:
            self.clipboard_clear()
            self.clipboard_append(path)

    def _open_folder(self) -> None:
        import subprocess
        path = self._selected_path()
        if path:
            folder = str(Path(path).parent)
            try:
                subprocess.Popen(["explorer", "/select,", path])
            except Exception:
                try:
                    subprocess.Popen(["explorer", folder])
                except Exception:
                    pass

    # ── Sort ─────────────────────────────────────────────────────────────

    def _sort_by(self, col: str) -> None:
        data = [(self._tree.set(c, col), c) for c in self._tree.get_children("")]
        data.sort(key=lambda t: t[0].lower())
        for idx, (_, item) in enumerate(data):
            self._tree.move(item, "", idx)

    # ── Export ───────────────────────────────────────────────────────────

    def _export_csv(self) -> None:
        if not self._groups:
            return
        default_dir = self._app.get_setting("export_folder", str(Path.home()))
        path = filedialog.asksaveasfilename(
            title="Export Duplicates",
            initialdir=default_dir,
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(["Group", "Full Path", "Size", "Owner", "Section", "Hash Computed"])
                for g_idx, group in enumerate(self._groups):
                    for row in group:
                        writer.writerow([
                            f"G{g_idx + 1}",
                            row["full_path"],
                            row["size_bytes"],
                            row.get("owner_name") or "",
                            row.get("section_name") or "",
                            row.get("computed_at") or "",
                        ])
            messagebox.showinfo("Export Complete", f"Saved to:\n{path}")
        except Exception as exc:
            messagebox.showerror("Export Failed", str(exc))

    # ── Utilities ────────────────────────────────────────────────────────

    def _after(self, fn) -> None:
        self.after(0, fn)


def _fmt_size(n: int | None) -> str:
    if n is None:
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"
