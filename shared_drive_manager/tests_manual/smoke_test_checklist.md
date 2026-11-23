# Smoke Test Checklist — Shared Drive Policy Manager

Run this checklist against a clean deployment before signing off on any release.
Use `arcgispro-py3` (ArcGIS Pro 3.3.1 / Python 3.11) for all tests.
Mark each item **PASS**, **FAIL**, or **SKIP** (with reason).

---

## 1. Launch

| # | Check | Expected | Result |
|---|-------|----------|--------|
| 1.1 | Double-click `launch.bat` | Window opens within 5 seconds | |
| 1.2 | `"%ProgramFiles%\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" run_app.py` | Same window opens | |
| 1.3 | `python -m shared_drive_manager` from repo root | Same window opens | |
| 1.4 | Window title | "Shared Drive Policy Manager" | |
| 1.5 | Six notebook tabs visible | Dashboard, Scan Setup, Policy Config, Results, Reports, Settings | |

---

## 2. Dashboard Tab

| # | Check | Expected | Result |
|---|-------|----------|--------|
| 2.1 | Python version row | Shows "3.11.x" and green indicator | |
| 2.2 | sqlite3 row | Green indicator | |
| 2.3 | tkinter row | Green indicator | |
| 2.4 | DB Writable row | Green (creates DB in `%LOCALAPPDATA%\SharedDrivePolicyManager\`) | |
| 2.5 | win32security row | Green if available; yellow/red if absent — no crash either way | |
| 2.6 | openpyxl, pandas, arcpy, psutil rows | Green or yellow — no crash | |
| 2.7 | Latest Scan section (fresh DB) | "No scans yet" message | |
| 2.8 | Inventory Totals section (fresh DB) | All zeros | |

---

## 3. Settings

| # | Check | Expected | Result |
|---|-------|----------|--------|
| 3.1 | DB File Path | Populated with default path | |
| 3.2 | Default Export Folder | Populated | |
| 3.3 | Max Workers / Batch Size / Long Path Threshold | Default values shown | |
| 3.4 | Max Errors spinbox | Shows 0 (unlimited) | |
| 3.5 | Collect owner checkbox | Checked by default | |
| 3.6 | Collect ACL checkbox | Present but disabled | |
| 3.7 | Log Level combobox | Shows INFO | |
| 3.8 | Click Save Settings | "Settings Saved" dialog appears | |
| 3.9 | Click Vacuum Database | "VACUUM and ANALYZE completed" dialog appears | |
| 3.10 | Change DB path; save; restart | App uses new path; no crash | |
| 3.11 | Change Max Errors to 5; save; reload | Shows 5 after reload | |

---

## 4. Scan Roots

Prepare a local test folder, e.g. `C:\Temp\TestShare`, with nested subfolders and files.

| # | Check | Expected | Result |
|---|-------|----------|--------|
| 4.1 | Scan Setup tab — Add Root | Dialog opens | |
| 4.2 | Add local test folder with label "Test" | Root appears in list | |
| 4.3 | Select root; click Validate Access | "Access OK" message | |
| 4.4 | Add non-existent path; Validate Access | Clear error message; no crash | |
| 4.5 | Remove Root | Root deactivated; still visible as inactive | |
| 4.6 | Re-add root | Root becomes active again | |

---

## 5. Policy Configuration

| # | Check | Expected | Result |
|---|-------|----------|--------|
| 5.1 | Open Policy Config tab | 8 starter templates listed, all disabled | |
| 5.2 | Enable "Empty files" policy | Toggle on; saved without restart | |
| 5.3 | Open "Stale files older than 7 years" | Rule: `mtime_utc older_than_days 2555` | |
| 5.4 | Edit rule value to 3650; save | Persists on reopen | |
| 5.5 | Create new policy: name "Test Policy", severity warning, rule `extension equals .log` | Appears in list | |
| 5.6 | Enter regex > 500 characters | Validation error; save blocked | |
| 5.7 | Enter invalid regex `[unclosed` | Validation error; save blocked | |
| 5.8 | Disable test policy | Persists | |
| 5.9 | Delete test policy | Removed from list | |

---

## 6. Full Scan

Prepare test folder tree containing:
- One zero-byte file
- One file named `~$temp.docx`
- One `.bat` file
- One file with `mtime` set to >7 years ago (use `PowerShell`: `(Get-Item file).LastWriteTime = "2010-01-01"`)
- One deeply nested path (> 240 characters total if feasible)
- One subfolder with permissions denied to current user (if test environment allows)

| # | Check | Expected | Result |
|---|-------|----------|--------|
| 6.1 | Click Start Full Scan | Progress bar starts; log shows activity | |
| 6.2 | GUI responsiveness during scan | Window movable; tabs switchable | |
| 6.3 | Progress counter update rate | Updates at least every 2 seconds | |
| 6.4 | Scan completes | Status: "completed"; final counters shown | |
| 6.5 | Dashboard refreshes | Files inventoried, violations, errors reflected | |
| 6.6 | Zero-byte file | "Empty files" violation in Results | |
| 6.7 | `.bat` file | "Potentially risky executables" (critical) violation | |
| 6.8 | `~$temp.docx` | "Temporary or duplicate-looking names" violation | |
| 6.9 | Stale file | "Stale files" violation (if policy enabled) | |
| 6.10 | Long path | "Long paths" violation (if policy enabled) | |
| 6.11 | Inaccessible folder | Scan error recorded; scan does not abort | |
| 6.12 | Re-run full scan immediately | No duplicate file records; `first_seen_run_id` unchanged | |

---

## 7. Cancel and Resume

| # | Check | Expected | Result |
|---|-------|----------|--------|
| 7.1 | Start scan on large folder; click Cancel before completion | Scan stops; status: "canceled" | |
| 7.2 | Click Resume Interrupted Scan… | Dialog lists the canceled run with details | |
| 7.3 | Select run; click Resume | Scan continues; no duplicate records | |
| 7.4 | Resume completes | Status: "completed" | |
| 7.5 | Force-kill app mid-scan; relaunch | App starts normally | |
| 7.6 | Open Resume dialog after crash | Prior interrupted run listed | |

---

## 8. Incremental Scan

| # | Check | Expected | Result |
|---|-------|----------|--------|
| 8.1 | Run full scan on test folder | Completes; file count N recorded | |
| 8.2 | Add one new file to test folder; run incremental scan | New file appears in inventory | |
| 8.3 | Unchanged files | Retain original `first_seen_run_id` | |
| 8.4 | Delete one file; run incremental scan | Deleted file marked `is_deleted = 1` | |

---

## 9. Max Errors Threshold

| # | Check | Expected | Result |
|---|-------|----------|--------|
| 9.1 | Set Max Errors to 1 in Settings | Saved | |
| 9.2 | Scan folder containing inaccessible subfolder | Scan stops after first error; status message mentions threshold | |
| 9.3 | Set Max Errors back to 0; scan same folder | Scan runs to completion despite errors | |

---

## 10. Results Browser

| # | Check | Expected | Result |
|---|-------|----------|--------|
| 10.1 | Open Results tab after scan | Violations listed | |
| 10.2 | Filter by severity "critical" | Only critical rows shown | |
| 10.3 | Filter by policy name | Only that policy's rows shown | |
| 10.4 | Filter by path fragment | Rows filtered correctly | |
| 10.5 | Clear all filters | All violations return | |
| 10.6 | Copy Path action | Full path on clipboard | |
| 10.7 | Open Containing Folder action | Windows Explorer opens at parent | |
| 10.8 | Mark Reviewed action | Row status changes to "reviewed" | |
| 10.9 | Add Note action | Note saved; visible on reopen | |
| 10.10 | Export current view to CSV | File created; opens in Excel | |

---

## 11. Reports

| # | Check | Expected | Result |
|---|-------|----------|--------|
| 11.1 | Open Reports tab | Summary tables load | |
| 11.2 | Violations by severity | Counts match Results Browser | |
| 11.3 | Violations by extension | Shows `.bat` and others from scan | |
| 11.4 | Largest flagged files | Top-N list loads | |
| 11.5 | Scan errors by path | Errors from inaccessible folder shown | |
| 11.6 | Export to CSV | File written to default export folder | |
| 11.7 | Export to XLSX (openpyxl available) | .xlsx opens in Excel without errors | |
| 11.8 | Export to XLSX (openpyxl absent) | Button disabled or clear "not available" message | |

---

## 12. Database Verification

Open `%LOCALAPPDATA%\SharedDrivePolicyManager\shared_drive_manager.sqlite3` with any SQLite browser.

| # | Check | Expected | Result |
|---|-------|----------|--------|
| 12.1 | All 11 tables present | `app_settings`, `scan_roots`, `section_map`, `scan_runs`, `scan_directories`, `file_inventory`, `policies`, `policy_rules`, `policy_violations`, `scan_errors`, `review_actions` | |
| 12.2 | `policies` table | 8 starter rows seeded; no duplicates after repeated launches | |
| 12.3 | `file_inventory` unique constraint | No duplicate `(root_id, path_hash)` rows | |
| 12.4 | WAL mode | `PRAGMA journal_mode` returns `wal` | |
| 12.5 | All new indexes present | `idx_policy_violations_run_severity`, `idx_policy_violations_run_status`, `idx_file_inventory_size`, `idx_file_inventory_deleted` | |

---

## 13. Log Verification

| # | Check | Expected | Result |
|---|-------|----------|--------|
| 13.1 | Log file location | `%LOCALAPPDATA%\SharedDrivePolicyManager\logs\app.log` | |
| 13.2 | Log contains startup messages | "Starting Shared Drive Policy Manager", "Boot complete", "UI ready" | |
| 13.3 | Log rotates | After >5 MB, backup files `.log.1` through `.log.5` created | |
| 13.4 | DEBUG entries absent at INFO level | No DEBUG lines in log when level is INFO | |

---

## 14. ArcGIS Pro Toolbox (requires ArcGIS Pro license)

| # | Check | Expected | Result |
|---|-------|----------|--------|
| 14.1 | Add `arcgis_toolbox\launch_shared_drive_manager.pyt` to ArcGIS Pro Catalog | Toolbox and tool appear | |
| 14.2 | Run "Launch Shared Drive Policy Manager" tool | New process launches GUI | |
| 14.3 | ArcGIS Pro UI during launch | Remains responsive; not blocked | |
| 14.4 | Close GUI | ArcGIS Pro unaffected | |

---

## 15. Edge Cases

| # | Check | Expected | Result |
|---|-------|----------|--------|
| 15.1 | Scan root with 0 files | Completes; counters show 0 | |
| 15.2 | Two scans in sequence | Second scan creates new `scan_run`; prior results preserved | |
| 15.3 | Incremental scan with no prior full scan | Handled gracefully (treated as full scan or clear error) | |
| 15.4 | UNC path root (e.g. `\\localhost\c$\Temp`) | Scans if reachable; access error if not — no crash | |
| 15.5 | Very long file names (> 255 characters) | Recorded as scan error or handled; no crash | |

---

## Sign-off

| Tester | Date | Environment | Overall Result |
|--------|------|-------------|----------------|
| | | ArcGIS Pro 3.3.1 / Python 3.11 / Windows | PASS / FAIL |

**Blocker issues (FAIL items):**

**Notes:**
