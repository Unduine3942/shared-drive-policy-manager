"""Policy configuration page — CRUD for policies and rules."""
from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Callable

from shared_drive_manager.core.policy_engine import NO_VALUE_OPS, validate_rule_value
from shared_drive_manager.ui.theme import Theme
from shared_drive_manager.ui.widgets import section_header, separator

if TYPE_CHECKING:
    from shared_drive_manager.app import Application

# ---------------------------------------------------------------------------
# Field / operator metadata
# ---------------------------------------------------------------------------

FIELD_NAMES: list[str] = [
    "name", "extension", "full_path", "parent_path", "section_name",
    "size_bytes", "ctime_utc", "mtime_utc", "atime_utc",
    "owner_name", "owner_sid", "path_depth", "path_length", "is_empty",
]

_FIELD_TYPE: dict[str, str] = {
    "name": "string",
    "extension": "string",
    "full_path": "string",
    "parent_path": "string",
    "section_name": "string_nullable",
    "size_bytes": "numeric",
    "ctime_utc": "date",
    "mtime_utc": "date",
    "atime_utc": "date",
    "owner_name": "string_nullable",
    "owner_sid": "string_nullable",
    "path_depth": "numeric",
    "path_length": "numeric",
    "is_empty": "boolean",
}

_STRING_OPS = [
    "equals", "not_equals", "contains", "starts_with", "ends_with",
    "glob", "regex", "in", "not_in",
]
_NULLABLE_OPS = _STRING_OPS + ["is_missing", "is_not_missing"]
_NUMERIC_OPS = ["gt", "gte", "lt", "lte", "between"]
_DATE_OPS = ["before", "after", "older_than_days", "newer_than_days"]
_BOOL_OPS = ["is_true", "is_false"]

_OPERATORS_FOR_TYPE: dict[str, list[str]] = {
    "string": _STRING_OPS,
    "string_nullable": _NULLABLE_OPS,
    "numeric": _NUMERIC_OPS,
    "date": _DATE_OPS,
    "boolean": _BOOL_OPS,
}

_VALUE_HINTS: dict[str, str] = {
    "between": "min, max  e.g. 100, 5368709120",
    "in": "val1, val2, val3  (comma-separated)",
    "not_in": "val1, val2, val3  (comma-separated)",
    "before": "YYYY-MM-DD",
    "after": "YYYY-MM-DD",
    "older_than_days": "number of days",
    "newer_than_days": "number of days",
    "gt": "number",
    "gte": "number",
    "lt": "number",
    "lte": "number",
}

_SEVERITIES = ["info", "warning", "critical"]
_MATCH_MODES = ["all", "any"]


# ---------------------------------------------------------------------------
# Value encoding / display helpers
# ---------------------------------------------------------------------------

def _encode_value(operator: str, text: str) -> str:
    """Convert user-entered text to a JSON string for DB storage."""
    if operator in NO_VALUE_OPS:
        return "null"
    if operator in ("in", "not_in"):
        items = [v.strip() for v in text.split(",") if v.strip()]
        return json.dumps(items)
    if operator == "between":
        lo, hi = [p.strip() for p in text.split(",")]
        return json.dumps([float(lo), float(hi)])
    if operator in ("gt", "gte", "lt", "lte", "older_than_days", "newer_than_days"):
        return json.dumps(float(text.strip()))
    return json.dumps(text.strip())


def _display_value(value_json: str) -> str:
    try:
        v = json.loads(value_json)
    except (json.JSONDecodeError, TypeError):
        return str(value_json)
    if v is None:
        return ""
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    return str(v)


# ---------------------------------------------------------------------------
# PolicyPage
# ---------------------------------------------------------------------------

