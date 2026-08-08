---
phase: 05-output-packaging
plan: "01"
subsystem: output
tags: [csv, zip, tdd, pandas, output]
dependency_graph:
  requires: [metrics.py, pandas]
  provides: [output.py]
  affects: [vco_edge_export.py (wired in 05-02)]
tech_stack:
  added: []
  patterns: [urllib.parse.urlparse for URL parsing, pathlib.Path.iterdir for zip packaging, pandas left merge for metrics enrichment]
key_files:
  created:
    - output.py
    - tests/test_output.py
  modified: []
decisions:
  - "Used urllib.parse.urlparse.hostname to strip port/protocol/path — handles all URL variants uniformly"
  - "Used pandas left merge (merged_df with metrics_df) so edges missing metrics receive NaN automatically without explicit null-setting"
  - "UTF-8 BOM encoding (utf-8-sig) for CSV output to match existing vco_edge_export convention"
metrics:
  duration: "~5 minutes"
  completed: "2026-08-08T02:31:57Z"
  tasks_completed: 2
  files_created: 2
  files_modified: 0
requirements:
  - OUT-01
  - OUT-02
  - OUT-04
---

# Phase 05 Plan 01: Output Module (CSV + Zip) Summary

**One-liner:** Pure output module with extract_vco_name (urlparse hostname), write_month_csvs (per-month CSV with NaN for unmatched edges), and create_zip_archive (deflated zip with flat filenames), covered by 13 TDD tests.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write failing tests for output module (RED) | ba47a5a | tests/test_output.py |
| 2 | Implement output module to pass all tests (GREEN) | 406c8a1 | output.py |

## What Was Built

### output.py — 3 exported functions

**`extract_vco_name(vco_url: str) -> str`**
Uses `urllib.parse.urlparse(url).hostname` to extract only the network location hostname. Automatically handles port stripping, protocol removal, and path removal. Works for all URL patterns tested.

**`write_month_csvs(merged_df, metrics_results, target_months, vco_name, output_dir) -> list[str]`**
For each month in `target_months`:
1. Copies `merged_df` and adds `Month-Year` column
2. Filters `metrics_results` to the current month, builds a metrics DataFrame, renames keys to match join columns
3. Left merges on `["Customer Name", "Edge Name"]` — unmatched edges get NaN automatically
4. Writes `{vco_name}.{MM-YYYY}.csv` with UTF-8 BOM encoding
5. Returns list of all written paths

**`create_zip_archive(source_dir: str, zip_path: str) -> str`**
Uses `zipfile.ZipFile` with `ZIP_DEFLATED` compression. Iterates `Path(source_dir).iterdir()` and adds each file with `arcname=file.name` (no path info in the zip). Returns `zip_path`.

### tests/test_output.py — 13 tests across 3 classes

- `TestExtractVcoName` (5 tests): standard URL, no trailing slash, subdomain with hyphens, URL with port, bare URL
- `TestWriteMonthCsvs` (5 tests): single month file creation, additional columns present, Month-Year populated for all rows, unmatched edge has NaN p95 columns, two months creates two files
- `TestCreateZipArchive` (3 tests): file existence, flat filenames in zip, return value

## TDD Gate Compliance

RED gate (test commit): ba47a5a — `test(05-01): add failing tests for output module`
GREEN gate (feat commit): 406c8a1 — `feat(05-01): implement output module with CSV and zip functions`

Both gates satisfied. Tests failed with `ModuleNotFoundError` at RED, all 13 passed at GREEN.

## Verification Results

- Full test suite: 49/49 passed (36 pre-existing + 13 new)
- `from output import extract_vco_name, write_month_csvs, create_zip_archive` — OK
- No new third-party dependencies added
- `grep -c "import requests|import openpyxl|from requests" output.py` — 0

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns outside the plan's threat model.
- `extract_vco_name` uses `urlparse.hostname` (no path traversal via hostname — T-05-01 mitigated)
- `create_zip_archive` uses `Path.iterdir()` on the provided `source_dir` only (no arbitrary file inclusion — T-05-03 mitigated)

## Self-Check: PASSED

- [x] `output.py` exists at repo root
- [x] `tests/test_output.py` exists with 13 test functions
- [x] Commit ba47a5a exists (RED gate)
- [x] Commit 406c8a1 exists (GREEN gate)
- [x] 49/49 tests pass
