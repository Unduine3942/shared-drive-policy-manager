import json
import sqlite3
from datetime import datetime, timezone
from typing import Any


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SettingsRepo:
    def get(self, conn: sqlite3.Connection, key: str, default: Any = None) -> Any:
        row = conn.execute(
            "SELECT value_json FROM app_settings WHERE key = ?", (key,)
        ).fetchone()
        return json.loads(row["value_json"]) if row else default

    def set(self, conn: sqlite3.Connection, key: str, value: Any) -> None:
        conn.execute(
            """
            INSERT INTO app_settings (key, value_json, updated_at_utc)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE
                SET value_json = excluded.value_json,
                    updated_at_utc = excluded.updated_at_utc
            """,
            (key, json.dumps(value), _utcnow()),
        )
        conn.commit()

    def get_all(self, conn: sqlite3.Connection) -> dict[str, Any]:
        rows = conn.execute("SELECT key, value_json FROM app_settings").fetchall()
        return {r["key"]: json.loads(r["value_json"]) for r in rows}


class ScanRootRepo:
    def list_active(self, conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute(
            "SELECT * FROM scan_roots WHERE active = 1 ORDER BY label"
        ).fetchall()
        return [dict(r) for r in rows]

    def get(self, conn: sqlite3.Connection, root_id: int) -> dict | None:
        row = conn.execute(
            "SELECT * FROM scan_roots WHERE root_id = ?", (root_id,)
        ).fetchone()
        return dict(row) if row else None

    def create(
        self,
        conn: sqlite3.Connection,
        label: str,
        root_path: str,
        exclude_globs: list[str] | None = None,
        max_depth: int | None = None,
        follow_symlinks: bool = False,
    ) -> int:
        now = _utcnow()
        cur = conn.execute(
            """
            INSERT INTO scan_roots
                (label, root_path, active, include_globs_json, exclude_globs_json,
                 max_depth, follow_symlinks, created_at_utc, updated_at_utc)
            VALUES (?, ?, 1, '[]', ?, ?, ?, ?, ?)
            """,
            (
                label,
                root_path,
                json.dumps(exclude_globs or []),
                max_depth,
                int(follow_symlinks),
                now,
                now,
            ),
        )
        conn.commit()
        return cur.lastrowid

    def update(self, conn: sqlite3.Connection, root_id: int, **fields) -> None:
        allowed = {
            "label", "root_path", "active", "include_globs_json",
            "exclude_globs_json", "max_depth", "follow_symlinks",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        updates["updated_at_utc"] = _utcnow()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE scan_roots SET {set_clause} WHERE root_id = ?",
            list(updates.values()) + [root_id],
        )
        conn.commit()

    def deactivate(self, conn: sqlite3.Connection, root_id: int) -> None:
        conn.execute(
            "UPDATE scan_roots SET active = 0, updated_at_utc = ? WHERE root_id = ?",
            (_utcnow(), root_id),
        )
        conn.commit()


class SectionMapRepo:
    def list_active(self, conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute(
            "SELECT * FROM section_map WHERE active = 1 ORDER BY path_prefix"
        ).fetchall()
        return [dict(r) for r in rows]

    def find_section(self, conn: sqlite3.Connection, path: str) -> str | None:
        rows = conn.execute(
            "SELECT section_name, path_prefix FROM section_map WHERE active = 1"
        ).fetchall()
        path_lower = path.lower()
        best: tuple[str, str] | None = None
        for row in rows:
            prefix = row["path_prefix"].lower()
            if path_lower.startswith(prefix):
                if best is None or len(prefix) > len(best[1]):
                    best = (row["section_name"], prefix)
        return best[0] if best else None

    def create(
        self,
        conn: sqlite3.Connection,
        section_name: str,
        path_prefix: str,
        business_owner: str | None = None,
        notes: str | None = None,
    ) -> int:
        now = _utcnow()
        cur = conn.execute(
            """
            INSERT INTO section_map
                (section_name, path_prefix, business_owner, notes, active,
                 created_at_utc, updated_at_utc)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (section_name, path_prefix, business_owner, notes, now, now),
        )
        conn.commit()
        return cur.lastrowid

    def update(
        self,
        conn: sqlite3.Connection,
        section_id: int,
        section_name: str,
        path_prefix: str,
        business_owner: str | None = None,
        notes: str | None = None,
    ) -> None:
        conn.execute(
            """
            UPDATE section_map
               SET section_name = ?, path_prefix = ?,
                   business_owner = ?, notes = ?,
                   updated_at_utc = ?
             WHERE section_id = ?
            """,
            (section_name, path_prefix, business_owner, notes, _utcnow(), section_id),
        )
        conn.commit()

    def delete(self, conn: sqlite3.Connection, section_id: int) -> None:
        conn.execute(
            "UPDATE section_map SET active = 0 WHERE section_id = ?",
            (section_id,),
        )
        conn.commit()


class ScanRunRepo:
    def get_latest(self, conn: sqlite3.Connection) -> dict | None:
        row = conn.execute(
            "SELECT * FROM scan_runs ORDER BY run_id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def list_all(self, conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute(
            "SELECT * FROM scan_runs ORDER BY run_id DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def list_resumable(self, conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute(
            "SELECT * FROM scan_runs WHERE status = 'running' ORDER BY run_id DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def create(self, conn: sqlite3.Connection, run_type: str) -> int:
        cur = conn.execute(
            "INSERT INTO scan_runs (run_type, status, started_at_utc) VALUES (?, 'pending', ?)",
            (run_type, _utcnow()),
        )
        conn.commit()
        return cur.lastrowid

    def set_running(self, conn: sqlite3.Connection, run_id: int, root_count: int) -> None:
        conn.execute(
            "UPDATE scan_runs SET status = 'running', root_count = ? WHERE run_id = ?",
            (root_count, run_id),
        )
        conn.commit()

    def finish(
        self,
        conn: sqlite3.Connection,
        run_id: int,
        status: str,
        message: str | None = None,
    ) -> None:
        conn.execute(
            "UPDATE scan_runs SET status = ?, ended_at_utc = ?, message = ? WHERE run_id = ?",
            (status, _utcnow(), message, run_id),
        )
        conn.commit()

    def increment_counters(
        self,
        conn: sqlite3.Connection,
        run_id: int,
        dirs: int = 0,
        files: int = 0,
        bytez: int = 0,
        violations: int = 0,
        errors: int = 0,
    ) -> None:
        conn.execute(
            """
            UPDATE scan_runs SET
                directories_seen  = directories_seen  + ?,
                files_seen        = files_seen        + ?,
                bytes_seen        = bytes_seen        + ?,
                violations_seen   = violations_seen   + ?,
                errors_seen       = errors_seen       + ?
            WHERE run_id = ?
            """,
            (dirs, files, bytez, violations, errors, run_id),
        )
        conn.commit()

    def delete(self, conn: sqlite3.Connection, run_id: int) -> None:
        """Hard-delete a scan run and all dependent records.

        file_inventory rows whose *only* run reference is this run are deleted;
        rows that have other run references are patched so neither FK points here.
        Raises ValueError if the run is currently in 'running' status.
        """
        row = conn.execute(
            "SELECT status FROM scan_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return
        if row["status"] == "running":
            raise ValueError("Cannot delete a run that is currently running.")

        # review_actions → policy_violations → scan_errors → scan_directories
        conn.execute(
            """
            DELETE FROM review_actions
             WHERE violation_id IN (
                 SELECT violation_id FROM policy_violations WHERE run_id = ?
             )
            """,
            (run_id,),
        )
        conn.execute("DELETE FROM policy_violations WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM scan_errors WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM scan_directories WHERE run_id = ?", (run_id,))

        # file_inventory: only seen in this run → delete entirely
        conn.execute(
            """
            DELETE FROM file_inventory
             WHERE first_seen_run_id = ? AND last_seen_run_id = ?
            """,
            (run_id, run_id),
        )
        # first_seen was this run but file was seen later → slide forward
        conn.execute(
            """
            UPDATE file_inventory
               SET first_seen_run_id = last_seen_run_id
             WHERE first_seen_run_id = ? AND last_seen_run_id != ?
            """,
            (run_id, run_id),
        )
        # last_seen was this run but file was seen earlier → slide back
        conn.execute(
            """
            UPDATE file_inventory
               SET last_seen_run_id = first_seen_run_id
             WHERE last_seen_run_id = ? AND first_seen_run_id != ?
            """,
            (run_id, run_id),
        )

        conn.execute("DELETE FROM scan_runs WHERE run_id = ?", (run_id,))
        conn.commit()


class PolicyRepo:
    def list_all(self, conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute(
            "SELECT * FROM policies ORDER BY severity DESC, name"
        ).fetchall()
        return [dict(r) for r in rows]

    def list_active(self, conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute(
            "SELECT * FROM policies WHERE enabled = 1 ORDER BY severity DESC, name"
        ).fetchall()
        return [dict(r) for r in rows]

    def get(self, conn: sqlite3.Connection, policy_id: int) -> dict | None:
        row = conn.execute(
            "SELECT * FROM policies WHERE policy_id = ?", (policy_id,)
        ).fetchone()
        return dict(row) if row else None

    def create(
        self,
        conn: sqlite3.Connection,
        name: str,
        description: str,
        severity: str,
        match_mode: str,
        scope_prefixes: list[str] | None = None,
        enabled: bool = False,
    ) -> int:
        now = _utcnow()
        cur = conn.execute(
            """
            INSERT INTO policies
                (name, description, enabled, severity, match_mode,
                 scope_prefixes_json, created_at_utc, updated_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                description,
                int(enabled),
                severity,
                match_mode,
                json.dumps(scope_prefixes or []),
                now,
                now,
            ),
        )
        conn.commit()
        return cur.lastrowid

    def update(self, conn: sqlite3.Connection, policy_id: int, **fields) -> None:
        allowed = {
            "name", "description", "enabled", "severity",
            "match_mode", "scope_prefixes_json",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        updates["updated_at_utc"] = _utcnow()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE policies SET {set_clause} WHERE policy_id = ?",
            list(updates.values()) + [policy_id],
        )
        conn.commit()

    def delete(self, conn: sqlite3.Connection, policy_id: int) -> None:
        conn.execute("DELETE FROM policies WHERE policy_id = ?", (policy_id,))
        conn.commit()


class PolicyRuleRepo:
    def list_for_policy(self, conn: sqlite3.Connection, policy_id: int) -> list[dict]:
        rows = conn.execute(
            "SELECT * FROM policy_rules WHERE policy_id = ? ORDER BY sort_order",
            (policy_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def create(
        self,
        conn: sqlite3.Connection,
        policy_id: int,
        field_name: str,
        operator: str,
        value: Any,
        case_sensitive: bool = False,
        negated: bool = False,
        sort_order: int = 0,
    ) -> int:
        now = _utcnow()
        cur = conn.execute(
            """
            INSERT INTO policy_rules
                (policy_id, field_name, operator, value_json,
                 case_sensitive, negated, sort_order,
                 created_at_utc, updated_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                policy_id,
                field_name,
                operator,
                json.dumps(value),
                int(case_sensitive),
                int(negated),
                sort_order,
                now,
                now,
            ),
        )
        conn.commit()
        return cur.lastrowid

    def delete(self, conn: sqlite3.Connection, rule_id: int) -> None:
        conn.execute("DELETE FROM policy_rules WHERE rule_id = ?", (rule_id,))
        conn.commit()

    def delete_for_policy(self, conn: sqlite3.Connection, policy_id: int) -> None:
        conn.execute("DELETE FROM policy_rules WHERE policy_id = ?", (policy_id,))
        conn.commit()


class FileInventoryRepo:
    def count(self, conn: sqlite3.Connection) -> int:
        return conn.execute(
            "SELECT COUNT(*) FROM file_inventory WHERE is_deleted = 0"
        ).fetchone()[0]

    def total_bytes(self, conn: sqlite3.Connection) -> int:
        return conn.execute(
            "SELECT COALESCE(SUM(size_bytes), 0) FROM file_inventory WHERE is_deleted = 0"
        ).fetchone()[0]

    def upsert_batch(
        self,
        conn: sqlite3.Connection,
        records: list[dict],
        run_id: int,
    ) -> None:
        now = _utcnow()
        conn.executemany(
            """
            INSERT INTO file_inventory
                (root_id, path_hash, full_path, parent_path, name, extension,
                 section_name, size_bytes, ctime_utc, mtime_utc, atime_utc,
                 owner_sid, owner_name, doc_creator, doc_modifier,
                 file_attrs, path_depth, path_length,
                 is_empty, first_seen_run_id, last_seen_run_id, is_deleted,
                 last_error, updated_at_utc)
            VALUES
                (:root_id, :path_hash, :full_path, :parent_path, :name, :extension,
                 :section_name, :size_bytes, :ctime_utc, :mtime_utc, :atime_utc,
                 :owner_sid, :owner_name, :doc_creator, :doc_modifier,
                 :file_attrs, :path_depth, :path_length,
                 :is_empty, :run_id, :run_id, 0, :last_error, :now)
            ON CONFLICT(root_id, path_hash) DO UPDATE SET
                full_path        = excluded.full_path,
                parent_path      = excluded.parent_path,
                name             = excluded.name,
                extension        = excluded.extension,
                section_name     = excluded.section_name,
                size_bytes       = excluded.size_bytes,
                ctime_utc        = excluded.ctime_utc,
                mtime_utc        = excluded.mtime_utc,
                atime_utc        = excluded.atime_utc,
                owner_sid        = excluded.owner_sid,
                owner_name       = excluded.owner_name,
                doc_creator      = excluded.doc_creator,
                doc_modifier     = excluded.doc_modifier,
                file_attrs       = excluded.file_attrs,
                path_depth       = excluded.path_depth,
                path_length      = excluded.path_length,
                is_empty         = excluded.is_empty,
                last_seen_run_id = excluded.last_seen_run_id,
                is_deleted       = 0,
                last_error       = excluded.last_error,
                updated_at_utc   = excluded.updated_at_utc
            """,
            [{**r, "run_id": run_id, "now": now} for r in records],
        )

    def touch_by_hashes(
        self,
        conn: sqlite3.Connection,
        root_id: int,
        path_hashes: list[str],
        run_id: int,
    ) -> None:
        if not path_hashes:
            return
        now = _utcnow()
        for i in range(0, len(path_hashes), 900):
            chunk = path_hashes[i : i + 900]
            placeholders = ",".join("?" * len(chunk))
            conn.execute(
                f"""
                UPDATE file_inventory
                   SET last_seen_run_id = ?, is_deleted = 0, updated_at_utc = ?
                 WHERE root_id = ? AND path_hash IN ({placeholders})
                """,
                [run_id, now, root_id] + chunk,
            )

    def get_stats_for_dir(
        self, conn: sqlite3.Connection, root_id: int, parent_path: str
    ) -> dict[str, tuple[str | None, int]]:
        rows = conn.execute(
            """
            SELECT path_hash, mtime_utc, size_bytes
              FROM file_inventory
             WHERE root_id = ? AND parent_path = ? AND is_deleted = 0
            """,
            (root_id, parent_path),
        ).fetchall()
        return {r["path_hash"]: (r["mtime_utc"], r["size_bytes"]) for r in rows}

    def mark_deleted(
        self, conn: sqlite3.Connection, root_id: int, run_id: int
    ) -> int:
        cur = conn.execute(
            """
            UPDATE file_inventory
               SET is_deleted = 1, updated_at_utc = ?
             WHERE root_id = ? AND last_seen_run_id != ? AND is_deleted = 0
            """,
            (_utcnow(), root_id, run_id),
        )
        return cur.rowcount


def _violation_clauses(
    run_id: int | None,
    policy_id: int | None,
    severity: str | None,
    status: str | None,
    section: str | None,
    owner_contains: str | None,
    extension: str | None,
    path_contains: str | None,
    min_size: int | None,
    mtime_from: str | None,
    mtime_to: str | None,
) -> tuple[list[str], list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if run_id is not None:
        clauses.append("pv.run_id = ?")
        params.append(run_id)
    if policy_id is not None:
        clauses.append("pv.policy_id = ?")
        params.append(policy_id)
    if severity:
        clauses.append("pv.severity = ?")
        params.append(severity)
    if status:
        clauses.append("pv.status = ?")
        params.append(status)
    if section:
        clauses.append("fi.section_name = ?")
        params.append(section)
    if owner_contains:
        clauses.append("fi.owner_name LIKE ?")
        params.append(f"%{owner_contains}%")
    if extension:
        ext = extension.lower()
        if not ext.startswith("."):
            ext = "." + ext
        clauses.append("fi.extension = ?")
        params.append(ext)
    if path_contains:
        clauses.append("fi.full_path LIKE ?")
        params.append(f"%{path_contains}%")
    if min_size is not None:
        clauses.append("fi.size_bytes >= ?")
        params.append(min_size)
    if mtime_from:
        clauses.append("fi.mtime_utc >= ?")
        params.append(mtime_from)
    if mtime_to:
        clauses.append("fi.mtime_utc <= ?")
        params.append(mtime_to)
    return clauses, params


class ViolationRepo:
    def insert_batch(self, conn: sqlite3.Connection, violations: list[dict]) -> None:
        now = _utcnow()
        conn.executemany(
            """
            INSERT INTO policy_violations
                (run_id, file_id, policy_id, severity, reason,
                 status, created_at_utc)
            VALUES
                (:run_id, :file_id, :policy_id, :severity, :reason,
                 'open', :now)
            """,
            [{**v, "now": now} for v in violations],
        )

    def count_open(self, conn: sqlite3.Connection, run_id: int | None = None) -> int:
        if run_id is not None:
            return conn.execute(
                "SELECT COUNT(*) FROM policy_violations WHERE run_id=? AND status='open'",
                (run_id,),
            ).fetchone()[0]
        return conn.execute(
            "SELECT COUNT(*) FROM policy_violations WHERE status='open'"
        ).fetchone()[0]

    def count_critical_open(
        self, conn: sqlite3.Connection, run_id: int | None = None
    ) -> int:
        if run_id is not None:
            return conn.execute(
                "SELECT COUNT(*) FROM policy_violations "
                "WHERE run_id=? AND severity='critical' AND status='open'",
                (run_id,),
            ).fetchone()[0]
        return conn.execute(
            "SELECT COUNT(*) FROM policy_violations WHERE severity='critical' AND status='open'"
        ).fetchone()[0]

    def query(
        self,
        conn: sqlite3.Connection,
        *,
        run_id: int | None = None,
        policy_id: int | None = None,
        severity: str | None = None,
        status: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict]:
        clauses: list[str] = []
        params: list[Any] = []
        if run_id is not None:
            clauses.append("pv.run_id = ?")
            params.append(run_id)
        if policy_id is not None:
            clauses.append("pv.policy_id = ?")
            params.append(policy_id)
        if severity:
            clauses.append("pv.severity = ?")
            params.append(severity)
        if status:
            clauses.append("pv.status = ?")
            params.append(status)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = conn.execute(
            f"""
            SELECT pv.*, fi.full_path, fi.name, fi.size_bytes,
                   fi.owner_name, fi.owner_sid, fi.section_name, fi.mtime_utc, fi.ctime_utc,
                   p.name AS policy_name
              FROM policy_violations pv
              JOIN file_inventory fi ON pv.file_id = fi.file_id
              JOIN policies p ON pv.policy_id = p.policy_id
            {where}
            ORDER BY pv.violation_id DESC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        ).fetchall()
        return [dict(r) for r in rows]

    def update_status(
        self,
        conn: sqlite3.Connection,
        violation_id: int,
        status: str,
        reviewer: str | None = None,
        note: str | None = None,
    ) -> None:
        conn.execute(
            """
            UPDATE policy_violations
               SET status = ?, reviewer = ?, review_note = ?, reviewed_at_utc = ?
             WHERE violation_id = ?
            """,
            (status, reviewer, note, _utcnow(), violation_id),
        )
        conn.commit()

    def query_full(
        self,
        conn: sqlite3.Connection,
        *,
        run_id: int | None = None,
        policy_id: int | None = None,
        severity: str | None = None,
        status: str | None = None,
        section: str | None = None,
        owner_contains: str | None = None,
        extension: str | None = None,
        path_contains: str | None = None,
        min_size: int | None = None,
        mtime_from: str | None = None,
        mtime_to: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        clauses, params = _violation_clauses(
            run_id, policy_id, severity, status, section,
            owner_contains, extension, path_contains, min_size,
            mtime_from, mtime_to,
        )
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = conn.execute(
            f"""
            SELECT pv.violation_id, pv.run_id, pv.policy_id, pv.severity,
                   pv.reason, pv.status, pv.reviewer, pv.review_note,
                   pv.reviewed_at_utc, pv.created_at_utc,
                   fi.file_id, fi.full_path, fi.name AS file_name,
                   fi.size_bytes, fi.extension,
                   fi.owner_name, fi.section_name,
                   fi.doc_creator, fi.doc_modifier,
                   fi.mtime_utc, fi.ctime_utc,
                   p.name AS policy_name
              FROM policy_violations pv
              JOIN file_inventory fi ON pv.file_id = fi.file_id
              JOIN policies p ON pv.policy_id = p.policy_id
            {where}
            ORDER BY pv.violation_id DESC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        ).fetchall()
        return [dict(r) for r in rows]

    def count_full(
        self,
        conn: sqlite3.Connection,
        *,
        run_id: int | None = None,
        policy_id: int | None = None,
        severity: str | None = None,
        status: str | None = None,
        section: str | None = None,
        owner_contains: str | None = None,
        extension: str | None = None,
        path_contains: str | None = None,
        min_size: int | None = None,
        mtime_from: str | None = None,
        mtime_to: str | None = None,
    ) -> int:
        clauses, params = _violation_clauses(
            run_id, policy_id, severity, status, section,
            owner_contains, extension, path_contains, min_size,
            mtime_from, mtime_to,
        )
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        return conn.execute(
            f"""
            SELECT COUNT(*)
              FROM policy_violations pv
              JOIN file_inventory fi ON pv.file_id = fi.file_id
              JOIN policies p ON pv.policy_id = p.policy_id
            {where}
            """,
            params,
        ).fetchone()[0]

    def distinct_sections(
        self, conn: sqlite3.Connection, run_id: int | None = None
    ) -> list[str]:
        if run_id is not None:
            rows = conn.execute(
                """
                SELECT DISTINCT fi.section_name
                  FROM policy_violations pv
                  JOIN file_inventory fi ON pv.file_id = fi.file_id
                 WHERE pv.run_id = ? AND fi.section_name IS NOT NULL
                 ORDER BY fi.section_name
                """,
                (run_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT DISTINCT fi.section_name
                  FROM policy_violations pv
                  JOIN file_inventory fi ON pv.file_id = fi.file_id
                 WHERE fi.section_name IS NOT NULL
                 ORDER BY fi.section_name
                """
            ).fetchall()
        return [r[0] for r in rows]


class ScanDirectoryRepo:
    def seed(self, conn: sqlite3.Connection, entries: list[dict]) -> None:
        now = _utcnow()
        conn.executemany(
            """
            INSERT OR IGNORE INTO scan_directories
                (run_id, dir_hash, root_id, dir_path, parent_hash,
                 depth, status, dir_mtime, updated_at_utc)
            VALUES
                (:run_id, :dir_hash, :root_id, :dir_path, :parent_hash,
                 :depth, 'pending', :dir_mtime, :now)
            """,
            [{**e, "now": now, "dir_mtime": e.get("dir_mtime")} for e in entries],
        )
        conn.commit()

    def claim_pending(
        self, conn: sqlite3.Connection, run_id: int, limit: int = 4
    ) -> list[dict]:
        now = _utcnow()
        hashes = [
            r[0]
            for r in conn.execute(
                """
                SELECT dir_hash FROM scan_directories
                WHERE run_id = ? AND status = 'pending'
                LIMIT ?
                """,
                (run_id, limit),
            ).fetchall()
        ]
        if not hashes:
            return []
        placeholders = ",".join("?" * len(hashes))
        conn.execute(
            f"""
            UPDATE scan_directories
               SET status = 'in_progress', updated_at_utc = ?
             WHERE run_id = ? AND dir_hash IN ({placeholders})
            """,
            [now, run_id] + hashes,
        )
        conn.commit()
        rows = conn.execute(
            f"""
            SELECT * FROM scan_directories
             WHERE run_id = ? AND dir_hash IN ({placeholders})
            """,
            [run_id] + hashes,
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_scanned(
        self,
        conn: sqlite3.Connection,
        run_id: int,
        dir_hash: str,
        dir_mtime: str | None = None,
    ) -> None:
        conn.execute(
            "UPDATE scan_directories"
            " SET status='scanned', dir_mtime=?, updated_at_utc=?"
            " WHERE run_id=? AND dir_hash=?",
            (dir_mtime, _utcnow(), run_id, dir_hash),
        )

    def get_prev_dir_mtime(
        self, conn: sqlite3.Connection, dir_hash: str, current_run_id: int
    ) -> str | None:
        row = conn.execute(
            """
            SELECT sd.dir_mtime
              FROM scan_directories sd
              JOIN scan_runs sr ON sd.run_id = sr.run_id
             WHERE sd.dir_hash = ? AND sd.run_id < ?
               AND sr.status = 'completed' AND sd.status = 'scanned'
               AND sd.dir_mtime IS NOT NULL
             ORDER BY sd.run_id DESC LIMIT 1
            """,
            (dir_hash, current_run_id),
        ).fetchone()
        return row["dir_mtime"] if row else None

    def mark_error(
        self,
        conn: sqlite3.Connection,
        run_id: int,
        dir_hash: str,
        error: str,
    ) -> None:
        conn.execute(
            "UPDATE scan_directories SET status='error', last_error=?, updated_at_utc=? "
            "WHERE run_id=? AND dir_hash=?",
            (error, _utcnow(), run_id, dir_hash),
        )

    def reset_stale_in_progress(self, conn: sqlite3.Connection, run_id: int) -> None:
        conn.execute(
            "UPDATE scan_directories SET status='pending', updated_at_utc=? "
            "WHERE run_id=? AND status='in_progress'",
            (_utcnow(), run_id),
        )
        conn.commit()

    def has_pending(self, conn: sqlite3.Connection, run_id: int) -> bool:
        return (
            conn.execute(
                "SELECT COUNT(*) FROM scan_directories WHERE run_id=? AND status='pending'",
                (run_id,),
            ).fetchone()[0]
            > 0
        )


class ScanErrorRepo:
    def count(self, conn: sqlite3.Connection, run_id: int) -> int:
        return conn.execute(
            "SELECT COUNT(*) FROM scan_errors WHERE run_id = ?", (run_id,)
        ).fetchone()[0]

    def insert(
        self,
        conn: sqlite3.Connection,
        run_id: int,
        path: str,
        operation: str,
        error_type: str,
        error_message: str,
        traceback_text: str | None = None,
        root_id: int | None = None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO scan_errors
                (run_id, root_id, path, operation, error_type,
                 error_message, traceback_text, created_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                root_id,
                path,
                operation,
                error_type,
                error_message,
                traceback_text,
                _utcnow(),
            ),
        )


class ReviewActionRepo:
    def insert(
        self,
        conn: sqlite3.Connection,
        violation_id: int,
        action_type: str,
        actor: str,
        note: str | None = None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO review_actions
                (violation_id, action_type, actor, note, created_at_utc)
            VALUES (?, ?, ?, ?, ?)
            """,
            (violation_id, action_type, actor, note, _utcnow()),
        )
        conn.commit()

    def list_for_violation(
        self,
        conn: sqlite3.Connection,
        violation_id: int,
    ) -> list[dict]:
        rows = conn.execute(
            """
            SELECT action_id, violation_id, action_type, actor, note, created_at_utc
              FROM review_actions
             WHERE violation_id = ?
             ORDER BY created_at_utc
            """,
            (violation_id,),
        ).fetchall()
        return [dict(r) for r in rows]


class MonitorSubjectRepo:
    def list_all(self, conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute(
            "SELECT * FROM monitor_subjects ORDER BY label"
        ).fetchall()
        return [dict(r) for r in rows]

    def add(
        self,
        conn: sqlite3.Connection,
        label: str,
        watch_path: str,
        watch_type: str,
        recursive: bool = False,
    ) -> int:
        now = _utcnow()
        cur = conn.execute(
            """
            INSERT INTO monitor_subjects
                (label, watch_path, watch_type, recursive, active, created_at_utc, updated_at_utc)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (label, watch_path, watch_type, int(recursive), now, now),
        )
        conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def remove(self, conn: sqlite3.Connection, subject_id: int) -> None:
        conn.execute(
            "DELETE FROM monitor_subjects WHERE subject_id = ?", (subject_id,)
        )
        conn.commit()

    def set_active(
        self, conn: sqlite3.Connection, subject_id: int, active: bool
    ) -> None:
        conn.execute(
            "UPDATE monitor_subjects SET active=?, updated_at_utc=? WHERE subject_id=?",
            (int(active), _utcnow(), subject_id),
        )
        conn.commit()


class MonitorEventRepo:
    def add_batch(self, conn: sqlite3.Connection, events: list[dict]) -> None:
        if not events:
            return
        conn.executemany(
            """
            INSERT INTO monitor_events
                (subject_id, event_type, path, old_path, created_at_utc)
            VALUES (:subject_id, :event_type, :path, :old_path, :created_at_utc)
            """,
            events,
        )
        conn.commit()

    def list_recent(
        self,
        conn: sqlite3.Connection,
        *,
        subject_id: int | None = None,
        event_type: str | None = None,
        limit: int = 500,
    ) -> list[dict]:
        clauses: list[str] = []
        params: list[object] = []
        if subject_id is not None:
            clauses.append("me.subject_id = ?")
            params.append(subject_id)
        if event_type is not None:
            clauses.append("me.event_type = ?")
            params.append(event_type)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        limit_clause = f"LIMIT {int(limit)}" if limit > 0 else ""
        rows = conn.execute(
            f"""
            SELECT me.*, ms.label AS subject_label
              FROM monitor_events me
              JOIN monitor_subjects ms ON me.subject_id = ms.subject_id
            {where}
            ORDER BY me.event_id DESC
            {limit_clause}
            """,
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def clear(
        self,
        conn: sqlite3.Connection,
        subject_id: int | None = None,
    ) -> None:
        if subject_id is not None:
            conn.execute(
                "DELETE FROM monitor_events WHERE subject_id = ?", (subject_id,)
            )
        else:
            conn.execute("DELETE FROM monitor_events")
        conn.commit()

    def export_csv(
        self,
        conn: sqlite3.Connection,
        file_path: str,
        *,
        subject_id: int | None = None,
        event_type: str | None = None,
    ) -> int:
        import csv

        rows = self.list_recent(
            conn, subject_id=subject_id, event_type=event_type, limit=0
        )
        if not rows:
            return 0
        with open(file_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        return len(rows)


class UserRepo:
    def count(self, conn: sqlite3.Connection) -> int:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    def get_by_username(
        self, conn: sqlite3.Connection, username: str
    ) -> dict | None:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? AND active = 1",
            (username,),
        ).fetchone()
        return dict(row) if row else None

    def list_non_secret(self, conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute(
            "SELECT * FROM users WHERE role != 'secret_admin' AND active = 1"
            " ORDER BY user_id"
        ).fetchall()
        return [dict(r) for r in rows]

    def create_user(
        self,
        conn: sqlite3.Connection,
        username: str,
        password_hash: str,
        salt: str,
        role: str,
        created_by: str,
    ) -> int:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        cur = conn.execute(
            """
            INSERT INTO users (username, password_hash, salt, role, created_by, created_at_utc)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (username, password_hash, salt, role, created_by, now),
        )
        conn.commit()
        return cur.lastrowid

    def seed_default_users(self, conn: sqlite3.Connection) -> None:
        # One-time seed: runs only on a fresh database (count == 0).
        # Subsequent launches skip this entirely; passwords are changed via
        # the Manage Users page — never by re-seeding.
        # SECURITY NOTE: The plaintext strings below are the intended initial
        # credentials for this internal airgapped tool.  They are hashed with
        # SHA-256 + a unique random salt before being written to the database;
        # no plaintext is stored.  The viewer account has no password.
        if self.count(conn) > 0:
            return

        from shared_drive_manager.core.auth import generate_salt, hash_password

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # (username, initial_password, role, created_by)
        # Passwords are immediately hashed; plaintext never persists.
        accounts = [
            ("viewer",      "",                   "viewer",       "system"),
            ("admin",       "Marines!1Marines!1",  "admin",       "system"),
            ("BigBrother",  "D@T@T3@M",            "secret_admin", "system"),
        ]

        for username, password, role, created_by in accounts:
            salt = generate_salt()
            pw_hash = hash_password(password, salt)
            conn.execute(
                """
                INSERT INTO users
                    (username, password_hash, salt, role, created_by, created_at_utc)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (username, pw_hash, salt, role, created_by, now),
            )

        conn.commit()


# ── FileHashRepo ────────────────────────────────────────────────────────────

class FileHashRepo:
    def upsert(
        self,
        conn: sqlite3.Connection,
        file_id: int,
        hash_type: str,
        hash_value: str,
    ) -> None:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            """
            INSERT INTO file_hashes (file_id, hash_type, hash_value, computed_at_utc)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(file_id, hash_type) DO UPDATE SET
                hash_value      = excluded.hash_value,
                computed_at_utc = excluded.computed_at_utc
            """,
            (file_id, hash_type, hash_value, now),
        )

    def get_duplicates(
        self,
        conn: sqlite3.Connection,
        hash_type: str,
        root_ids: list[int] | None = None,
    ) -> list[dict]:
        """Return file records that share a hash_value for the given hash_type."""
        base = """
            SELECT fi.file_id, fi.full_path, fi.name, fi.size_bytes,
                   fi.owner_name, fi.section_name, fh.hash_value, fh.computed_at_utc
            FROM file_hashes fh
            JOIN file_inventory fi ON fi.file_id = fh.file_id
            WHERE fh.hash_type = ?
              AND fh.hash_value IN (
                  SELECT hash_value FROM file_hashes
                  WHERE hash_type = ?
                  GROUP BY hash_value HAVING COUNT(*) > 1
              )
              AND fi.is_deleted = 0
        """
        params: list = [hash_type, hash_type]
        if root_ids:
            placeholders = ",".join("?" * len(root_ids))
            base += f" AND fi.root_id IN ({placeholders})"
            params.extend(root_ids)
        base += " ORDER BY fh.hash_value, fi.size_bytes DESC, fi.full_path"
        rows = conn.execute(base, params).fetchall()
        return [dict(r) for r in rows]

    def count_hashed(self, conn: sqlite3.Connection, hash_type: str) -> int:
        return conn.execute(
            "SELECT COUNT(*) FROM file_hashes WHERE hash_type = ?", (hash_type,)
        ).fetchone()[0]

    def delete_for_file(self, conn: sqlite3.Connection, file_id: int) -> None:
        conn.execute("DELETE FROM file_hashes WHERE file_id = ?", (file_id,))


# ── OwnerContactRepo ────────────────────────────────────────────────────────

class OwnerContactRepo:
    def list_all(self, conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute(
            "SELECT * FROM owner_contact_map ORDER BY owner_name"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_by_owner(self, conn: sqlite3.Connection, owner_name: str) -> dict | None:
        row = conn.execute(
            "SELECT * FROM owner_contact_map WHERE owner_name = ?", (owner_name,)
        ).fetchone()
        return dict(row) if row else None

    def upsert(
        self,
        conn: sqlite3.Connection,
        owner_name: str,
        display_name: str | None = None,
        email: str | None = None,
        department: str | None = None,
        notes: str | None = None,
    ) -> int:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        cur = conn.execute(
            """
            INSERT INTO owner_contact_map
                (owner_name, display_name, email, department, notes,
                 created_at_utc, updated_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(owner_name) DO UPDATE SET
                display_name   = excluded.display_name,
                email          = excluded.email,
                department     = excluded.department,
                notes          = excluded.notes,
                updated_at_utc = excluded.updated_at_utc
            """,
            (owner_name, display_name, email, department, notes, now, now),
        )
        conn.commit()
        return cur.lastrowid

    def get_violation_summary(self, conn: sqlite3.Connection) -> list[dict]:
        """Ranked list of owners with total, open, critical violation counts."""
        rows = conn.execute(
            """
            SELECT
                COALESCE(fi.owner_name, '(unknown)') AS owner_name,
                COUNT(pv.violation_id)                                      AS total_violations,
                SUM(CASE WHEN pv.status = 'open'       THEN 1 ELSE 0 END)  AS open_violations,
                SUM(CASE WHEN pv.severity = 'critical'  THEN 1 ELSE 0 END) AS critical_violations,
                SUM(fi.size_bytes)                                          AS total_bytes,
                ocm.display_name,
                ocm.email,
                ocm.department
            FROM policy_violations pv
            JOIN file_inventory fi ON fi.file_id = pv.file_id
            LEFT JOIN owner_contact_map ocm ON ocm.owner_name = fi.owner_name
            WHERE fi.is_deleted = 0
            GROUP BY fi.owner_name
            ORDER BY open_violations DESC, critical_violations DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


# ── DraftPolicyRepo ─────────────────────────────────────────────────────────

class DraftPolicyRepo:
    def list_pending(self, conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute(
            "SELECT * FROM policy_drafts WHERE status = 'pending' ORDER BY created_at_utc"
        ).fetchall()
        return [dict(r) for r in rows]

    def list_all(self, conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute(
            "SELECT * FROM policy_drafts ORDER BY created_at_utc DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get(self, conn: sqlite3.Connection, draft_id: int) -> dict | None:
        row = conn.execute(
            "SELECT * FROM policy_drafts WHERE draft_id = ?", (draft_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_rules(self, conn: sqlite3.Connection, draft_id: int) -> list[dict]:
        rows = conn.execute(
            "SELECT * FROM policy_draft_rules WHERE draft_id = ? ORDER BY sort_order",
            (draft_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def create(
        self,
        conn: sqlite3.Connection,
        name: str,
        description: str | None,
        severity: str,
        match_mode: str,
        scope_prefixes_json: str,
        submitted_by: str,
        rules: list[dict],
    ) -> int:
        import json as _json
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        cur = conn.execute(
            """
            INSERT INTO policy_drafts
                (name, description, severity, match_mode, scope_prefixes_json,
                 status, submitted_by, created_at_utc, updated_at_utc)
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)
            """,
            (name, description, severity, match_mode, scope_prefixes_json,
             submitted_by, now, now),
        )
        draft_id = cur.lastrowid
        for order, rule in enumerate(rules):
            conn.execute(
                """
                INSERT INTO policy_draft_rules
                    (draft_id, field_name, operator, value_json,
                     case_sensitive, negated, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    rule["field_name"],
                    rule["operator"],
                    _json.dumps(rule.get("value")),
                    int(rule.get("case_sensitive", False)),
                    int(rule.get("negated", False)),
                    order,
                ),
            )
        conn.commit()
        return draft_id

    def approve(
        self,
        conn: sqlite3.Connection,
        draft_id: int,
        reviewed_by: str,
        review_note: str | None = None,
    ) -> int:
        """Approve draft: promote to live policies table, return new policy_id."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        draft = self.get(conn, draft_id)
        if draft is None:
            raise ValueError(f"Draft {draft_id} not found")

        conn.execute(
            """
            UPDATE policy_drafts
            SET status = 'approved', reviewed_by = ?, review_note = ?,
                reviewed_at_utc = ?, updated_at_utc = ?
            WHERE draft_id = ?
            """,
            (reviewed_by, review_note, now, now, draft_id),
        )

        cur = conn.execute(
            """
            INSERT INTO policies
                (name, description, enabled, severity, match_mode,
                 scope_prefixes_json, created_at_utc, updated_at_utc)
            VALUES (?, ?, 1, ?, ?, ?, ?, ?)
            """,
            (
                draft["name"],
                draft["description"],
                draft["severity"],
                draft["match_mode"],
                draft["scope_prefixes_json"],
                now,
                now,
            ),
        )
        policy_id = cur.lastrowid

        for rule in self.get_rules(conn, draft_id):
            conn.execute(
                """
                INSERT INTO policy_rules
                    (policy_id, field_name, operator, value_json,
                     case_sensitive, negated, sort_order,
                     created_at_utc, updated_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    policy_id,
                    rule["field_name"],
                    rule["operator"],
                    rule["value_json"],
                    rule["case_sensitive"],
                    rule["negated"],
                    rule["sort_order"],
                    now,
                    now,
                ),
            )

        conn.commit()
        return policy_id

    def reject(
        self,
        conn: sqlite3.Connection,
        draft_id: int,
        reviewed_by: str,
        review_note: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            """
            UPDATE policy_drafts
            SET status = 'rejected', reviewed_by = ?, review_note = ?,
                reviewed_at_utc = ?, updated_at_utc = ?
            WHERE draft_id = ?
            """,
            (reviewed_by, review_note, now, now, draft_id),
        )
        conn.commit()

    def count_pending(self, conn: sqlite3.Connection) -> int:
        return conn.execute(
            "SELECT COUNT(*) FROM policy_drafts WHERE status = 'pending'"
        ).fetchone()[0]