class PolicyPage(ttk.Frame):
    def __init__(self, parent: tk.Widget, app: "Application") -> None:
        super().__init__(parent)
        self.app = app
        self._editing_policy_id: int | None = None
        self._rules_buffer: list[dict] = []
        self._build()
        self._refresh_policy_list()

    # ── Layout ──────────────────────────────────────────────────────────────

    def _build(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.pack(side="top", fill="x", padx=6, pady=(6, 2))
        ttk.Button(toolbar, text="+ New Policy", command=self._new_policy).pack(side="left")

        pane = ttk.PanedWindow(self, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=6, pady=(2, 6))

        left = ttk.Frame(pane)
        right = ttk.Frame(pane)
        self._build_left(left)
        self._build_right(right)
        pane.add(left, weight=1)
        pane.add(right, weight=2)

    def _build_left(self, parent: ttk.Frame) -> None:
        section_header(parent, "Policies")

        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)

        cols = ("name", "severity", "on", "rules")
        self._policy_tree = ttk.Treeview(
            frame, columns=cols, show="headings",
            selectmode="browse", height=24,
        )
        self._policy_tree.heading("name", text="Name")
        self._policy_tree.heading("severity", text="Severity")
        self._policy_tree.heading("on", text="On")
        self._policy_tree.heading("rules", text="#")
        self._policy_tree.column("name", width=170, stretch=True)
        self._policy_tree.column("severity", width=70, anchor="center", stretch=False)
        self._policy_tree.column("on", width=30, anchor="center", stretch=False)
        self._policy_tree.column("rules", width=28, anchor="center", stretch=False)

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self._policy_tree.yview)
        self._policy_tree.configure(yscrollcommand=vsb.set)
        self._policy_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        self._policy_tree.tag_configure("sev_critical", foreground=Theme.RED)
        self._policy_tree.tag_configure("sev_warning", foreground=Theme.AMBER)
        self._policy_tree.tag_configure("sev_info", foreground=Theme.BLUE)
        self._policy_tree.tag_configure("empty", foreground=Theme.MUTED)

        self._policy_tree.bind("<<TreeviewSelect>>", self._on_policy_select)

    def _build_right(self, parent: ttk.Frame) -> None:
        inner = ttk.Frame(parent)
        inner.pack(fill="both", expand=True)
        self._build_policy_form(inner)
        self._build_rules_section(inner)
        self._build_action_buttons(inner)

    def _build_policy_form(self, parent: ttk.Frame) -> None:
        section_header(parent, "Policy Details")

        self._name_var = tk.StringVar()
        self._desc_var = tk.StringVar()
        self._severity_var = tk.StringVar(value="warning")
        self._match_mode_var = tk.StringVar(value="all")
        self._scope_var = tk.StringVar()
        self._enabled_var = tk.BooleanVar(value=False)

        def _row(label: str) -> ttk.Frame:
            r = ttk.Frame(parent)
            r.pack(anchor="w", fill="x", pady=1, padx=6)
            if label:
                ttk.Label(r, text=label, width=18, anchor="w").pack(side="left")
            return r

        ttk.Entry(_row("Name:"), textvariable=self._name_var, width=40).pack(side="left")
        ttk.Entry(_row("Description:"), textvariable=self._desc_var, width=40).pack(side="left")
        ttk.Combobox(
            _row("Severity:"), textvariable=self._severity_var,
            values=_SEVERITIES, state="readonly", width=12,
        ).pack(side="left")
        ttk.Combobox(
            _row("Match Mode:"), textvariable=self._match_mode_var,
            values=_MATCH_MODES, state="readonly", width=8,
        ).pack(side="left")

        scope_row = _row("Scope Prefixes:")
        ttk.Entry(scope_row, textvariable=self._scope_var, width=40).pack(side="left")

        ttk.Label(
            parent,
            text="  comma-separated path prefixes that limit where this policy applies  (blank = all paths)",
            font=("", 8), foreground=Theme.MUTED,
        ).pack(anchor="w", padx=6)

        ttk.Checkbutton(
            _row(""), text="Enabled", variable=self._enabled_var,
        ).pack(side="left")

    def _build_rules_section(self, parent: ttk.Frame) -> None:
        separator(parent)
        section_header(parent, "Rules")

        tree_frame = ttk.Frame(parent)
        tree_frame.pack(anchor="w", fill="x", padx=6, pady=2)

        cols = ("field", "operator", "value", "cs")
        self._rule_tree = ttk.Treeview(
            tree_frame, columns=cols, show="headings",
            selectmode="browse", height=8,
        )
        self._rule_tree.heading("field", text="Field")
        self._rule_tree.heading("operator", text="Operator")
        self._rule_tree.heading("value", text="Value")
        self._rule_tree.heading("cs", text="CS")
        self._rule_tree.column("field", width=130, stretch=True)
        self._rule_tree.column("operator", width=140, stretch=True)
        self._rule_tree.column("value", width=180, stretch=True)
        self._rule_tree.column("cs", width=28, anchor="center", stretch=False)

        rule_vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._rule_tree.yview)
        self._rule_tree.configure(yscrollcommand=rule_vsb.set)
        self._rule_tree.pack(side="left", fill="both", expand=True)
        rule_vsb.pack(side="left", fill="y")
        self._rule_tree.tag_configure("empty", foreground=Theme.MUTED)

        btn_row = ttk.Frame(parent)
        btn_row.pack(anchor="w", padx=6, pady=2)
        ttk.Button(btn_row, text="Add Rule", command=self._add_rule).pack(side="left", padx=(0, 4))
        ttk.Button(btn_row, text="Delete Rule", command=self._delete_rule).pack(side="left", padx=(0, 12))
        tk.Button(
            btn_row, text="? Field & Operator Help",
            bg=Theme.PANEL_2, fg=Theme.CYAN,
            font=("Segoe UI", 9), relief="flat",
            padx=8, pady=2, cursor="hand2",
            activebackground=Theme.PANEL_3, activeforeground=Theme.TEXT,
            command=PolicyHelpDialog.open,
        ).pack(side="left")

    def _build_action_buttons(self, parent: ttk.Frame) -> None:
        separator(parent)
        btn_row = ttk.Frame(parent)
        btn_row.pack(anchor="w", padx=6, pady=6)

        role = (self.app.authenticated_user or {}).get("role", "viewer")
        if role == "secret_admin":
            ttk.Button(
                btn_row, text="Save Policy", command=self._save_policy,
                style="Accent.TButton",
            ).pack(side="left", padx=(0, 8))
            ttk.Button(btn_row, text="Delete Policy", command=self._delete_policy).pack(side="left", padx=(0, 12))
            self._pending_btn = tk.Button(
                btn_row, text="Pending Approvals (0)",
                bg=Theme.AMBER, fg=Theme.BG,
                font=Theme.FONT_BODY_SB, relief="flat", padx=8,
                command=self._open_approvals_dialog,
            )
            self._pending_btn.pack(side="left")
        elif role == "admin":
            ttk.Button(
                btn_row, text="Submit for Approval", command=self._submit_draft,
                style="Accent.TButton",
            ).pack(side="left", padx=(0, 8))
            ttk.Button(btn_row, text="Delete Policy", command=self._delete_policy).pack(side="left")
            self._pending_btn = None
        else:
            self._pending_btn = None

    # ── Data helpers ─────────────────────────────────────────────────────────

    def _refresh_policy_list(self) -> None:
        self._policy_tree.delete(*self._policy_tree.get_children())
        policies = self.app.policy_repo.list_all(self.app.conn)
        for p in policies:
            rule_count = len(self.app.rule_repo.list_for_policy(self.app.conn, p["policy_id"]))
            sev_tag = f"sev_{p['severity']}"
            self._policy_tree.insert(
                "", "end",
                iid=str(p["policy_id"]),
                values=(
                    p["name"],
                    p["severity"],
                    "✓" if p["enabled"] else "",
                    rule_count,
                ),
                tags=(sev_tag,),
            )
        if not policies:
            self._policy_tree.insert("", "end",
                                     values=("(no policies)", "", "", ""),
                                     tags=("empty",))

    def _on_policy_select(self, _event=None) -> None:
        sel = self._policy_tree.selection()
        if sel:
            self._load_policy(int(sel[0]))

    def _load_policy(self, policy_id: int) -> None:
        policy = self.app.policy_repo.get(self.app.conn, policy_id)
        if policy is None:
            return
        self._editing_policy_id = policy_id
        self._name_var.set(policy["name"])
        self._desc_var.set(policy.get("description") or "")
        self._severity_var.set(policy["severity"])
        self._match_mode_var.set(policy["match_mode"])
        prefixes = json.loads(policy.get("scope_prefixes_json") or "[]")
        self._scope_var.set(", ".join(prefixes))
        self._enabled_var.set(bool(policy["enabled"]))
        self._rules_buffer = [dict(r) for r in self.app.rule_repo.list_for_policy(self.app.conn, policy_id)]
        self._refresh_rules_view()

    def _clear_form(self) -> None:
        self._editing_policy_id = None
        self._name_var.set("")
        self._desc_var.set("")
        self._severity_var.set("warning")
        self._match_mode_var.set("all")
        self._scope_var.set("")
        self._enabled_var.set(False)
        self._rules_buffer = []
        self._refresh_rules_view()

    def _refresh_rules_view(self) -> None:
        self._rule_tree.delete(*self._rule_tree.get_children())
        for i, rule in enumerate(self._rules_buffer):
            neg = "NOT " if rule.get("negated") else ""
            self._rule_tree.insert(
                "", "end", iid=str(i),
                values=(
                    rule["field_name"],
                    neg + rule["operator"],
                    _display_value(rule["value_json"]),
                    "✓" if rule.get("case_sensitive") else "",
                ),
            )
        if not self._rules_buffer:
            self._rule_tree.insert("", "end",
                                   values=("(no rules)", "", "", ""),
                                   tags=("empty",))

    # ── Actions ──────────────────────────────────────────────────────────────

    def on_tab_activate(self) -> None:
        self._refresh_policy_list()
        self._update_pending_badge()

    def _update_pending_badge(self) -> None:
        if not hasattr(self, "_pending_btn") or self._pending_btn is None:
            return
        try:
            count = self.app.draft_policy_repo.count_pending(self.app.conn)
            self._pending_btn.configure(
                text=f"Pending Approvals ({count})",
                bg=Theme.RED if count > 0 else Theme.AMBER,
            )
        except Exception:
            pass

    def _submit_draft(self) -> None:
        """Admin: validate form and submit as a pending draft."""
        name = self._name_var.get().strip()
        if not name:
            messagebox.showerror("Validation", "Policy name is required.")
            return
        if not self._rules_buffer:
            messagebox.showerror("Validation", "Add at least one rule before submitting.")
            return

        scope_text = self._scope_var.get().strip()
        scope_prefixes = [p.strip() for p in scope_text.split(",") if p.strip()] if scope_text else []

        submitter = (self.app.authenticated_user or {}).get("username", "admin")
        draft_id = self.app.draft_policy_repo.create(
            self.app.conn,
            name=name,
            description=self._desc_var.get().strip() or None,
            severity=self._severity_var.get(),
            match_mode=self._match_mode_var.get(),
            scope_prefixes_json=json.dumps(scope_prefixes),
            submitted_by=submitter,
            rules=self._rules_buffer,
        )
        messagebox.showinfo(
            "Submitted",
            f"Policy draft '{name}' submitted for approval (Draft #{draft_id}).",
        )
        self._clear_form()

    def _open_approvals_dialog(self) -> None:
        DraftApprovalDialog(self, self.app)
        self._update_pending_badge()
        self._refresh_policy_list()

    def _new_policy(self) -> None:
        self._policy_tree.selection_remove(*self._policy_tree.selection())
        self._clear_form()

    def _save_policy(self) -> None:
        name = self._name_var.get().strip()
        if not name:
            messagebox.showerror("Validation", "Policy name is required.")
            return

        scope_text = self._scope_var.get().strip()
        scope_prefixes = [p.strip() for p in scope_text.split(",") if p.strip()] if scope_text else []

        conn = self.app.conn
        policy_repo = self.app.policy_repo
        rule_repo = self.app.rule_repo

        if self._editing_policy_id is None:
            policy_id = policy_repo.create(
                conn,
                name=name,
                description=self._desc_var.get().strip(),
                severity=self._severity_var.get(),
                match_mode=self._match_mode_var.get(),
                scope_prefixes=scope_prefixes,
                enabled=self._enabled_var.get(),
            )
            self._editing_policy_id = policy_id
        else:
            policy_id = self._editing_policy_id
            policy_repo.update(
                conn,
                policy_id,
                name=name,
                description=self._desc_var.get().strip(),
                severity=self._severity_var.get(),
                match_mode=self._match_mode_var.get(),
                scope_prefixes_json=json.dumps(scope_prefixes),
                enabled=int(self._enabled_var.get()),
            )

        rule_repo.delete_for_policy(conn, policy_id)
        for i, rule in enumerate(self._rules_buffer):
            rule_repo.create(
                conn,
                policy_id=policy_id,
                field_name=rule["field_name"],
                operator=rule["operator"],
                value=json.loads(rule["value_json"]),
                case_sensitive=bool(rule.get("case_sensitive", False)),
                negated=bool(rule.get("negated", False)),
                sort_order=i,
            )

        self._refresh_policy_list()
        try:
            self._policy_tree.selection_set(str(policy_id))
            self._policy_tree.see(str(policy_id))
        except tk.TclError:
            pass
        messagebox.showinfo("Saved", f"Policy '{name}' saved.")

    def _delete_policy(self) -> None:
        if self._editing_policy_id is None:
            messagebox.showwarning("No Selection", "Select a policy to delete.")
            return
        policy = self.app.policy_repo.get(self.app.conn, self._editing_policy_id)
        if policy is None:
            return
        if not messagebox.askyesno(
            "Confirm Delete",
            f"Delete policy '{policy['name']}'?\nThis cannot be undone.",
        ):
            return
        self.app.policy_repo.delete(self.app.conn, self._editing_policy_id)
        self._clear_form()
        self._refresh_policy_list()

    def _add_rule(self) -> None:
        def _on_save(rule_dict: dict) -> None:
            self._rules_buffer.append(rule_dict)
            self._refresh_rules_view()

        RuleDialog(self, _on_save)

    def _delete_rule(self) -> None:
        sel = self._rule_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a rule to delete.")
            return
        if messagebox.askyesno("Confirm Delete", "Remove this rule?"):
            del self._rules_buffer[int(sel[0])]
            self._refresh_rules_view()


