"""Policy engine — operator dispatch, evaluation, violation generation."""
from __future__ import annotations

import fnmatch
import json
import logging
import re
import sqlite3
from datetime import datetime, timezone
from typing import Callable

from shared_drive_manager.core.models import FileRecord, Policy, Rule, Violation

log = logging.getLogger(__name__)

_REGEX_MAX_LEN = 500

# Maps the rule field_name to the matching FileRecord attribute name.
_FIELD_TO_ATTR: dict[str, str] = {
    "name": "name",
    "extension": "extension",
    "full_path": "full_path",
    "parent_path": "parent_path",
    "section_name": "section_name",
    "size_bytes": "size_bytes",
    "ctime_utc": "ctime_utc",
    "mtime_utc": "mtime_utc",
    "atime_utc": "atime_utc",
    "owner_name": "owner_name",
    "owner_sid": "owner_sid",
    "doc_creator": "doc_creator",
    "doc_modifier": "doc_modifier",
    "path_depth": "path_depth",
    "path_length": "path_length",
    "is_empty": "is_empty",
}

# ---------------------------------------------------------------------------
# Operator implementations — all take (field_value, rule_value, case_sensitive)
# ---------------------------------------------------------------------------

def _str(v, cs: bool) -> str:
    s = str(v) if v is not None else ""
    return s if cs else s.lower()


def _op_equals(fv, rv, cs: bool) -> bool:
    return _str(fv, cs) == _str(rv, cs)


def _op_not_equals(fv, rv, cs: bool) -> bool:
    return _str(fv, cs) != _str(rv, cs)


def _op_contains(fv, rv, cs: bool) -> bool:
    return _str(rv, cs) in _str(fv, cs)


def _op_starts_with(fv, rv, cs: bool) -> bool:
    return _str(fv, cs).startswith(_str(rv, cs))


def _op_ends_with(fv, rv, cs: bool) -> bool:
    return _str(fv, cs).endswith(_str(rv, cs))


def _op_glob(fv, rv, cs: bool) -> bool:
    text = _str(fv, cs)
    pattern = _str(rv, cs)
    return fnmatch.fnmatchcase(text, pattern)


def _op_regex(fv, rv, cs: bool) -> bool:
    pattern = str(rv)
    if len(pattern) > _REGEX_MAX_LEN:
        raise ValueError(f"Regex too long ({len(pattern)} > {_REGEX_MAX_LEN})")
    flags = 0 if cs else re.IGNORECASE
    compiled = re.compile(pattern, flags)
    return bool(compiled.search(str(fv) if fv is not None else ""))


def _op_in(fv, rv, cs: bool) -> bool:
    items = rv if isinstance(rv, list) else [rv]
    needle = _str(fv, cs)
    return needle in [_str(i, cs) for i in items]


def _op_not_in(fv, rv, cs: bool) -> bool:
    return not _op_in(fv, rv, cs)


# Numeric

def _num(v) -> float:
    return float(v) if v is not None else 0.0


def _op_gt(fv, rv, _cs: bool) -> bool:
    return _num(fv) > _num(rv)


def _op_gte(fv, rv, _cs: bool) -> bool:
    return _num(fv) >= _num(rv)


def _op_lt(fv, rv, _cs: bool) -> bool:
    return _num(fv) < _num(rv)


def _op_lte(fv, rv, _cs: bool) -> bool:
    return _num(fv) <= _num(rv)


def _op_between(fv, rv, _cs: bool) -> bool:
    lo, hi = float(rv[0]), float(rv[1])
    return lo <= _num(fv) <= hi


# Date — UTC ISO-8601 strings

def _parse_utc(s) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except ValueError:
        return None


def _op_before(fv, rv, _cs: bool) -> bool:
    a, b = _parse_utc(fv), _parse_utc(rv)
    return (a < b) if (a and b) else False


def _op_after(fv, rv, _cs: bool) -> bool:
    a, b = _parse_utc(fv), _parse_utc(rv)
    return (a > b) if (a and b) else False


def _op_older_than_days(fv, rv, _cs: bool) -> bool:
    dt = _parse_utc(fv)
    if dt is None:
        return False
    return (datetime.now(timezone.utc) - dt).days > int(float(rv))


def _op_newer_than_days(fv, rv, _cs: bool) -> bool:
    dt = _parse_utc(fv)
    if dt is None:
        return False
    return (datetime.now(timezone.utc) - dt).days < int(float(rv))


# Boolean

def _op_is_true(fv, _rv, _cs: bool) -> bool:
    return bool(fv)


def _op_is_false(fv, _rv, _cs: bool) -> bool:
    return not bool(fv)


# Null / missing

def _op_is_missing(fv, _rv, _cs: bool) -> bool:
    return fv is None or fv == ""


def _op_is_not_missing(fv, _rv, _cs: bool) -> bool:
    return fv is not None and fv != ""


