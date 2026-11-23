# Changelog — Shared Drive Policy Manager (GEOINT Sharedrive Manager)

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Provenance:** This changelog was reconstructed retroactively on
> 2026-07-29 from Claude Code session archives, file modification
> timestamps, and project documentation. Entry dates reflect when the work
> was actually performed; no changelog was kept contemporaneously.

> **Version note:** The May 2026 activity report slide "GEOINT Sharedrive Manager — Version 1.0.4 (Released APR 2026)" conflates this project with its sibling File_Refresher (GEOINT Hub Manager v2.0); neither codebase carries a 1.0.4 designation. This changelog records this project's own substantiated ladder.


## [1.0.1] - 2026-05-27 — ArcGIS packaging and documentation
### Added
- ArcGIS Pro toolbox launcher packaging (`launch_shared_drive_manager.pyt`, 2026-05-11); validated against ArcGIS Pro 3.3.1.

### Documentation
- README, Architecture, Decisions, and TODO refreshed (2026-05-27); portfolio status ~95% MVP.

## [1.0.0] - 2026-05-08 — MVP release
### Added
- SQLite schema v1 (WAL mode): scan_roots, file_inventory, policies, policy_violations, scan_runs, scan_directories, scan_errors, review_actions, owner_accountability, monitor_events. Streams 40M+ file records without in-memory growth.
- Incremental/full/resume scans with persisted directory queue.
- Duplicate detection and Owner Accountability pages; NTFS owner/SID resolution via win32security with graceful fallback.
- CSV/XLSX report export (openpyxl optional).
- Test suite: test_auth, test_path_utils, test_policy_engine, test_repositories.

### Limitations (MVP)
- No automatic deletion/quarantine; ACL collection optional and disabled by default; owner attribution via NTFS only.

## [0.9.0] - 2026-05-07 — UI expansion and authentication
### Added
- UI build-out: Dashboard, Scan Setup, Policy Config, Results Browser, Reports, Settings, Sections, and Hidden Files pages with shared theme/widgets.
- Auth/login window and user management.

## [0.8.0] - 2026-05-06 — Scanning, policy engine, monitoring
### Added
- Streaming metadata scanner with batch upsert (default 2,000 files/batch).
- Scan controller with ThreadPoolExecutor (default 4 workers, max 16).
- Policy engine with 22 rule operators (string, number, date, boolean, null/missing).
- Real-time folder monitoring (`file_monitor.py`) and Monitor page.
- 8 starter policy templates (all disabled by default): stale >7 years, risky executables, personal archives/mail, oversized >5 GB, temp/duplicate names, long paths >240 chars, unknown owner, empty files.

## [0.5.0] - 2026-05-01 — First runnable build
### Added
- Application starts end-to-end ("Build and Fix" session).

### Security
- Code review completed; security fixes applied.

## [0.1.0] - 2026-04-29 — Project scaffolding
### Added
- Project launch: architecture plan and specification (claude.md), README, and full scaffolding for `db/`, `core/`, `ui/`, and `arcgis_toolbox/` layers.