# ---------------------------------------------------------------------------
# RuleDialog
# ---------------------------------------------------------------------------

class RuleDialog(tk.Toplevel):
    """Modal dialog for adding a single rule to the rules buffer."""

    def __init__(self, parent: tk.Widget, callback: Callable[[dict], None]) -> None:
        super().__init__(parent)
        self.title("Add Rule")
        self.resizable(False, False)
        self.grab_set()
        self._callback = callback
        self._build()
        self.transient(parent)
        self.wait_window()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)

        # Field row
        ttk.Label(outer, text="Field:", width=14, anchor="w").grid(
            row=0, column=0, sticky="w", pady=4,
        )
        self._field_var = tk.StringVar(value=FIELD_NAMES[0])
        field_cb = ttk.Combobox(
            outer, textvariable=self._field_var,
            values=FIELD_NAMES, state="readonly", width=24,
        )
        field_cb.grid(row=0, column=1, sticky="w", pady=4)
        self._field_var.trace_add("write", self._on_field_change)

        # Operator row
        ttk.Label(outer, text="Operator:", width=14, anchor="w").grid(
            row=1, column=0, sticky="w", pady=4,
        )
        self._op_var = tk.StringVar()
        self._op_cb = ttk.Combobox(
            outer, textvariable=self._op_var, state="readonly", width=24,
        )
        self._op_cb.grid(row=1, column=1, sticky="w", pady=4)
        self._op_var.trace_add("write", self._on_op_change)

        # Value row
        ttk.Label(outer, text="Value:", width=14, anchor="w").grid(
            row=2, column=0, sticky="w", pady=4,
        )
        self._value_var = tk.StringVar()
        self._value_entry = ttk.Entry(outer, textvariable=self._value_var, width=32)
        self._value_entry.grid(row=2, column=1, sticky="w", pady=4)

        self._hint_lbl = ttk.Label(outer, text="", foreground="gray", font=("", 8))
        self._hint_lbl.grid(row=3, column=1, sticky="w")

        # Case sensitive
        self._cs_var = tk.BooleanVar(value=False)
        self._cs_cb = ttk.Checkbutton(outer, text="Case Sensitive", variable=self._cs_var)
        self._cs_cb.grid(row=4, column=0, columnspan=2, sticky="w", pady=3)

        # Negated
        self._neg_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(outer, text="Negate (NOT)", variable=self._neg_var).grid(
            row=5, column=0, columnspan=2, sticky="w", pady=3,
        )

        # Buttons
        btn_row = ttk.Frame(outer)
        btn_row.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(
            btn_row, text="Add", command=self._save, style="Accent.TButton",
        ).pack(side="left", padx=(0, 4))
        ttk.Button(btn_row, text="Cancel", command=self.destroy).pack(side="left")
        ttk.Button(
            btn_row, text="? Help",
            command=lambda: PolicyHelpDialog.open(self),
        ).pack(side="right")

        # Seed initial operator list
        self._on_field_change()

    def _on_field_change(self, *_) -> None:
        field = self._field_var.get()
        ftype = _FIELD_TYPE.get(field, "string")
        ops = _OPERATORS_FOR_TYPE.get(ftype, _STRING_OPS)
        self._op_cb["values"] = ops
        self._op_var.set(ops[0] if ops else "")
        # Case-sensitive only makes sense for string fields
        if ftype in ("string", "string_nullable"):
            self._cs_cb.state(["!disabled"])
        else:
            self._cs_var.set(False)
            self._cs_cb.state(["disabled"])

    def _on_op_change(self, *_) -> None:
        op = self._op_var.get()
        if op in NO_VALUE_OPS:
            self._value_entry.state(["disabled"])
            self._value_var.set("")
            self._hint_lbl["text"] = "(no value needed)"
        else:
            self._value_entry.state(["!disabled"])
            self._hint_lbl["text"] = _VALUE_HINTS.get(op, "")

    def _save(self) -> None:
        op = self._op_var.get()
        val_text = self._value_var.get().strip()

        err = validate_rule_value(op, val_text)
        if err:
            messagebox.showerror("Validation", err, parent=self)
            return

        try:
            value_json = _encode_value(op, val_text)
        except (ValueError, IndexError) as exc:
            messagebox.showerror("Validation", f"Invalid value: {exc}", parent=self)
            return

        self._callback({
            "field_name": self._field_var.get(),
            "operator": op,
            "value_json": value_json,
            "case_sensitive": self._cs_var.get(),
            "negated": self._neg_var.get(),
        })
        self.destroy()


