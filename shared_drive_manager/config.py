import os
from pathlib import Path

APP_NAME = "SharedDrivePolicyManager"


def _load_version() -> str:
    try:
        return (Path(__file__).resolve().parents[1] / "VERSION").read_text(
            encoding="utf-8").strip()
    except OSError:
        return "unknown"


APP_VERSION = _load_version()

_appdata = os.environ.get("LOCALAPPDATA", "")
APP_DIR: Path = (
    Path(_appdata) / APP_NAME if _appdata else Path.home() / f".{APP_NAME}"
)
DB_DEFAULT_PATH: Path = APP_DIR / "shared_drive_manager.sqlite3"
LOG_DIR: Path = APP_DIR / "logs"

LONG_PATH_THRESHOLD: int = 240
DEFAULT_WORKERS: int = 4
MAX_WORKERS: int = 16
DEFAULT_BATCH_SIZE: int = 2000
DEFAULT_FOLLOW_SYMLINKS: bool = False
DEFAULT_COLLECT_OWNER: bool = True
DEFAULT_COLLECT_ACL: bool = False
DEFAULT_LOG_LEVEL: str = "INFO"
DEFAULT_EXPORT_FOLDER: str = str(Path.home() / "Documents")

DEFAULT_EXCLUDE_GLOBS: list[str] = ["~$*", "*.tmp", "*.lock"]

MAX_ERROR_THRESHOLD: int = 0  # 0 = disabled; positive = stop scan after N errors

SCHEMA_VERSION: int = 1
