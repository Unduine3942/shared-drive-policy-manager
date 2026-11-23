# Shared Drive Policy Manager

A desktop application for scanning shared drives, enforcing file retention and security policies, and generating compliance reports.

Runs entirely within **ArcGIS Pro 3.3.1's `arcgispro-py3` environment** (Python 3.11). No external package installation is required.

---

## Requirements

| Requirement | Details |
|-------------|---------|
| ArcGIS Pro  | 3.3.1 (provides `arcgispro-py3`) |
| Python      | 3.11 (bundled with ArcGIS Pro) |
| OS          | Windows 10 / 11 |
| Disk        | ~50 MB for application + database |
| Network     | Read access to all target shared-drive roots |

**Optional packages** (automatically detected; features degrade gracefully if absent):

| Package        | Feature enabled                     |
|----------------|-------------------------------------|
| `win32security`| File owner / ACL resolution         |
| `openpyxl`     | Excel export (.xlsx)                |
| `pandas`       | Enhanced CSV export                 |
| `arcpy`        | ArcGIS toolbox integration          |
| `psutil`       | System resource monitoring          |

---

## Deployment

### 1. Copy the folder

Place the entire `Sharedrive_Manager` folder in an approved location accessible to the drive administrator, for example:

```
C:\Tools\SharedDrivePolicyManager\
```

No installation, no pip/conda commands, no admin rights required.

### 2. Verify the ArcGIS Pro Python interpreter

```bat
"%ProgramFiles%\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" --version
```

Expected output: `Python 3.11.x`

### 3. Launch

**Option A — double-click the batch launcher:**

```
launch.bat
```

**Option B — command line:**

```bat
"%ProgramFiles%\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" run_app.py
```

**Option C — Python module:**

```bat
"%ProgramFiles%\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" -m shared_drive_manager
```

**Option D — ArcGIS Pro toolbox:**

1. Open ArcGIS Pro.
2. In the **Catalog** pane, right-click **Toolboxes → Add Toolbox**.
3. Browse to `shared_drive_manager\arcgis_toolbox\launch_shared_drive_manager.pyt`.
4. Expand the toolbox and double-click **Launch Shared Drive Policy Manager**.
5. Click **Run** — the GUI opens as a separate process.

---

## First-Run Checklist

1. **Dashboard tab** opens automatically and shows environment checks.
   - All checks except optional packages should show green.
2. **Settings tab** — verify or override:
   - *DB File Path* (default: `%LOCALAPPDATA%\SharedDrivePolicyManager\shared_drive_manager.sqlite3`)
   - *Max Workers* (default: 4; increase for faster local drives)
   - *Max Errors* (default: 0 = unlimited; set a positive value to abort a runaway scan)
3. **Scan Setup tab** — add at least one scan root.
   - Click **Add Root…** → enter a label and a path (UNC paths like `\\server\share` are supported).
   - Click **Validate Access** to confirm connectivity before scanning.
4. **Policy Config tab** — review the eight starter templates (all disabled by default).
   - Enable and edit templates appropriate for your organization.
5. Click **Start Full Scan** on the Scan Setup tab.

---

## Usage Guide

### Scan Setup

| Control | Purpose |
|---------|---------|
| Add Root… | Add a folder or UNC path to scan. |
| Remove Root | Deactivate a root (file records are kept). |
| Validate Access | Confirm the selected root is reachable. |
| Start Full Scan | Scan all active roots; mark absent files as deleted. |
| Start Incremental Scan | Re-walk directories; update changed files only. |
| Resume Interrupted Scan… | Continue a scan that was canceled or lost during a crash. |
| Cancel Scan | Stop after the current directory batch completes. |

### Policy Configuration

Policies are organized as rule groups. Each policy has:
- A **severity** (`info`, `warning`, `critical`)
- A **match mode** (`all` rules must match, or `any` rule must match)
- Optional **scope prefixes** to limit evaluation to specific paths

Rules evaluate file fields such as `extension`, `size_bytes`, `mtime_utc`, `owner_name`, `path_length`, and more. See the full operator list in `claude.md`.

**Starter templates** (disabled by default):

