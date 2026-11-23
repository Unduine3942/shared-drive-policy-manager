"""Application bootstrap — owns DB connection, settings cache, and all repos."""
from __future__ import annotations

import logging
import sqlite3
import sys
import tkinter as tk
import tkinter.ttk
from pathlib import Path

from shared_drive_manager import config
from shared_drive_manager.db.connection import open_connection
from shared_drive_manager.db.migrations import run_migrations
from shared_drive_manager.db.repositories import (
    DraftPolicyRepo,
    FileHashRepo,
    FileInventoryRepo,
    MonitorEventRepo,
    MonitorSubjectRepo,
    OwnerContactRepo,
    PolicyRepo,
    PolicyRuleRepo,
    ReviewActionRepo,
    ScanDirectoryRepo,
    ScanErrorRepo,
    ScanRootRepo,
    ScanRunRepo,
    SectionMapRepo,
    SettingsRepo,
    UserRepo,
    ViolationRepo,
)
from shared_drive_manager.core.file_monitor import MonitorController
from shared_drive_manager.core.scan_controller import ScanController
from shared_drive_manager.logging_config import setup_logging

log = logging.getLogger(__name__)


class Application:
    def __init__(self) -> None:
        self.conn: sqlite3.Connection | None = None
        self.db_path: Path = config.DB_DEFAULT_PATH
        self.settings: dict = {}
        self.authenticated_user: dict | None = None

        self.settings_repo = SettingsRepo()
        self.user_repo = UserRepo()
        self.scan_root_repo = ScanRootRepo()
        self.section_repo = SectionMapRepo()
        self.scan_run_repo = ScanRunRepo()
        self.policy_repo = PolicyRepo()
        self.rule_repo = PolicyRuleRepo()
        self.file_repo = FileInventoryRepo()
        self.violation_repo = ViolationRepo()
        self.scan_dir_repo = ScanDirectoryRepo()
        self.scan_error_repo = ScanErrorRepo()
        self.review_repo = ReviewActionRepo()
        self.monitor_subject_repo = MonitorSubjectRepo()
        self.monitor_event_repo = MonitorEventRepo()
        self.file_hash_repo = FileHashRepo()
        self.owner_contact_repo = OwnerContactRepo()
        self.draft_policy_repo = DraftPolicyRepo()
        self.monitor_controller = MonitorController()
        self.scan_controller = ScanController(self)

    def run(self) -> None:
        self._boot()
        self._start_ui()

    # ------------------------------------------------------------------
    # Boot sequence
    # ------------------------------------------------------------------

    def _boot(self) -> None:
        config.APP_DIR.mkdir(parents=True, exist_ok=True)
        config.LOG_DIR.mkdir(parents=True, exist_ok=True)

        setup_logging(config.LOG_DIR, config.DEFAULT_LOG_LEVEL)
        log.info("Starting Shared Drive Policy Manager")

        self._open_db(config.DB_DEFAULT_PATH)
        run_migrations(self.conn)

        self.settings = self._load_settings()

        log_level = self.settings.get("log_level", config.DEFAULT_LOG_LEVEL)
        setup_logging(config.LOG_DIR, log_level)

        override_path = self.settings.get("db_path", "")
        if override_path:
            candidate = Path(override_path).resolve()
            if candidate != self.db_path:
                try:
                    candidate.parent.mkdir(parents=True, exist_ok=True)
                    self._open_db(candidate)
                    run_migrations(self.conn)
                    log.info("Using override DB path: %s", candidate)
                except Exception as exc:
                    log.warning(
                        "Cannot open override DB '%s': %s. Falling back to default.",
                        candidate,
                        exc,
                    )
                    self._open_db(config.DB_DEFAULT_PATH)

        log.info("Boot complete. DB: %s", self.db_path)

    def _open_db(self, path: Path) -> None:
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
        self.conn = open_connection(path)
        self.db_path = path

    def _load_settings(self) -> dict:
        defaults: dict = {
            "db_path": str(config.DB_DEFAULT_PATH),
            "export_folder": config.DEFAULT_EXPORT_FOLDER,
            "max_workers": config.DEFAULT_WORKERS,
            "batch_size": config.DEFAULT_BATCH_SIZE,
            "long_path_threshold": config.LONG_PATH_THRESHOLD,
            "max_error_threshold": config.MAX_ERROR_THRESHOLD,
            "collect_owner": config.DEFAULT_COLLECT_OWNER,
            "collect_acl": config.DEFAULT_COLLECT_ACL,
            "log_level": config.DEFAULT_LOG_LEVEL,
        }
        stored = self.settings_repo.get_all(self.conn)
        return {**defaults, **stored}

    # ------------------------------------------------------------------
    # UI startup
    # ------------------------------------------------------------------

    def _start_ui(self) -> None:
        root = tk.Tk()
        self.root = root
        root.withdraw()

        from shared_drive_manager.ui.theme import configure_styles
        configure_styles(root)

        from shared_drive_manager.ui.login_window import LoginWindow
        login = LoginWindow(root, self)
        root.wait_window(login.dialog)

        if self.authenticated_user is None:
            root.destroy()
            return

        from shared_drive_manager.ui.main_window import MainWindow
        self.main_window = MainWindow(root, self)
        log.info("UI ready — role: %s", self.authenticated_user["role"])
        root.deiconify()
        root.mainloop()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_db(self) -> sqlite3.Connection:
        if self.conn is None:
            raise RuntimeError("Database connection is not open.")
        return self.conn

    def get_setting(self, key: str, default=None):
        return self.settings.get(key, default)

    def save_setting(self, key: str, value) -> None:
        self.settings_repo.set(self.conn, key, value)
        self.settings[key] = value