# ---------------------------------------------------------------------------
# PolicyHelpDialog
# ---------------------------------------------------------------------------

_HELP_TEXT = """\
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 FIELDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

name              Filename only (no path), e.g. report.xlsx
extension         Lowercase extension including dot, e.g. .pdf  .docx
full_path         Complete file path including drive/UNC root
parent_path       Parent directory of the file
section_name      Section label assigned via Section Map (may be blank)
size_bytes        File size in bytes (integer)
ctime_utc         File creation timestamp (UTC)
mtime_utc         Last-modified timestamp (UTC)
atime_utc         Last-accessed timestamp (UTC)
owner_name        Windows owner/creator proxy, e.g. DOMAIN\\\\user
owner_sid         Windows Security Identifier of the owner
path_depth        Directory levels below the scan root (integer)
path_length       Total character length of the full path (integer)
is_empty          True when file has zero bytes


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 OPERATORS — STRING fields
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

equals            Exact match                   value: report.xlsx
not_equals        Does not match exactly        value: report.xlsx
contains          Substring present             value: copy of
starts_with       Begins with text              value: ~$
ends_with         Ends with text                value: final
glob              Shell wildcard pattern        value: ~$*.docx  or  * - Copy.*
regex             Python regular expression     value: \\\\.(exe|bat|cmd)$
                  Applied to 'name' by default; use 'full_path' for path matching.
                  Max 500 characters. Prefer glob for simple patterns.
in                Value is one of a list        value: .exe, .bat, .cmd
not_in            Value is not in list          value: .pdf, .docx

  → section_name / owner_name / owner_sid also support:
      is_missing        Field is NULL or blank
      is_not_missing    Field has a value


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 OPERATORS — NUMERIC fields
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  (size_bytes, path_depth, path_length)

gt                Greater than                  value: 5368709120
gte               Greater than or equal to      value: 1048576
lt                Less than                     value: 1024
lte               Less than or equal to         value: 240
between           Inclusive range               value: 1024, 5368709120


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 OPERATORS — DATE fields
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  (ctime_utc, mtime_utc, atime_utc)

before            Modified/created before date  value: 2020-01-01
after             Modified/created after date   value: 2024-06-15
older_than_days   More than N days ago          value: 2555  (≈ 7 years)
newer_than_days   Within the last N days        value: 30


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 OPERATORS — BOOLEAN fields
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  (is_empty)

is_true           Flag is set (True)
is_false          Flag is not set (False)


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 MATCH MODE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

all   Every rule in the policy must match (AND logic)
any   At least one rule must match (OR logic)


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 OTHER OPTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Case Sensitive    When checked, string comparisons are case-sensitive.
                  Has no effect on numeric, date, or boolean operators.

Negate (NOT)      Inverts the rule result. A file that would have matched
                  now does NOT match, and vice versa.

Scope Prefixes    Comma-separated path prefixes that restrict where the
                  policy applies. Leave blank to apply to all scanned paths.
                  Example:  \\\\\\\\server\\\\share\\\\Finance, \\\\\\\\server\\\\share\\\\HR
"""