_OPERATORS: dict[str, Callable] = {
    "equals": _op_equals,
    "not_equals": _op_not_equals,
    "contains": _op_contains,
    "starts_with": _op_starts_with,
    "ends_with": _op_ends_with,
    "glob": _op_glob,
    "regex": _op_regex,
    "in": _op_in,
    "not_in": _op_not_in,
    "gt": _op_gt,
    "gte": _op_gte,
    "lt": _op_lt,
    "lte": _op_lte,
    "between": _op_between,
    "before": _op_before,
    "after": _op_after,
    "older_than_days": _op_older_than_days,
    "newer_than_days": _op_newer_than_days,
    "is_true": _op_is_true,
    "is_false": _op_is_false,
    "is_missing": _op_is_missing,
    "is_not_missing": _op_is_not_missing,
}

# Operators that require no value field (value stored as JSON null).
NO_VALUE_OPS: frozenset[str] = frozenset(
    ["is_true", "is_false", "is_missing", "is_not_missing"]
)


# ---------------------------------------------------------------------------
# Public validation helper (used by the UI before saving a rule)
# ---------------------------------------------------------------------------

def validate_rule_value(operator: str, value_str: str) -> str | None:
    """Return an error message string, or None if the value is acceptable."""
    if operator in NO_VALUE_OPS:
        return None
    if not value_str.strip():
        return "Value is required for this operator."
    if operator == "regex":
        if len(value_str) > _REGEX_MAX_LEN:
            return f"Regex too long ({len(value_str)} > {_REGEX_MAX_LEN} chars)."
        try:
            re.compile(value_str)
        except re.error as exc:
            return f"Invalid regex: {exc}"
    elif operator == "between":
        parts = [p.strip() for p in value_str.split(",")]
        if len(parts) != 2:
            return "between requires two comma-separated numbers: lo, hi"
        try:
            float(parts[0])
            float(parts[1])
        except ValueError:
            return "between values must be numbers."
    elif operator in ("gt", "gte", "lt", "lte", "older_than_days", "newer_than_days"):
        try:
            float(value_str.strip())
        except ValueError:
            return f"'{operator}' requires a numeric value."
    return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _match_rule(rule: Rule, record: FileRecord) -> bool:
    attr = _FIELD_TO_ATTR.get(rule.field_name)
    if attr is None:
        log.warning("Unknown field '%s' in rule %s — skipping", rule.field_name, rule.rule_id)
        return False
    op_fn = _OPERATORS.get(rule.operator)
    if op_fn is None:
        log.warning("Unknown operator '%s' in rule %s — skipping", rule.operator, rule.rule_id)
        return False

    field_val = getattr(record, attr, None)
    try:
        result = op_fn(field_val, rule.value, rule.case_sensitive)
    except Exception as exc:
        log.warning("Rule %s eval error (%s): %s", rule.rule_id, rule.operator, exc)
        return False

    return (not result) if rule.negated else result


def _build_reason(policy: Policy, record: FileRecord, matched: list[bool]) -> str:
    parts = []
    for rule, hit in zip(policy.rules, matched):
        if hit:
            neg = "NOT " if rule.negated else ""
            parts.append(f"{rule.field_name} {neg}{rule.operator} {rule.value!r}")
    return "; ".join(parts) if parts else policy.name


# ---------------------------------------------------------------------------
# PolicyEngine
# ---------------------------------------------------------------------------

class PolicyEngine:
    """Loads active policies and evaluates them against FileRecord objects."""

    def load_active_policies(self, conn: sqlite3.Connection) -> list[Policy]:
        from shared_drive_manager.db.repositories import PolicyRepo, PolicyRuleRepo

        policy_repo = PolicyRepo()
        rule_repo = PolicyRuleRepo()
        policies: list[Policy] = []

        for row in policy_repo.list_active(conn):
            rule_rows = rule_repo.list_for_policy(conn, row["policy_id"])
            rules = [
                Rule(
                    rule_id=r["rule_id"],
                    policy_id=r["policy_id"],
                    field_name=r["field_name"],
                    operator=r["operator"],
                    value=json.loads(r["value_json"]),
                    case_sensitive=bool(r["case_sensitive"]),
                    negated=bool(r["negated"]),
                    sort_order=r["sort_order"],
                )
                for r in rule_rows
            ]
            prefixes = json.loads(row.get("scope_prefixes_json") or "[]")
            policies.append(
                Policy(
                    policy_id=row["policy_id"],
                    name=row["name"],
                    severity=row["severity"],
                    match_mode=row["match_mode"],
                    scope_prefixes=prefixes,
                    rules=rules,
                    enabled=bool(row["enabled"]),
                )
            )
        return policies

    def evaluate(
        self,
        record: FileRecord,
        policies: list[Policy],
        run_id: int,
    ) -> list[Violation]:
        if record.file_id is None:
            return []

        violations: list[Violation] = []
        for policy in policies:
            if policy.scope_prefixes:
                path_lower = record.full_path.lower()
                if not any(path_lower.startswith(p.lower()) for p in policy.scope_prefixes):
                    continue

            if not policy.rules:
                continue

            matched = [_match_rule(rule, record) for rule in policy.rules]
            hit = all(matched) if policy.match_mode == "all" else any(matched)

            if hit:
                violations.append(
                    Violation(
                        run_id=run_id,
                        file_id=record.file_id,
                        policy_id=policy.policy_id,
                        severity=policy.severity,
                        reason=_build_reason(policy, record, matched),
                    )
                )
        return violations
