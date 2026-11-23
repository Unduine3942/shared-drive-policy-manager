import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def run_migrations(conn: sqlite3.Connection) -> None:
    _apply_schema(conn)
    _add_columns(conn)
    _seed_starter_policies(conn)
    from shared_drive_manager.db.repositories import UserRepo
    UserRepo().seed_default_users(conn)


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _add_columns(conn: sqlite3.Connection) -> None:
    """Add columns introduced after initial schema deployment (idempotent)."""
    for table, col, ddl in [
        ("file_inventory",   "doc_creator", "TEXT"),
        ("file_inventory",   "doc_modifier", "TEXT"),
        ("scan_directories", "dir_mtime",   "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
            conn.commit()
        except Exception:
            pass  # column already exists

    try:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_scan_directories_dir_hash"
            " ON scan_directories(dir_hash)"
        )
        conn.commit()
    except Exception:
        pass


def _apply_schema(conn: sqlite3.Connection) -> None:
    schema_path = Path(__file__).parent / "schema.sql"
    conn.executescript(schema_path.read_text(encoding="utf-8"))


def _seed_starter_policies(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0] > 0:
        return

    now = _utcnow()

    starters = [
        {
            "name": "Stale files older than 7 years",
            "description": "Flags files not modified in over 7 years (2555 days).",
            "severity": "warning",
            "match_mode": "all",
            "rules": [
                {"field_name": "mtime_utc", "operator": "older_than_days", "value": 2555},
            ],
        },
        {
            "name": "Potentially risky executables",
            "description": "Flags executable and script file types.",
            "severity": "critical",
            "match_mode": "all",
            "rules": [
                {
                    "field_name": "extension",
                    "operator": "in",
                    "value": [".exe", ".bat", ".cmd", ".ps1", ".vbs", ".msi"],
                },
            ],
        },
        {
            "name": "Personal archive and mail files",
            "description": "Flags personal archive and email container files.",
            "severity": "warning",
            "match_mode": "all",
            "rules": [
                {
                    "field_name": "extension",
                    "operator": "in",
                    "value": [".pst", ".ost", ".zip", ".7z", ".rar"],
                },
            ],
        },
        {
            "name": "Oversized files",
            "description": "Flags files larger than 5 GB.",
            "severity": "warning",
            "match_mode": "all",
            "rules": [
                {"field_name": "size_bytes", "operator": "gt", "value": 5368709120},
            ],
        },
        {
            "name": "Temporary or duplicate-looking names",
            "description": "Flags files whose names suggest temp copies or duplicates.",
            "severity": "info",
            "match_mode": "any",
            "rules": [
                {"field_name": "name", "operator": "starts_with", "value": "~$"},
                {"field_name": "name", "operator": "contains", "value": "copy of"},
                {"field_name": "name", "operator": "glob", "value": "* - Copy.*"},
            ],
        },
        {
            "name": "Long paths",
            "description": "Flags files whose full path exceeds 240 characters.",
            "severity": "warning",
            "match_mode": "all",
            "rules": [
                {"field_name": "path_length", "operator": "gt", "value": 240},
            ],
        },
        {
            "name": "Unknown owner",
            "description": "Flags files where the owner/creator proxy could not be resolved.",
            "severity": "info",
            "match_mode": "all",
            "rules": [
                {"field_name": "owner_name", "operator": "is_missing", "value": None},
            ],
        },
        {
            "name": "Empty files",
            "description": "Flags zero-byte files.",
            "severity": "info",
            "match_mode": "all",
            "rules": [
                {"field_name": "is_empty", "operator": "is_true", "value": None},
            ],
        },
    ]

    for policy in starters:
        cur = conn.execute(
            """
            INSERT INTO policies
                (name, description, enabled, severity, match_mode,
                 scope_prefixes_json, created_at_utc, updated_at_utc)
            VALUES (?, ?, 0, ?, ?, '[]', ?, ?)
            """,
            (
                policy["name"],
                policy["description"],
                policy["severity"],
                policy["match_mode"],
                now,
                now,
            ),
        )
        policy_id = cur.lastrowid
        for order, rule in enumerate(policy["rules"]):
            conn.execute(
                """
                INSERT INTO policy_rules
                    (policy_id, field_name, operator, value_json,
                     case_sensitive, negated, sort_order,
                     created_at_utc, updated_at_utc)
                VALUES (?, ?, ?, ?, 0, 0, ?, ?, ?)
                """,
                (
                    policy_id,
                    rule["field_name"],
                    rule["operator"],
                    json.dumps(rule["value"]),
                    order,
                    now,
                    now,
                ),
            )

    conn.commit()