class PolicyHelpDialog(tk.Toplevel):
    """Read-only scrollable reference for policy fields and operators."""

    def __init__(self, parent: tk.Widget | None = None) -> None:
        super().__init__(parent)
        self.title("Policy Rule Reference")
        self.resizable(True, True)
        self.geometry("680x580")
        self.configure(bg=Theme.BG)
        if parent:
            self.transient(parent)
        self.grab_set()
        self._build()

    @staticmethod
    def open(parent: tk.Widget | None = None) -> None:
        PolicyHelpDialog(parent)

    def _build(self) -> None:
        # Header bar
        header = tk.Frame(self, bg=Theme.PANEL, height=36)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="  POLICY RULE REFERENCE",
            bg=Theme.PANEL, fg=Theme.CYAN,
            font=("Segoe UI Semibold", 10), anchor="w",
        ).pack(side="left", fill="y")
        tk.Frame(self, bg=Theme.BORDER, height=1).pack(fill="x")

        # Scrollable text body
        body = tk.Frame(self, bg=Theme.BG)
        body.pack(fill="both", expand=True, padx=2, pady=2)

        vsb = tk.Scrollbar(body, orient="vertical")
        vsb.pack(side="right", fill="y")

        text = tk.Text(
            body,
            yscrollcommand=vsb.set,
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=("Consolas", 9),
            relief="flat",
            wrap="none",
            cursor="arrow",
            state="normal",
            padx=14,
            pady=10,
        )
        text.pack(side="left", fill="both", expand=True)
        vsb.config(command=text.yview)

        # Horizontal scrollbar for wide content
        hsb = tk.Scrollbar(self, orient="horizontal", command=text.xview)
        hsb.pack(fill="x", padx=2)
        text.configure(xscrollcommand=hsb.set)

        # Tags for visual hierarchy
        text.tag_configure("heading",
                           foreground=Theme.CYAN,
                           font=("Consolas", 9, "bold"))
        text.tag_configure("field_name",
                           foreground=Theme.AMBER,
                           font=("Consolas", 9))
        text.tag_configure("op_name",
                           foreground=Theme.GREEN,
                           font=("Consolas", 9))
        text.tag_configure("dim",
                           foreground=Theme.MUTED,
                           font=("Consolas", 8))

        self._insert_help(text)
        text.configure(state="disabled")

        # Close button
        tk.Frame(self, bg=Theme.BORDER, height=1).pack(fill="x")
        footer = tk.Frame(self, bg=Theme.PANEL)
        footer.pack(fill="x", pady=6)
        tk.Button(
            footer, text="Close",
            bg=Theme.PANEL_2, fg=Theme.TEXT,
            font=("Segoe UI", 9), relief="flat",
            padx=18, pady=4, cursor="hand2",
            activebackground=Theme.PANEL_3,
            command=self.destroy,
        ).pack(side="right", padx=12)

    def _insert_help(self, text: tk.Text) -> None:
        sections = [
            ("FIELDS", _FIELD_HELP),
            ("OPERATORS — STRING fields", _OP_STRING_HELP),
            ("OPERATORS — NUMERIC fields  (size_bytes, path_depth, path_length)", _OP_NUMERIC_HELP),
            ("OPERATORS — DATE fields  (ctime_utc, mtime_utc, atime_utc)", _OP_DATE_HELP),
            ("OPERATORS — BOOLEAN fields  (is_empty)", _OP_BOOL_HELP),
            ("MATCH MODE", _MATCH_MODE_HELP),
            ("OTHER OPTIONS", _OTHER_HELP),
        ]
        for title, rows in sections:
            text.insert("end", f"\n{'━' * 52}\n", "dim")
            text.insert("end", f" {title}\n", "heading")
            text.insert("end", f"{'━' * 52}\n\n", "dim")
            for item in rows:
                if len(item) == 2:
                    name, desc = item
                    text.insert("end", f"  {name:<22}", "field_name")
                    text.insert("end", f"{desc}\n")
                elif len(item) == 3:
                    name, example_label, example = item
                    text.insert("end", f"  {name:<22}", "op_name")
                    text.insert("end", f"{example_label:<30}", "dim")
                    text.insert("end", f"  e.g. {example}\n")
                else:
                    text.insert("end", f"  {item[0]}\n", "dim")
            text.insert("end", "\n")


