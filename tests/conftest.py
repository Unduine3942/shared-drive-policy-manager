"""pytest configuration and shared fixtures for Shared Drive Manager tests."""
import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database with the full schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # Apply schema
    schema_path = (
        Path(__file__).parent.parent
        / "shared_drive_manager"
        / "db"
        / "schema.sql"
    )
    schema_sql = schema_path.read_text(encoding="utf-8")
    conn.executescript(schema_sql)

    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()

    yield conn

    conn.close()
