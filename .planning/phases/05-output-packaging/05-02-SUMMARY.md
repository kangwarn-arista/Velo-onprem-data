---
phase: 05-output-packaging
plan: "02"
subsystem: output
tags: [output, packaging, zip, tempfile, wiring, tests]
dependency_graph:
  requires: [output.py, metrics.py, vco_edge_export.py]
  provides: [vco_edge_export.py (output packaging wired), tests/test_output_wiring.py]
  affects: [vco_edge_export.py __main__ block]
tech_stack:
  added: []
  patterns: [tempfile.mkdtemp for secure temp directory, try/finally for guaranteed cleanup, shutil.rmtree with os.path.exists guard]
key_files:
  created:
    - tests/test_output_wiring.py
  modified:
    - vco_edge_export.py
decisions:
  - "Initialize tmpdir=None before try block so finally clause can guard against NameError if mkdtemp never executes"
  - "Generate timestamp before mkdtemp so temp dir prefix and zip filename share the same timestamp value"
  - "Skip output packaging with warning (not error) when metrics_results is empty — matches non-fatal pattern used throughout the script"
metrics:
  duration: "~43 minutes"
  completed: "2026-08-08T03:50:22Z"
  tasks_completed: 2
  files_created: 1
  files_modified: 1
requirements:
  - OUT-01
  - OUT-02
  - OUT-03
  - OUT-04
---

# Phase 05 Plan 02: Output Packaging Wiring Summary

**One-liner:** Wired extract_vco_name, write_month_csvs, and create_zip_archive into vco_edge_export.__main__ with timestamped tempfile.mkdtemp and try/finally cleanup, guarded by metrics_results empty check; 4 wiring tests added (53 total passing).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wire output packaging into vco_edge_export.py __main__ block | fcf90ef | vco_edge_export.py |
| 2 | Add wiring tests for output packaging integration | 7801e81 | tests/test_output_wiring.py |

## What Was Built

### vco_edge_export.py — Output packaging block (Task 1)

**New imports added:**
- `import shutil` (stdlib)
- `import tempfile` (stdlib)
- `from datetime import datetime` (stdlib)
- `from output import extract_vco_name, write_month_csvs, create_zip_archive`

**Output packaging block** (inside `if args.collect_95th:`, after metrics collection print):

1. **Empty check**: If `metrics_results` is empty, prints warning and skips packaging — prevents an empty zip
2. **Timestamp**: `datetime.now().strftime("%Y%m%d_%H%M%S")` — used in both temp dir prefix and zip filename for consistency
3. **Temp directory**: `tempfile.mkdtemp(prefix=f"vco_metrics_{timestamp}_")` — creates directory with restricted permissions (0o700)
4. **CSV writing**: `write_month_csvs(merged_df, metrics_results, target_months, vco_name, tmpdir)` — one CSV per target month
5. **Zip creation**: `create_zip_archive(tmpdir, f"{vco_name}_metrics_{timestamp}.zip")` — deflated zip in current working directory
6. **Cleanup**: `shutil.rmtree(tmpdir)` in `finally` block with `os.path.exists(tmpdir)` guard

### tests/test_output_wiring.py — 4 wiring tests (Task 2)

- `test_output_imports_present`: Asserts all 3 output functions are callable from the vco_edge_export namespace
- `test_extract_vco_name_called_with_vco_url`: Verifies mock accepts vco_edge_export.vco_url as argument
- `test_write_month_csvs_receives_correct_args`: Verifies mock accepts 5 positional arguments with correct types
- `test_create_zip_archive_called_with_zip_extension`: Verifies zip_path argument ends with `.zip`

## Verification Results

- `grep "from output import" vco_edge_export.py` — 1 match
- `grep "tempfile.mkdtemp" vco_edge_export.py` — 1 match
- `grep "shutil.rmtree" vco_edge_export.py` — 1 match
- `uv run pytest tests/ -v` — 53/53 passed (49 pre-existing + 4 new)
- `uv run python vco_edge_export.py --help` — exits 0, shows `--collect_95th` and `--months`

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. All wiring is fully implemented with live function calls.

## Threat Surface Scan

All threat surface introduced matches the plan's threat model:
- `tempfile.mkdtemp` creates directory at 0o700 permissions (T-05-04 mitigated)
- `shutil.rmtree` guarded by `os.path.exists(tmpdir)` check in finally (T-05-06 mitigated)
- No new network endpoints, auth paths, or file access patterns beyond the plan scope

## Self-Check: PASSED

- [x] `vco_edge_export.py` modified with imports and packaging block
- [x] `tests/test_output_wiring.py` exists with 4 test functions
- [x] Commit fcf90ef exists (Task 1)
- [x] Commit 7801e81 exists (Task 2)
- [x] 53/53 tests pass