_FIELD_HELP = [
    ("name",          "Filename only (no path)                  e.g.  report.xlsx"),
    ("extension",     "Lowercase extension with dot             e.g.  .pdf   .docx"),
    ("full_path",     "Complete path including drive/UNC root"),
    ("parent_path",   "Parent directory of the file"),
    ("section_name",  "Section label from Section Map (may be blank)"),
    ("size_bytes",    "File size in bytes (integer)"),
    ("ctime_utc",     "File creation timestamp (UTC)"),
    ("mtime_utc",     "Last-modified timestamp (UTC)"),
    ("atime_utc",     "Last-accessed timestamp (UTC)"),
    ("owner_name",    "Windows owner proxy              e.g.  DOMAIN\\\\user"),
    ("owner_sid",     "Windows Security Identifier of the owner"),
    ("path_depth",    "Directory levels below the scan root (integer)"),
    ("path_length",   "Total character length of the full path (integer)"),
    ("is_empty",      "True when file size is zero bytes"),
]

_OP_STRING_HELP = [
    ("equals",        "Exact match",                    "report.xlsx"),
    ("not_equals",    "Does not match exactly",         "report.xlsx"),
    ("contains",      "Substring present",              "copy of"),
    ("starts_with",   "Begins with text",               "~$"),
    ("ends_with",     "Ends with text",                 "_final"),
    ("glob",          "Shell wildcard  (* ? [...])",    "~$*.docx  or  * - Copy.*"),
    ("regex",         "Python regex (max 500 chars)",   "\\\\.(exe|bat|cmd)$"),
    ("in",            "Value in comma-separated list",  ".exe, .bat, .cmd"),
    ("not_in",        "Value not in list",              ".pdf, .docx"),
    ("is_missing",    "Field is NULL/blank  (nullable fields only)",),
    ("is_not_missing","Field has a value   (nullable fields only)",),
]

