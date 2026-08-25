---
phase: 03-decryption-tooling
plan: "01"
subsystem: decryption-tooling
tags: [decryption, standalone, cli, fernet, tdd]

dependency_graph:
  requires: []
  provides: [decrypt_metrics.py]
  affects: []

tech_stack:
  added: []
  patterns:
    - standalone script with embedded Fernet key (obfuscation-grade, by design)
    - outer-zip -> data.enc -> inner-zip -> CSVs reverse-archive pattern

key_files:
  created:
    - decrypt_metrics.py
    - tests/test_decryption.py
  modified: []

decisions:
  - "Word-boundary regex used in test_standalone_no_project_imports to avoid false-positive from 'from cryptography' matching plan's 'from crypto' grep pattern"
  - "Embedded FERNET_KEY duplicated by design (not imported from crypto.py) to meet standalone requirement DEC-01"

metrics:
  duration: "4m"
  completed: "2026-08-23"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase 03 Plan 01: Standalone Decryption Script Summary

Standalone `decrypt_metrics.py` CLI tool that recovers metric CSVs from Fernet-encrypted archives using embedded key, with 14-test comprehensive suite verifying roundtrip byte-for-byte identity (DEC-02) and zero project imports (DEC-01).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create standalone decrypt_metrics.py (TDD RED) | 686df70 | _test_decrypt_red.py (temp) |
| 1 | Create standalone decrypt_metrics.py (TDD GREEN) | 528f36e | decrypt_metrics.py |
| 2 | Comprehensive test suite | 400345f | tests/test_decryption.py |
| - | Remove temp TDD RED file | f4cc127 | _test_decrypt_red.py (deleted) |

## What Was Built

### decrypt_metrics.py (115 lines)

Fully standalone offline script for recovering CSV files from encrypted archives:
- Embeds `FERNET_KEY = b"YVrZTl2xyS7QHyqxwaP2xd5gwMUjoctoo8RKUwjNi-8="` directly (no crypto.py import)
- `decrypt_archive(zip_path, output_dir=None) -> Path` reverses the two-level archive format:
  - Outer zip -> `data.enc` (Fernet-encrypted) -> inner zip -> individual CSV files
- Raises `FileNotFoundError` for missing paths, `KeyError` if no `data.enc`, `InvalidToken` if decryption fails
- CLI block: accepts `<encrypted-zip> [output-dir]`, prints "Decrypted N files to {dir}", exits 1 on any error
- Only imports: `sys`, `io`, `zipfile`, `pathlib.Path`, `cryptography.fernet.Fernet/InvalidToken`

### tests/test_decryption.py (233 lines, 14 tests)

Three test classes covering all acceptance criteria:
- `TestDecryptArchive` (8 tests): roundtrip, byte-for-byte content identity, default/custom output dirs, error cases, dir creation, return type
- `TestDecryptionKeyIdentity` (1 test): embedded key equals `crypto.FERNET_KEY` byte-for-byte
- `TestDecryptCLI` (5 tests): CLI exit codes, file count output, standalone no-project-imports verified via word-boundary regex

## Verification Results

```
uv run pytest tests/test_decryption.py -v
14 passed in 0.46s

uv run python decrypt_metrics.py <encrypted-zip>
Decrypted 1 files to <output-dir>  (exit 0)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Imprecise grep pattern for standalone check**

- **Found during:** Task 2 test_standalone_no_project_imports
- **Issue:** Plan acceptance criteria uses `grep -c "from crypto\|import crypto\|..."` which matches `from cryptography.fernet import ...` (substring match), producing a false positive against the required `cryptography` package import.
- **Fix:** Wrote `test_standalone_no_project_imports` using Python `re.search()` with word-boundary patterns (`\bimport crypto\b`, `\bfrom crypto\b`, etc.) that correctly distinguish `from crypto import` (project module) from `from cryptography.fernet import` (external package).
- **Files modified:** tests/test_decryption.py
- **Commit:** 400345f

## Pre-existing Test Failures (Out of Scope)

The following test failures existed before this plan's changes and affect only unrelated modules. They are logged here for visibility but were not introduced by this work:

| Test | File | Failure |
|------|------|---------|
| test_default_values | tests/test_cli.py | months default: expected 1, got 3 |
| TestBytesToMbps.test_one_megabyte_in_bytes | tests/test_metrics.py | bytes_to_mbps math mismatch |
| TestComputeDailyP95s.test_single_day_288_samples | tests/test_metrics.py | tx_p95 assertion |
| TestComputeDailyP95s.test_two_days_sorted_by_date | tests/test_metrics.py | tx_p95 assertion |
| TestWriteMonthCsvs.test_csv_has_additional_columns | tests/test_output.py | missing column |
| TestWriteMonthCsvs.test_unmatched_edge_has_nan_metrics | tests/test_output.py | missing column |
| test_write_month_csvs_produces_csv_via_namespace | tests/test_output_wiring.py | missing column |

## Known Stubs

None — decrypt_metrics.py is fully functional with real decryption logic.

## TDD Gate Compliance

Task 1:
- RED commit: `686df70` `test(03-01): add failing test for decrypt_archive`
- GREEN commit: `528f36e` `feat(03-01): implement standalone decrypt_metrics.py`

Task 2:
- Test commit: `400345f` `test(03-01): add comprehensive test suite for decrypt_metrics`
- All 14 tests passed against the Task 1 implementation immediately (no implementation gaps found)

## Self-Check: PASSED
