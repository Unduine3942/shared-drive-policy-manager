from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FileRecord:
    root_id: int
    path_hash: str
    full_path: str
    parent_path: str
    name: str
    extension: str
    size_bytes: int
    path_depth: int
    path_length: int
    is_empty: bool
    file_id: int | None = None
    section_name: str | None = None
    ctime_utc: str | None = None
    mtime_utc: str | None = None
    atime_utc: str | None = None
    owner_sid: str | None = None
    owner_name: str | None = None
    file_attrs: int | None = None
    last_error: str | None = None
    doc_creator: str | None = None
    doc_modifier: str | None = None


@dataclass
class Rule:
    rule_id: int
    policy_id: int
    field_name: str
    operator: str
    value: object
    case_sensitive: bool
    negated: bool
    sort_order: int


@dataclass
class Policy:
    policy_id: int
    name: str
    severity: str
    match_mode: str
    scope_prefixes: list[str]
    rules: list[Rule]
    enabled: bool = True


@dataclass
class Violation:
    run_id: int
    file_id: int
    policy_id: int
    severity: str
    reason: str


@dataclass
class ProgressEvent:
    files_delta: int = 0
    bytes_delta: int = 0
    violations_delta: int = 0
    errors_delta: int = 0
    dirs_delta: int = 0
    current_path: str = ""
    finished: bool = False
    status: str = ""


@dataclass
class MonitorEvent:
    subject_id: int
    subject_label: str
    event_type: str          # 'created' | 'modified' | 'deleted' | 'renamed'
    path: str
    old_path: str | None = None
    timestamp_utc: str = ""
    error: str | None = None  # set when the watcher thread dies unexpectedly
    stopped: bool = False     # sentinel: watcher for this subject has exited
