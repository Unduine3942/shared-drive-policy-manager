-- Shared Drive Policy Manager — canonical schema
-- All tables use CREATE TABLE IF NOT EXISTS for idempotent application.

CREATE TABLE IF NOT EXISTS app_settings (
    key             TEXT PRIMARY KEY,
    value_json      TEXT NOT NULL,
    updated_at_utc  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scan_roots (
    root_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    label                TEXT    NOT NULL,
    root_path            TEXT    NOT NULL UNIQUE,
    active               INTEGER NOT NULL DEFAULT 1,
    include_globs_json   TEXT    NOT NULL DEFAULT '[]',
    exclude_globs_json   TEXT    NOT NULL DEFAULT '[]',
    max_depth            INTEGER,
    follow_symlinks      INTEGER NOT NULL DEFAULT 0,
    created_at_utc       TEXT    NOT NULL,
    updated_at_utc       TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS section_map (
    section_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    section_name    TEXT    NOT NULL,
    path_prefix     TEXT    NOT NULL UNIQUE,
    business_owner  TEXT,
    notes           TEXT,
    active          INTEGER NOT NULL DEFAULT 1,
    created_at_utc  TEXT    NOT NULL,
    updated_at_utc  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS scan_runs (
    run_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type          TEXT    NOT NULL CHECK(run_type IN ('full', 'incremental', 'resume')),
    status            TEXT    NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'canceled', 'failed')),
    started_at_utc    TEXT,
    ended_at_utc      TEXT,
    root_count        INTEGER NOT NULL DEFAULT 0,
    directories_seen  INTEGER NOT NULL DEFAULT 0,
    files_seen        INTEGER NOT NULL DEFAULT 0,
    bytes_seen        INTEGER NOT NULL DEFAULT 0,
    violations_seen   INTEGER NOT NULL DEFAULT 0,
    errors_seen       INTEGER NOT NULL DEFAULT 0,
    message           TEXT
);

CREATE TABLE IF NOT EXISTS scan_directories (
    run_id          INTEGER NOT NULL,
    dir_hash        TEXT    NOT NULL,
    root_id         INTEGER NOT NULL,
    dir_path        TEXT    NOT NULL,
    parent_hash     TEXT,
    depth           INTEGER NOT NULL,
    status          TEXT    NOT NULL CHECK(status IN ('pending', 'in_progress', 'scanned', 'error', 'skipped')),
    last_error      TEXT,
    dir_mtime       TEXT,
    updated_at_utc  TEXT    NOT NULL,
    PRIMARY KEY (run_id, dir_hash),
    FOREIGN KEY (run_id)  REFERENCES scan_runs(run_id),
    FOREIGN KEY (root_id) REFERENCES scan_roots(root_id)
);

CREATE INDEX IF NOT EXISTS idx_scan_directories_status
    ON scan_directories(run_id, status);

CREATE INDEX IF NOT EXISTS idx_scan_directories_dir_hash
    ON scan_directories(dir_hash);

CREATE TABLE IF NOT EXISTS file_inventory (
    file_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    root_id           INTEGER NOT NULL,
    path_hash         TEXT    NOT NULL,
    full_path         TEXT    NOT NULL,
    parent_path       TEXT    NOT NULL,
    name              TEXT    NOT NULL,
    extension         TEXT    NOT NULL,
    section_name      TEXT,
    size_bytes        INTEGER NOT NULL,
    ctime_utc         TEXT,
    mtime_utc         TEXT,
    atime_utc         TEXT,
    owner_sid         TEXT,
    owner_name        TEXT,
    doc_creator       TEXT,
    doc_modifier      TEXT,
    file_attrs        INTEGER,
    path_depth        INTEGER NOT NULL,
    path_length       INTEGER NOT NULL,
    is_empty          INTEGER NOT NULL,
    first_seen_run_id INTEGER NOT NULL,
    last_seen_run_id  INTEGER NOT NULL,
    is_deleted        INTEGER NOT NULL DEFAULT 0,
    last_error        TEXT,
    updated_at_utc    TEXT    NOT NULL,
    UNIQUE(root_id, path_hash),
    FOREIGN KEY (root_id)           REFERENCES scan_roots(root_id),
    FOREIGN KEY (first_seen_run_id) REFERENCES scan_runs(run_id),
    FOREIGN KEY (last_seen_run_id)  REFERENCES scan_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_file_inventory_root_pathhash ON file_inventory(root_id, path_hash);
CREATE INDEX IF NOT EXISTS idx_file_inventory_last_seen     ON file_inventory(last_seen_run_id);
CREATE INDEX IF NOT EXISTS idx_file_inventory_owner         ON file_inventory(owner_name);
CREATE INDEX IF NOT EXISTS idx_file_inventory_owner_sid     ON file_inventory(owner_sid);
CREATE INDEX IF NOT EXISTS idx_file_inventory_extension     ON file_inventory(extension);
CREATE INDEX IF NOT EXISTS idx_file_inventory_section       ON file_inventory(section_name);
CREATE INDEX IF NOT EXISTS idx_file_inventory_mtime         ON file_inventory(mtime_utc);
CREATE INDEX IF NOT EXISTS idx_file_inventory_ctime         ON file_inventory(ctime_utc);
CREATE INDEX IF NOT EXISTS idx_file_inventory_size          ON file_inventory(size_bytes);
CREATE INDEX IF NOT EXISTS idx_file_inventory_deleted       ON file_inventory(is_deleted);

CREATE TABLE IF NOT EXISTS policies (
    policy_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT    NOT NULL UNIQUE,
    description         TEXT,
    enabled             INTEGER NOT NULL DEFAULT 1,
    severity            TEXT    NOT NULL CHECK(severity IN ('info', 'warning', 'critical')),
    match_mode          TEXT    NOT NULL CHECK(match_mode IN ('all', 'any')),
    scope_prefixes_json TEXT    NOT NULL DEFAULT '[]',
    created_at_utc      TEXT    NOT NULL,
    updated_at_utc      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS policy_rules (
    rule_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    policy_id      INTEGER NOT NULL,
    field_name     TEXT    NOT NULL,
    operator       TEXT    NOT NULL,
    value_json     TEXT    NOT NULL,
    case_sensitive INTEGER NOT NULL DEFAULT 0,
    negated        INTEGER NOT NULL DEFAULT 0,
    sort_order     INTEGER NOT NULL DEFAULT 0,
    created_at_utc TEXT    NOT NULL,
    updated_at_utc TEXT    NOT NULL,
    FOREIGN KEY (policy_id) REFERENCES policies(policy_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_policy_rules_policy ON policy_rules(policy_id, sort_order);

CREATE TABLE IF NOT EXISTS policy_violations (
    violation_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL,
    file_id         INTEGER NOT NULL,
    policy_id       INTEGER NOT NULL,
    severity        TEXT    NOT NULL CHECK(severity IN ('info', 'warning', 'critical')),
    reason          TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'reviewed', 'ignored', 'resolved')),
    reviewer        TEXT,
    review_note     TEXT,
    reviewed_at_utc TEXT,
    created_at_utc  TEXT    NOT NULL,
    FOREIGN KEY (run_id)    REFERENCES scan_runs(run_id),
    FOREIGN KEY (file_id)   REFERENCES file_inventory(file_id),
    FOREIGN KEY (policy_id) REFERENCES policies(policy_id)
);

CREATE INDEX IF NOT EXISTS idx_policy_violations_run    ON policy_violations(run_id);
CREATE INDEX IF NOT EXISTS idx_policy_violations_file   ON policy_violations(file_id);
CREATE INDEX IF NOT EXISTS idx_policy_violations_policy ON policy_violations(policy_id);
CREATE INDEX IF NOT EXISTS idx_policy_violations_status ON policy_violations(status);
CREATE INDEX IF NOT EXISTS idx_policy_violations_run_severity ON policy_violations(run_id, severity);
CREATE INDEX IF NOT EXISTS idx_policy_violations_run_status   ON policy_violations(run_id, status);

CREATE TABLE IF NOT EXISTS scan_errors (
    error_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id         INTEGER NOT NULL,
    root_id        INTEGER,
    path           TEXT    NOT NULL,
    operation      TEXT    NOT NULL,
    error_type     TEXT    NOT NULL,
    error_message  TEXT    NOT NULL,
    traceback_text TEXT,
    created_at_utc TEXT    NOT NULL,
    FOREIGN KEY (run_id)  REFERENCES scan_runs(run_id),
    FOREIGN KEY (root_id) REFERENCES scan_roots(root_id)
);

CREATE INDEX IF NOT EXISTS idx_scan_errors_run ON scan_errors(run_id);

CREATE TABLE IF NOT EXISTS review_actions (
    action_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    violation_id   INTEGER NOT NULL,
    action_type    TEXT    NOT NULL,
    actor          TEXT    NOT NULL,
    note           TEXT,
    created_at_utc TEXT    NOT NULL,
    FOREIGN KEY (violation_id) REFERENCES policy_violations(violation_id)
);

CREATE TABLE IF NOT EXISTS monitor_subjects (
    subject_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    label           TEXT    NOT NULL,
    watch_path      TEXT    NOT NULL UNIQUE,
    watch_type      TEXT    NOT NULL CHECK(watch_type IN ('file', 'directory')),
    recursive       INTEGER NOT NULL DEFAULT 0,
    active          INTEGER NOT NULL DEFAULT 1,
    created_at_utc  TEXT    NOT NULL,
    updated_at_utc  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS monitor_events (
    event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id      INTEGER NOT NULL,
    event_type      TEXT    NOT NULL CHECK(event_type IN ('created','modified','deleted','renamed')),
    path            TEXT    NOT NULL,
    old_path        TEXT,
    created_at_utc  TEXT    NOT NULL,
    FOREIGN KEY (subject_id) REFERENCES monitor_subjects(subject_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_monitor_events_subject
    ON monitor_events(subject_id, created_at_utc DESC);
CREATE INDEX IF NOT EXISTS idx_monitor_events_type
    ON monitor_events(event_type);

-- ── User accounts ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    user_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    username       TEXT    NOT NULL UNIQUE,
    password_hash  TEXT    NOT NULL,
    salt           TEXT    NOT NULL,
    role           TEXT    NOT NULL CHECK(role IN ('viewer', 'admin', 'secret_admin')),
    created_by     TEXT,
    created_at_utc TEXT    NOT NULL,
    active         INTEGER NOT NULL DEFAULT 1
);

-- ── Feature 1: Duplicate file detection ────────────────────────────────
CREATE TABLE IF NOT EXISTS file_hashes (
    hash_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id         INTEGER NOT NULL,
    hash_type       TEXT    NOT NULL CHECK(hash_type IN ('name_size', 'partial', 'full')),
    hash_value      TEXT    NOT NULL,
    computed_at_utc TEXT    NOT NULL,
    FOREIGN KEY (file_id) REFERENCES file_inventory(file_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_file_hashes_file_type ON file_hashes(file_id, hash_type);
CREATE INDEX IF NOT EXISTS idx_file_hashes_value ON file_hashes(hash_type, hash_value);

-- ── Feature 3: Owner accountability index ──────────────────────────────
CREATE TABLE IF NOT EXISTS owner_contact_map (
    map_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_name      TEXT    NOT NULL UNIQUE,
    display_name    TEXT,
    email           TEXT,
    department      TEXT,
    notes           TEXT,
    created_at_utc  TEXT    NOT NULL,
    updated_at_utc  TEXT    NOT NULL
);

-- ── Feature 4: Policy approval workflow ────────────────────────────────
CREATE TABLE IF NOT EXISTS policy_drafts (
    draft_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT    NOT NULL,
    description         TEXT,
    severity            TEXT    NOT NULL CHECK(severity IN ('info', 'warning', 'critical')),
    match_mode          TEXT    NOT NULL CHECK(match_mode IN ('all', 'any')),
    scope_prefixes_json TEXT    NOT NULL DEFAULT '[]',
    status              TEXT    NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
    submitted_by        TEXT    NOT NULL,
    reviewed_by         TEXT,
    review_note         TEXT,
    reviewed_at_utc     TEXT,
    created_at_utc      TEXT    NOT NULL,
    updated_at_utc      TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_policy_drafts_status ON policy_drafts(status);

CREATE TABLE IF NOT EXISTS policy_draft_rules (
    draft_rule_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id       INTEGER NOT NULL,
    field_name     TEXT    NOT NULL,
    operator       TEXT    NOT NULL,
    value_json     TEXT    NOT NULL,
    case_sensitive INTEGER NOT NULL DEFAULT 0,
    negated        INTEGER NOT NULL DEFAULT 0,
    sort_order     INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (draft_id) REFERENCES policy_drafts(draft_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_policy_draft_rules_draft ON policy_draft_rules(draft_id, sort_order);
