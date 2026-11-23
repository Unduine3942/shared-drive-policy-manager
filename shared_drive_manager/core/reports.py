"""Report generators and CSV/XLSX export helpers."""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

try:
    import openpyxl
    from openpyxl.styles import Font as _XlFont
    XLSX_AVAILABLE = True
except ImportError:
    openpyxl = None  # type: ignore[assignment]
    XLSX_AVAILABLE = False

_CSV_COLUMNS: list[tuple[str, str]] = [
    ("violation_id", "Violation ID"),
    ("severity", "Severity"),
    ("policy_name", "Policy"),
    ("file_name", "File Name"),
    ("full_path", "Full Path"),
    ("owner_name", "Owner / Creator Proxy"),
    ("size_bytes", "Size (bytes)"),
    ("ctime_utc", "Created (UTC)"),
    ("mtime_utc", "Modified (UTC)"),
    ("section_name", "Section"),
    ("reason", "Reason"),
    ("run_id", "Scan Run ID"),
    ("status", "Status"),
    ("review_note", "Review Note"),
    ("reviewed_at_utc", "Reviewed At (UTC)"),
]


def export_violations_csv(rows: list[dict], dest_path: str | Path) -> int:
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", newline="", encoding="utf-8-sig") as fh:
        keys = [k for k, _ in _CSV_COLUMNS]
        labels = {k: label for k, label in _CSV_COLUMNS}
        writer = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        writer.writerow(labels)
        writer.writerows(rows)
    return len(rows)


def export_violations_xlsx(rows: list[dict], dest_path: str | Path) -> int:
    if not XLSX_AVAILABLE:
        raise RuntimeError("openpyxl is not available in this environment.")
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Violations"
    keys = [k for k, _ in _CSV_COLUMNS]
    headers = [label for _, label in _CSV_COLUMNS]
    ws.append(headers)
    for row in rows:
        ws.append([row.get(k, "") for k in keys])
    for cell in ws[1]:
        cell.font = _XlFont(bold=True)
    ws.freeze_panes = "A2"
    wb.save(dest)
    return len(rows)


# ---------------------------------------------------------------------------
# Summary queries
# ---------------------------------------------------------------------------

def summary_by_severity(
    conn: sqlite3.Connection, run_id: int | None = None
) -> list[dict]:
    params: list = []
    where = ""
    if run_id is not None:
        where = "WHERE pv.run_id = ?"
        params.append(run_id)
    rows = conn.execute(
        f"""
        SELECT pv.severity,
               COUNT(*) AS violation_count,
               COUNT(DISTINCT pv.file_id) AS file_count
          FROM policy_violations pv
        {where}
        GROUP BY pv.severity
        ORDER BY
            CASE pv.severity WHEN 'critical' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END
        """,
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def summary_by_section(
    conn: sqlite3.Connection, run_id: int | None = None
) -> list[dict]:
    params: list = []
    where = ""
    if run_id is not None:
        where = "WHERE pv.run_id = ?"
        params.append(run_id)
    rows = conn.execute(
        f"""
        SELECT COALESCE(fi.section_name, '(no section)') AS section_name,
               COUNT(*) AS violation_count,
               COUNT(DISTINCT pv.file_id) AS file_count,
               COUNT(CASE WHEN pv.severity = 'critical' THEN 1 END) AS critical_count
          FROM policy_violations pv
          JOIN file_inventory fi ON pv.file_id = fi.file_id
        {where}
        GROUP BY fi.section_name
        ORDER BY violation_count DESC
        """,
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def summary_by_owner(
    conn: sqlite3.Connection, run_id: int | None = None, limit: int = 50
) -> list[dict]:
    params: list = []
    where = ""
    if run_id is not None:
        where = "WHERE pv.run_id = ?"
        params.append(run_id)
    rows = conn.execute(
        f"""
        SELECT COALESCE(fi.owner_name, '(unknown)') AS owner_name,
               COUNT(*) AS violation_count,
               COUNT(DISTINCT pv.file_id) AS file_count
          FROM policy_violations pv
          JOIN file_inventory fi ON pv.file_id = fi.file_id
        {where}
        GROUP BY fi.owner_name
        ORDER BY violation_count DESC
        LIMIT ?
        """,
        params + [limit],
    ).fetchall()
    return [dict(r) for r in rows]


def summary_by_extension(
    conn: sqlite3.Connection, run_id: int | None = None, limit: int = 50
) -> list[dict]:
    params: list = []
    where = ""
    if run_id is not None:
        where = "WHERE pv.run_id = ?"
        params.append(run_id)
    rows = conn.execute(
        f"""
        SELECT COALESCE(fi.extension, '(none)') AS extension,
               COUNT(*) AS violation_count,
               COUNT(DISTINCT pv.file_id) AS file_count
          FROM policy_violations pv
          JOIN file_inventory fi ON pv.file_id = fi.file_id
        {where}
        GROUP BY fi.extension
        ORDER BY violation_count DESC
        LIMIT ?
        """,
        params + [limit],
    ).fetchall()
    return [dict(r) for r in rows]


def scan_errors_for_run(conn: sqlite3.Connection, run_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT se.error_id, se.path, se.operation, se.error_type,
               se.error_message, se.created_at_utc,
               sr.root_path
          FROM scan_errors se
          LEFT JOIN scan_roots sr ON se.root_id = sr.root_id
         WHERE se.run_id = ?
         ORDER BY se.error_id
        """,
        (run_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def largest_flagged_files(
    conn: sqlite3.Connection, run_id: int | None = None, limit: int = 25
) -> list[dict]:
    params: list = []
    where = ""
    if run_id is not None:
        where = "WHERE pv.run_id = ?"
        params.append(run_id)
    rows = conn.execute(
        f"""
        SELECT DISTINCT fi.file_id, fi.full_path, fi.name,
               fi.size_bytes, fi.owner_name, fi.section_name,
               fi.mtime_utc
          FROM policy_violations pv
          JOIN file_inventory fi ON pv.file_id = fi.file_id
        {where}
        ORDER BY fi.size_bytes DESC
        LIMIT ?
        """,
        params + [limit],
    ).fetchall()
    return [dict(r) for r in rows]


def stale_by_section(
    conn: sqlite3.Connection, run_id: int | None = None, days: int = 2555
) -> list[dict]:
    """Flagged files not modified in `days` days, grouped by section."""
    where_clauses = ["fi.mtime_utc <= datetime('now', ?)"]
    params: list = [f"-{days} days"]
    if run_id is not None:
        where_clauses.append("pv.run_id = ?")
        params.append(run_id)
    where = "WHERE " + " AND ".join(where_clauses)
    rows = conn.execute(
        f"""
        SELECT COALESCE(fi.section_name, '(no section)') AS section_name,
               COUNT(DISTINCT fi.file_id) AS stale_count,
               COALESCE(SUM(fi.size_bytes), 0) AS total_bytes
          FROM policy_violations pv
          JOIN file_inventory fi ON pv.file_id = fi.file_id
        {where}
        GROUP BY fi.section_name
        ORDER BY stale_count DESC
        """,
        params,
    ).fetchall()
    return [dict(r) for r in rows]