_OP_NUMERIC_HELP = [
    ("gt",            "Greater than",                   "5368709120"),
    ("gte",           "Greater than or equal to",       "1048576"),
    ("lt",            "Less than",                      "1024"),
    ("lte",           "Less than or equal to",          "240"),
    ("between",       "Inclusive range (min, max)",     "1024, 5368709120"),
]

_OP_DATE_HELP = [
    ("before",           "Earlier than a date",         "2020-01-01"),
    ("after",            "Later than a date",           "2024-06-15"),
    ("older_than_days",  "More than N days ago",        "2555   (≈ 7 years)"),
    ("newer_than_days",  "Within the last N days",      "30"),
]

_OP_BOOL_HELP = [
    ("is_true",       "Flag is set (True)"),
    ("is_false",      "Flag is not set (False)"),
]

_MATCH_MODE_HELP = [
    ("all", "Every rule in the policy must match  (AND logic)"),
    ("any", "At least one rule must match  (OR logic)"),
]

_OTHER_HELP = [
    ("Case Sensitive",
     "String comparisons are case-sensitive when checked.\n"
     "                       Has no effect on numeric, date, or boolean operators."),
    ("Negate (NOT)",
     "Inverts the rule — a file that would have matched\n"
     "                       now does NOT match, and vice versa."),
    ("Scope Prefixes",
     "Comma-separated path prefixes that restrict where\n"
     "                       the policy applies. Blank = all scanned paths.\n"
     "                       e.g.  \\\\\\\\server\\\\share\\\\Finance, \\\\\\\\server\\\\share\\\\HR"),
]


# ---------------------------------------------------------------------------
# DraftApprovalDialog  (secret_admin only)
# ---------------------------------------------------------------------------