| Template | Severity | What it flags |
|----------|----------|---------------|
| Stale files older than 7 years | warning | Files not modified in 7+ years |
| Potentially risky executables | critical | `.exe`, `.bat`, `.cmd`, `.ps1`, `.vbs`, `.msi` |
| Personal archive/mail files | warning | `.pst`, `.ost`, `.zip`, `.7z`, `.rar` |
| Oversized files | warning | Files > 5 GB |
| Temporary or duplicate-looking names | info | `~$*`, `* - Copy.*`, names containing "copy of" |
| Long paths | warning | Paths > 240 characters |
| Unknown owner | info | Files where owner cannot be resolved |
| Empty files | info | Zero-byte files |

### Results Browser

Filter violations by policy, severity, section, owner, extension, path fragment, size, and date range. Actions available per row:
- **Open Containing Folder** — opens Windows Explorer at the file's location
- **Copy Path** — copies the full path to the clipboard
- **Mark Reviewed / Add Note** — records a review action in the database

### Reports

Pre-built summary views:
- Violations by severity, section, owner, extension
- Stale files by section
- Largest flagged files
- Scan errors by path

Export to **CSV** (always available) or **XLSX** (requires `openpyxl`).

---

## Data Storage

All persistent data is stored under `%LOCALAPPDATA%\SharedDrivePolicyManager\`:

| Path | Contents |
|------|---------|
| `shared_drive_manager.sqlite3` | Main database (SQLite WAL mode) |
| `logs\app.log` | Rotating application log (5 MB × 5 files) |

The database path can be overridden in **Settings → DB File Path**. A restart is required after changing this path.

**Maintenance:** Use **Settings → Vacuum Database** periodically to reclaim space and update query statistics after large scans.

---

## Project Structure

```
Sharedrive_Manager/
├── run_app.py                               Entry point
├── launch.bat                               Windows batch launcher
├── claude.md                                Full project specification
├── README.md
└── shared_drive_manager/
    ├── config.py                            Central constants
    ├── logging_config.py                    Rotating file + console logging
    ├── app.py                               Application bootstrap
    ├── arcgis_toolbox/
    │   └── launch_shared_drive_manager.pyt  ArcGIS Pro toolbox launcher
    ├── core/
    │   ├── models.py                        Dataclasses (FileRecord, Policy, Rule, …)
    │   ├── path_utils.py                    Path normalisation, hashing, formatting
    │   ├── owner_resolver.py               win32security owner resolution
    │   ├── scanner.py                       File system walker
    │   ├── scan_controller.py               Scan orchestration + threading
    │   ├── policy_engine.py                 Policy evaluation engine
    │   └── reports.py                       Export / reporting functions
    ├── db/
    │   ├── connection.py                    SQLite connection factory (WAL mode)
    │   ├── schema.sql                       DDL for all tables and indexes
    │   ├── migrations.py                    Schema bootstrap + starter policy seeding
    │   └── repositories.py                 Repository classes for all entities
    ├── ui/
    │   ├── main_window.py                   ttk.Notebook shell + menu + status bar
    │   ├── dashboard_page.py                Environment checks + scan summary
    │   ├── scan_page.py                     Scan setup and progress UI
    │   ├── policy_page.py                   Policy editor UI
    │   ├── results_page.py                  Results browser with filters
    │   ├── reports_page.py                  Summary reports + export
    │   ├── settings_page.py                 Application settings form
    │   └── widgets.py                       Shared ttk widget helpers
    └── tests_manual/
        ├── smoke_test_checklist.md          Manual acceptance checklist
        └── sample_policy_config.json        Reference policy definitions
```

---

## Performance Notes

- The scanner streams file metadata directly to SQLite; it does **not** hold the directory tree in memory.
- Memory usage should remain proportional to `batch_size`, not total file count.
- For very large shares (millions of files), start with the default batch size of 1000 and increase incrementally.
- Use **Resume Interrupted Scan** to continue a scan that was canceled or interrupted by a crash without re-scanning already-completed directories.
- The **Max Errors** setting (Settings tab) allows the scan to abort automatically if a large number of access errors are encountered (useful for shares with many restricted folders).

---

## Limitations (MVP)

- No automatic file deletion, movement, or quarantine.
- No real-time monitoring.
- No multi-user or web interface.
- Owner attribution is a best-effort proxy via NTFS ownership, not original file creator.
- ACL collection is disabled by default; enable only after performance testing.
