"""Integration tests for shared_drive_manager.db.repositories module."""
from datetime import datetime, timezone

import pytest

from shared_drive_manager.db.repositories import ReviewActionRepo


def _utcnow() -> str:
    """Get current UTC time in ISO-8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_violation_counter = 0


def _setup_violation(conn, now):
    """Helper to set up a scan run, file, policy, and violation. Returns violation_id."""
    global _violation_counter
    _violation_counter += 1

    # Create scan run
    cur = conn.execute(
        "INSERT INTO scan_runs (run_type, status, started_at_utc) VALUES (?, ?, ?)",
        ("full", "completed", now),
    )
    run_id = cur.lastrowid

    # Create scan root with unique path
    root_path = rf"C:\Test{_violation_counter}"
    cur = conn.execute(
        """
        INSERT INTO scan_roots
            (label, root_path, active, include_globs_json, exclude_globs_json,
             max_depth, follow_symlinks, created_at_utc, updated_at_utc)
        VALUES (?, ?, 1, '[]', '[]', NULL, 0, ?, ?)
        """,
        (f"Test Root {_violation_counter}", root_path, now, now),
    )
    root_id = cur.lastrowid

    # Create file inventory
    file_path = rf"{root_path}\file.txt"
    cur = conn.execute(
        """
        INSERT INTO file_inventory
            (root_id, path_hash, full_path, parent_path, name, extension,
             size_bytes, path_depth, path_length, is_empty,
             first_seen_run_id, last_seen_run_id, is_deleted, updated_at_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """,
        (
            root_id, f"hash{_violation_counter}", file_path, root_path,
            "file.txt", ".txt", 1024, 2, 20, 0, run_id, run_id, now
        ),
    )
    file_id = cur.lastrowid

    # Create policy with unique name
    cur = conn.execute(
        """
        INSERT INTO policies
            (name, description, enabled, severity, match_mode,
             scope_prefixes_json, created_at_utc, updated_at_utc)
        VALUES (?, ?, 1, ?, ?, '[]', ?, ?)
        """,
        (f"Test Policy {_violation_counter}", "Test", "warning", "all", now, now),
    )
    policy_id = cur.lastrowid

    # Create violation
    cur = conn.execute(
        """
        INSERT INTO policy_violations
            (run_id, file_id, policy_id, severity, reason,
             status, created_at_utc)
        VALUES (?, ?, ?, ?, ?, 'open', ?)
        """,
        (run_id, file_id, policy_id, "warning", "Test violation", now),
    )
    violation_id = cur.lastrowid

    conn.commit()
    return violation_id


class TestReviewActionRepo:
    """Integration tests for ReviewActionRepo."""

    def test_insert_and_list_for_violation(self, in_memory_db):
        """Should insert review actions and list them for a violation."""
        conn = in_memory_db
        now = _utcnow()
        violation_id = _setup_violation(conn, now)

        # Test: Insert review actions
        repo = ReviewActionRepo()
        repo.insert(conn, violation_id, "reviewed", "admin", "This is fine")
        repo.insert(conn, violation_id, "marked_ignored", "admin", None)

        # Test: List review actions
        actions = repo.list_for_violation(conn, violation_id)
        assert len(actions) == 2
        assert actions[0]["action_type"] == "reviewed"
        assert actions[0]["actor"] == "admin"
        assert actions[0]["note"] == "This is fine"
        assert actions[1]["action_type"] == "marked_ignored"
        assert actions[1]["actor"] == "admin"
        assert actions[1]["note"] is None

    def test_list_for_nonexistent_violation(self, in_memory_db):
        """Listing actions for nonexistent violation should return empty list."""
        conn = in_memory_db
        repo = ReviewActionRepo()
        actions = repo.list_for_violation(conn, 9999)
        assert actions == []

    def test_actions_ordered_by_created_time(self, in_memory_db):
        """Actions should be returned in chronological order."""
        conn = in_memory_db
        now = _utcnow()
        violation_id = _setup_violation(conn, now)

        repo = ReviewActionRepo()
        repo.insert(conn, violation_id, "action1", "user1", "First")
        repo.insert(conn, violation_id, "action2", "user2", "Second")
        repo.insert(conn, violation_id, "action3", "user3", "Third")

        actions = repo.list_for_violation(conn, violation_id)
        assert len(actions) == 3
        # Should be in order of creation
        assert actions[0]["action_type"] == "action1"
        assert actions[1]["action_type"] == "action2"
        assert actions[2]["action_type"] == "action3"

    def test_insert_action_without_note(self, in_memory_db):
        """Inserting action without note should work."""
        conn = in_memory_db
        now = _utcnow()
        violation_id = _setup_violation(conn, now)

        repo = ReviewActionRepo()
        repo.insert(conn, violation_id, "action_type", "actor_name", None)

        actions = repo.list_for_violation(conn, violation_id)
        assert len(actions) == 1
        assert actions[0]["note"] is None

    def test_multiple_violations_separate_actions(self, in_memory_db):
        """Actions for different violations should not mix."""
        conn = in_memory_db
        now = _utcnow()
        violation_id1 = _setup_violation(conn, now)
        violation_id2 = _setup_violation(conn, now)

        repo = ReviewActionRepo()
        repo.insert(conn, violation_id1, "action1", "user", "Note1")
        repo.insert(conn, violation_id2, "action2", "user", "Note2")

        actions1 = repo.list_for_violation(conn, violation_id1)
        actions2 = repo.list_for_violation(conn, violation_id2)

        assert len(actions1) == 1
        assert len(actions2) == 1
        assert actions1[0]["action_type"] == "action1"
        assert actions2[0]["action_type"] == "action2"

    def test_review_action_has_all_fields(self, in_memory_db):
        """Review action should have all expected fields."""
        conn = in_memory_db
        now = _utcnow()
        violation_id = _setup_violation(conn, now)

        repo = ReviewActionRepo()
        repo.insert(conn, violation_id, "test_action", "test_user", "test_note")

        actions = repo.list_for_violation(conn, violation_id)
        action = actions[0]

        assert "action_id" in action
        assert "violation_id" in action
        assert "action_type" in action
        assert "actor" in action
        assert "note" in action
        assert "created_at_utc" in action

    def test_multiple_actions_different_types(self, in_memory_db):
        """Should support different action types for same violation."""
        conn = in_memory_db
        now = _utcnow()
        violation_id = _setup_violation(conn, now)

        action_types = ["reviewed", "marked_ignored", "escalated", "resolved"]
        repo = ReviewActionRepo()

        for action_type in action_types:
            repo.insert(conn, violation_id, action_type, "admin", f"Note for {action_type}")

        actions = repo.list_for_violation(conn, violation_id)
        assert len(actions) == len(action_types)

        returned_types = [a["action_type"] for a in actions]
        assert returned_types == action_types