class DraftApprovalDialog(tk.Toplevel):
    """Modal dialog for reviewing and approving/rejecting pending policy drafts."""

    def __init__(self, parent: tk.Widget, app) -> None:
        super().__init__(parent)
        self.title("Pending Policy Drafts")
        self.resizable(True, True)
        self.geometry("960x560")
        self.grab_set()
        self._app = app
        self._selected_draft: dict | None = None
        self._build()
        self._load()
        self.transient(parent)
        self.wait_window()

    def _build(self) -> None:
        pane = ttk.PanedWindow(self, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=8)

        left = ttk.Frame(pane)
        right = ttk.Frame(pane)
        pane.add(left, weight=1)
        pane.add(right, weight=2)

        # Draft list
        section_header(left, "Pending Drafts")
        cols = ("name", "severity", "submitted_by", "created_at")
        self._draft_tree = ttk.Treeview(
            left, columns=cols, show="headings", selectmode="browse", height=20,
        )
        for col, label, w in [
            ("name", "Name", 150),
            ("severity", "Severity", 70),
            ("submitted_by", "Submitted By", 90),
            ("created_at", "Submitted", 110),
        ]:
            self._draft_tree.heading(col, text=label)
            self._draft_tree.column(col, width=w)
        vsb = ttk.Scrollbar(left, orient="vertical", command=self._draft_tree.yview)
        self._draft_tree.configure(yscrollcommand=vsb.set)
        self._draft_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")
        self._draft_tree.tag_configure("sev_critical", foreground=Theme.RED)
        self._draft_tree.tag_configure("sev_warning",  foreground=Theme.AMBER)
        self._draft_tree.tag_configure("sev_info",     foreground=Theme.BLUE)
        self._draft_tree.bind("<<TreeviewSelect>>", self._on_select)

        # Detail + actions
        section_header(right, "Draft Details")
        detail_frame = ttk.Frame(right, padding=6)
        detail_frame.pack(fill="both", expand=True)

        self._detail_text = tk.Text(
            detail_frame, height=14, state="disabled",
            bg=Theme.PANEL, fg=Theme.TEXT, font=Theme.FONT_MONO,
            relief="flat", wrap="word",
        )
        self._detail_text.pack(fill="both", expand=True, pady=(0, 6))

        ttk.Label(detail_frame, text="Review Note (optional):").pack(anchor="w")
        self._note_var = tk.StringVar()
        ttk.Entry(detail_frame, textvariable=self._note_var, width=60).pack(fill="x", pady=(2, 8))

        btn_row = ttk.Frame(detail_frame)
        btn_row.pack(anchor="w")
        ttk.Button(
            btn_row, text="Approve", style="Accent.TButton",
            command=self._approve,
        ).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="Reject", command=self._reject).pack(side="left", padx=(0, 12))
        ttk.Button(btn_row, text="Close", command=self.destroy).pack(side="left")

    def _load(self) -> None:
        self._draft_tree.delete(*self._draft_tree.get_children())
        drafts = self._app.draft_policy_repo.list_pending(self._app.conn)
        for d in drafts:
            self._draft_tree.insert(
                "", "end", iid=str(d["draft_id"]),
                values=(
                    d["name"],
                    d["severity"],
                    d["submitted_by"],
                    (d.get("created_at_utc") or "")[:16],
                ),
                tags=(f"sev_{d['severity']}",),
            )
        if not drafts:
            self._draft_tree.insert("", "end", values=("(no pending drafts)", "", "", ""))

    def _on_select(self, _event=None) -> None:
        sel = self._draft_tree.selection()
        if not sel:
            return
        try:
            draft_id = int(sel[0])
        except ValueError:
            return
        draft = self._app.draft_policy_repo.get(self._app.conn, draft_id)
        if draft is None:
            return
        self._selected_draft = draft
        rules = self._app.draft_policy_repo.get_rules(self._app.conn, draft_id)

        lines = [
            f"Name:        {draft['name']}",
            f"Severity:    {draft['severity']}",
            f"Match Mode:  {draft['match_mode']}",
            f"Description: {draft.get('description') or '—'}",
            f"Submitted:   {draft['submitted_by']}  @ {(draft.get('created_at_utc') or '')[:16]}",
            "",
            "Rules:",
        ]
        for r in rules:
            neg = "NOT " if r.get("negated") else ""
            cs  = "  [CS]" if r.get("case_sensitive") else ""
            lines.append(f"  {r['field_name']}  {neg}{r['operator']}  {_display_value(r['value_json'])}{cs}")

        self._detail_text.configure(state="normal")
        self._detail_text.delete("1.0", "end")
        self._detail_text.insert("end", "\n".join(lines))
        self._detail_text.configure(state="disabled")

    def _approve(self) -> None:
        if self._selected_draft is None:
            messagebox.showwarning("No Selection", "Select a draft first.", parent=self)
            return
        reviewer = (self._app.authenticated_user or {}).get("username", "secret_admin")
        note = self._note_var.get().strip() or None
        policy_id = self._app.draft_policy_repo.approve(
            self._app.conn, self._selected_draft["draft_id"], reviewer, note,
        )
        messagebox.showinfo(
            "Approved",
            f"Policy '{self._selected_draft['name']}' approved and activated (Policy #{policy_id}).",
            parent=self,
        )
        self._selected_draft = None
        self._note_var.set("")
        self._detail_text.configure(state="normal")
        self._detail_text.delete("1.0", "end")
        self._detail_text.configure(state="disabled")
        self._load()

    def _reject(self) -> None:
        if self._selected_draft is None:
            messagebox.showwarning("No Selection", "Select a draft first.", parent=self)
            return
        if not messagebox.askyesno("Confirm Reject",
                                   f"Reject draft '{self._selected_draft['name']}'?",
                                   parent=self):
            return
        reviewer = (self._app.authenticated_user or {}).get("username", "secret_admin")
        note = self._note_var.get().strip() or None
        self._app.draft_policy_repo.reject(
            self._app.conn, self._selected_draft["draft_id"], reviewer, note,
        )
        messagebox.showinfo("Rejected", "Draft rejected.", parent=self)
        self._selected_draft = None
        self._note_var.set("")
        self._detail_text.configure(state="normal")
        self._detail_text.delete("1.0", "end")
        self._detail_text.configure(state="disabled")
        self._load()
