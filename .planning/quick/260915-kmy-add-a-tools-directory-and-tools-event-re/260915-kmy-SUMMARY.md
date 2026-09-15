---
id: 260915-kmy
status: complete
completed: 2026-09-15
phase: quick
tags: [vco, json-rpc, cli, events, csv, pytest]
commits:
  - 4cdee49
  - 3b98c18
---

# Quick Task 260915-kmy: Add tools/event_report.py

**One-liner:** Standalone VCO enterprise-event export CLI (`tools/event_report.py`) using the same auth/JSON-RPC/retry conventions as `vco_edge_export.py`, with 19 mocked pytest tests.

## What Shipped

- **`tools/__init__.py`** — empty package marker enabling `from tools.event_report import …` in pytest
- **`tools/event_report.py`** — standalone CLI (≥150 lines) that fetches enterprise events via `event/getEnterpriseEvents` JSON-RPC and writes a CSV; flags: `--days` (default 7), `--vco-host`, `--vco-token`, `--output`, `--enterprise-ids`; pure helpers: `compute_interval_ms`, `write_events_csv`; auth/retry/error layer: `VCOAuthError`, `normalize_token`, `api_call` with 429 backoff — copied shape from `vco_edge_export.py`, not imported
- **`tests/test_event_report.py`** — 19 tests (CLI parsing, interval math, CSV writer, API wrappers, auth-error paths) — all mocked, no live VCO
- **`README.md`** — minimal `### tools/event_report.py` subsection added under Scripts

## Commits

| Commit | Description |
|--------|-------------|
| `4cdee49` | Add tools/event_report.py — standalone VCO enterprise event export CLI |
| `3b98c18` | Add mocked pytest coverage for event_report and brief README mention |

## Verification

```
uv run python tools/event_report.py --help    ✓  exits 0, all flags shown
uv run python tools/event_report.py --version ✓  prints "event_report.py 0.1.0"
uv run pytest tests/test_event_report.py -v   ✓  19/19 passed
uv run pytest tests/ -q                       ✓  267/267 passed (no regressions)
```

## Constraints Honored

- No changes to any existing root scripts
- No files created or modified under `doc/`
- `SKIP_95TH` and `OBFUSCATED` not referenced anywhere in new code or docs
- No output filename details added under `doc/`
- `uv run` used for all Python invocations
- Planning docs commit deferred to orchestrator
