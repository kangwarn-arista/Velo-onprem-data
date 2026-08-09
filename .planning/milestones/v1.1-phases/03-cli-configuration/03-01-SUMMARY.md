---
phase: 03-cli-configuration
plan: "01"
subsystem: vco_edge_export
tags: [cli, argparse, tdd, pytest]
dependency_graph:
  requires: []
  provides: [build_parser, CLI-arg-parsing]
  affects: [vco_edge_export.py, tests/test_cli.py]
tech_stack:
  added: [argparse (stdlib), logging (stdlib), pytest>=8.0]
  patterns: [argparse ArgumentParser, TDD red-green cycle]
key_files:
  created:
    - tests/__init__.py
    - tests/test_cli.py
  modified:
    - vco_edge_export.py
    - pyproject.toml
    - uv.lock
decisions:
  - "Added import argparse and import logging to stdlib imports block"
  - "build_parser() placed after normalize_token() and before __main__ block for logical grouping"
  - "args = build_parser().parse_args() is the very first line in __main__ so flags are available before env validation"
  - "months validation (>= 1) placed after token normalization, before API calls"
  - "logging.info/error used for collection mode and months validation (consistent with CLAUDE.md guidance)"
metrics:
  duration: "~4 minutes"
  completed_date: "2026-08-05"
  tasks_completed: 2
  files_modified: 5
requirements_validated: [CLI-01, CLI-02, CLI-03, CLI-04]
---

# Phase 03 Plan 01: CLI Argument Parsing Summary

**One-liner:** argparse CLI integration with `--collect_95th` and `--months` flags via `build_parser()`, backed by 6 pytest tests covering all flag combinations.

## What Was Built

Added argparse-based CLI argument parsing to `vco_edge_export.py`. Users can now pass:
- `--collect_95th` to enable 95th percentile bandwidth metrics collection (future phases will act on this)
- `--months N` to set how many complete months to collect (default 1, validated >= 1)

No flags = identical behavior to v1.0 (env validation, enterprise fetch, license CSV, merge, CSV write).

## Task Completion

| Task | Name | Commits | Status |
|------|------|---------|--------|
| 1 | Add build_parser function and argparse integration | `3c1e394` (RED), `8515b2f` (GREEN) | Done |
| 2 | Create CLI parser tests | `2e568bd` | Done |

## TDD Gate Compliance

| Gate | Commit | Type |
|------|--------|------|
| RED | `3c1e394` | test(03-01): add failing test for build_parser |
| GREEN | `8515b2f` | feat(03-01): add build_parser and argparse integration |
| REFACTOR | n/a | Not required — implementation is clean |

RED phase confirmed: `from vco_edge_export import build_parser` raised `ImportError` before GREEN implementation.

## Changes Made

### vco_edge_export.py

- Added `import argparse` and `import logging` in stdlib imports block (alongside `io`, `json`, `time`)
- Added `build_parser() -> argparse.ArgumentParser` function with Google-style docstring
  - `--collect_95th`: action="store_true", default=False
  - `--months`: type=int, default=1
- In `__main__`: `args = build_parser().parse_args()` as first line
- After token normalization: validates `args.months >= 1` with `logging.error()` and `exit(1)`
- Logs collection mode via `logging.info()` (enabled/disabled with month count)
- All existing pipeline logic (env validation, enterprise fetch, license CSV, merge, CSV output) unchanged

### tests/test_cli.py (created)

Six pytest tests using `build_parser()` in isolation:
- `test_default_values`: parse_args([]) -> collect_95th=False, months=1
- `test_collect_95th_flag`: --collect_95th -> collect_95th=True
- `test_months_custom`: --months 3 -> months=3
- `test_combined_flags`: --collect_95th --months 6 -> both set correctly
- `test_months_invalid_type`: --months abc raises SystemExit
- `test_help_contains_flags`: format_help() contains --collect_95th and --months

Sets `VCO_TOKEN` and `VCO_URL` via `os.environ.setdefault()` before import to isolate tests from `.env`.

### pyproject.toml

Added `pytest>=8.0` to `[dependency-groups] dev` via `uv add --dev "pytest>=8.0"`.

## Deviations from Plan

None — plan executed exactly as written. All acceptance criteria met.

## Threat Model Compliance

| Threat ID | Mitigation | Status |
|-----------|------------|--------|
| T-03-01 (Tampering: --months) | argparse type=int rejects non-integer input; __main__ validates months >= 1 | Implemented |
| T-03-02 (DoS: large --months) | Accepted — large N is a legitimate user choice | No action needed |
| T-03-SC (pytest install) | pytest is well-established; installed via uv add | Verified safe |

## Known Stubs

None. The `args.collect_95th` and `args.months` values are parsed and logged correctly. Downstream phases (04+) will wire these flags to the metrics collection pipeline — this is intentional phased delivery, not a stub.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check: PASSED

Files created/modified exist at expected paths:
- FOUND: vco_edge_export.py (modified)
- FOUND: tests/__init__.py (created)
- FOUND: tests/test_cli.py (created)
- FOUND: pyproject.toml (modified)

Commits exist:
- FOUND: 3c1e394 (RED test)
- FOUND: 8515b2f (GREEN feat)
- FOUND: 2e568bd (full test suite)

Verification commands passed:
- `uv run python vco_edge_export.py --help` exits 0, shows --collect_95th and --months
- `uv run pytest tests/test_cli.py -v` exits 0, 6 passed
