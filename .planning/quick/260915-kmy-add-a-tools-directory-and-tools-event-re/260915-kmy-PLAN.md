---
phase: quick-260915-kmy
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tools/__init__.py
  - tools/event_report.py
  - tests/test_event_report.py
  - README.md
autonomous: true

must_haves:
  truths:
    - "User can run `uv run python tools/event_report.py --help` and see credential + time-window flags"
    - "User can run `uv run python tools/event_report.py` and it exports enterprise events to a CSV using .env credentials"
    - "`--days N` (default 7) controls the time window; `--vco-host` and `--vco-token` override .env"
    - "Invalid/expired tokens surface as `VCOAuthError` with a clear message (HTTP 401/403 or auth-keyword JSON-RPC error)"
    - "Rate-limited responses (HTTP 429) retry with backoff up to 5 attempts, matching vco_edge_export.py"
    - "`pytest tests/test_event_report.py` passes without contacting a live VCO (HTTP is mocked)"
    - "Existing root scripts (vco_edge_export.py, get_all_users.py, decrypt_metrics.py, compare_exports.py, bw_license_analysis.py) are unchanged"
  artifacts:
    - path: "tools/__init__.py"
      provides: "Marks tools/ as an importable package so pytest can `from tools.event_report import ...`"
      contains: ""
    - path: "tools/event_report.py"
      provides: "Standalone CLI that fetches enterprise events via VCO JSON-RPC and writes a CSV"
      exports: ["build_parser", "api_call", "get_enterprise_ids", "get_enterprise_events", "normalize_token", "VCOAuthError"]
      min_lines: 150
    - path: "tests/test_event_report.py"
      provides: "Pytest tests for CLI parsing and event API wrapper with mocked HTTP"
      min_lines: 60
    - path: "README.md"
      provides: "Brief mention of tools/event_report.py under Scripts section (invocation only)"
  key_links:
    - from: "tools/event_report.py"
      to: ".env (VCO_HOST, VCO_TOKEN)"
      via: "python-dotenv load_dotenv() on the script directory, matching vco_edge_export.py"
      pattern: "load_dotenv\\(.*\\.env"
    - from: "tools/event_report.py"
      to: "https://{vco_host}/portal/ (JSON-RPC 2.0)"
      via: "requests.post with Authorization=Token ..., verify=False, 429 retry-with-backoff, VCOAuthError on 401/403"
      pattern: "event/getEnterpriseEvents"
    - from: "tests/test_event_report.py"
      to: "tools.event_report.api_call"
      via: "unittest.mock.patch('tools.event_report.api_call')"
      pattern: "patch\\(['\\\"]tools\\.event_report\\.api_call"
---

<objective>
Add a `tools/` directory at the repo root and drop in `tools/event_report.py` — a small, standalone VCO CLI that exports enterprise events over JSON-RPC 2.0 and writes a CSV. Existing root scripts are not touched.

Purpose: Give analysts a dedicated event report generator that reuses the exact auth, JSON-RPC, retry, and error conventions already established in `vco_edge_export.py`, without cross-contaminating the existing export pipeline.

Output: `tools/__init__.py` (empty), `tools/event_report.py` (CLI), `tests/test_event_report.py` (mocked HTTP), and a one-line README bump. No changes under `doc/`.
</objective>

<execution_context>
Quick task — no separate execute-plan workflow file. Follow this PLAN.md directly.
Existing project conventions to mirror:
- Auth + JSON-RPC layer: `vco_edge_export.py` (`api_call`, `VCOAuthError`, `normalize_token`, 429 retries, `verify=False`)
- .env loading pattern: `_script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))` + `load_dotenv(os.path.join(_script_dir, ".env"))`
- CLI shape: argparse with `--vco-host`, `--vco-token`, `-v/--version` (see `build_parser` in `vco_edge_export.py`)
- Test shape: `tests/conftest.py` (sets `VCO_TOKEN`/`VCO_HOST` before import), `tests/test_cli.py` (argparse tests), `tests/test_metrics_api.py` (mock `api_call` with `unittest.mock.patch`)
</execution_context>

<context>
@.planning/STATE.md
@.planning/PROJECT.md
@CLAUDE.md
@vco_edge_export.py
@get_all_users.py
@USAGE.md
@README.md
@tests/conftest.py
@tests/test_cli.py
@tests/test_metrics_api.py
@pyproject.toml
@.env.example
</context>

<constraints>
- **CLAUDE.md rules:** Never reference `SKIP_95TH` or `OBFUSCATED` env vars anywhere under `doc/`. Never add output file details (names, tables, descriptions) under `doc/`. This plan does not touch `doc/` at all.
- **Do not** rename, move, refactor, or import from existing root scripts. `tools/event_report.py` is standalone — it re-implements the small `api_call`/`VCOAuthError`/`normalize_token` surface locally, just like `get_all_users.py` does, so it stays a self-contained CLI.
- **Do not** modify `.env`, `.env.example`, `USAGE.md`, or `doc/*`.
- **Dependencies:** use only what is already in `pyproject.toml` (`requests`, `python-dotenv`, `urllib3`). No new packages.
- **Prefer CSV** for output (matches `vco_edge_export.py`'s CSV convention). Do not emit an Excel workbook.
- **SSL:** `urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)` + `verify=False`, matching existing scripts.
- **No live VCO in tests** — mock `requests.post` and/or `tools.event_report.api_call` with `unittest.mock`.
</constraints>

<tasks>

<task type="auto">
  <name>Task 1: Create tools/ package and event_report.py CLI</name>
  <files>tools/__init__.py, tools/event_report.py</files>
  <action>
Create two files under a new `tools/` directory at the repo root.

**1. `tools/__init__.py`** — empty file. Purpose: make `tools` a real package so `from tools.event_report import ...` works cleanly from pytest and future tooling.

**2. `tools/event_report.py`** — standalone CLI. Structure it after `vco_edge_export.py`'s auth/API/argparse pattern (NOT `get_all_users.py`'s older VCO_URL pattern). Concretely:

Top of file:
- `__version__ = "0.1.0"`
- Imports: `argparse`, `csv`, `json`, `logging`, `os`, `sys`, `time`, `urllib3`, `requests`, `from datetime import datetime, timedelta, timezone`, `from dotenv import load_dotenv`, `from requests.structures import CaseInsensitiveDict`
- `urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)`
- Load `.env` next to the script/binary: `_script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))` then `load_dotenv(os.path.join(_script_dir, ".env"))`
- Module-level `token = os.getenv("VCO_TOKEN")`, `vco_host = os.getenv("VCO_HOST", "localhost")`, `vco_url = None`

Core primitives (copy shape from `vco_edge_export.py`, do NOT import from it):
- `class VCOAuthError(Exception): pass`
- `def normalize_token(raw_token: str) -> str` — idempotently prepend `"Token "`; raise `ValueError` on empty input. Same behavior as `vco_edge_export.normalize_token`.
- `def api_call(method, params, max_retries=5)` — JSON-RPC 2.0 POST to `vco_url` with headers `Authorization: <token>` and `Content-Type: application/json`, body `{"id": 0, "jsonrpc": "2.0", "method": method, "params": params}`, `verify=False`. Behavior:
  - 401/403 → raise `VCOAuthError` with the standard "Authentication failed (HTTP …). Check that VCO_TOKEN in .env is valid and not expired." message.
  - 429 → sleep `Retry-After` (fallback `2**attempt`), retry up to `max_retries`.
  - 5xx → exponential backoff retry up to `max_retries`.
  - JSON-RPC `"error"` in response with any of `["authentication", "unauthorized", "token", "permission"]` in the message → raise `VCOAuthError`. Other JSON-RPC errors → `logging.error(...)` and return `{}`.
  - Network/timeout exceptions → backoff retry; final failure → `logging.error(...)` and return `{}`.

API wrappers:
- `def get_enterprise_ids() -> list[dict]` — call `network/getNetworkEnterprises` with `{"networkId": 1, "with": ["edges"]}`; map results to `[{"id", "name", "logicalId"}]`. Mirror `vco_edge_export.get_enterprise_ids`.
- `def get_enterprise_events(enterprise_id: int, start_ms: int, end_ms: int, limit: int = 2048) -> dict` — call JSON-RPC method `event/getEnterpriseEvents` with params:
  ```
  {
      "enterpriseId": enterprise_id,
      "interval": {"start": start_ms, "end": end_ms},
      "limit": limit,
  }
  ```
  Return the full parsed response dict (event list is at `result["data"]` on real VCO; do not assume — just return the dict and let the writer defensively pull `result.get("data", []) or result.get("result", [])` when it's a list-shaped result).

CLI:
- `def build_parser() -> argparse.ArgumentParser` with:
  - `-v/--version` → `action="version"`, `version=f"%(prog)s {__version__}"`
  - `--vco-host` (str, default `None`, help: overrides VCO_HOST)
  - `--vco-token` (str, default `None`, help: overrides VCO_TOKEN)
  - `--days` (int, default `7`, help: "Days of event history to fetch (default: 7)")
  - `--output` (str, default `None`, help: "Output CSV path (default: vco_events_{timestamp}.csv in current directory)")
  - `--enterprise-ids` (int nargs="+", default `None`, metavar="ID") to optionally restrict enterprises
- `def compute_interval_ms(days: int, now: datetime | None = None) -> tuple[int, int]` — pure helper: returns `(start_ms, end_ms)` where `end_ms = int(now.timestamp() * 1000)` and `start_ms = end_ms - days * 86_400_000`. Default `now` to `datetime.now(tz=timezone.utc)`. Keep it pure so it's directly testable.
- `def write_events_csv(rows: list[dict], output_path: str) -> str` — pure helper. If `rows` is empty, write a CSV with a default header set (`["id", "eventTime", "event", "category", "severity", "enterpriseId", "enterpriseName", "edgeName", "message", "detail"]`). Otherwise take the union of keys (stable order: first-seen order across rows) as the header. Use `csv.DictWriter` with `extrasaction="ignore"`. Return the path.

`if __name__ == "__main__":` block:
- `logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")`
- Parse args. Resolve `token` (CLI overrides env) and `vco_host` (CLI overrides env). Fail fast with `sys.exit(1)` and the same error strings used by `vco_edge_export.py` if either is missing (`"ERROR: VCO_TOKEN not found. Set VCO_TOKEN in .env or use --vco-token."`, `"ERROR: VCO_HOST not found. Set VCO_HOST in .env or use --vco-host."`).
- `token = normalize_token(token)`; `vco_url = f"https://{vco_host}/portal/"`.
- Compute `start_ms, end_ms = compute_interval_ms(args.days)`.
- Call `get_enterprise_ids()`; if empty, print the standard "No enterprises returned" auth-hint message and `sys.exit(1)`.
- Optionally filter by `args.enterprise_ids`.
- For each enterprise: call `get_enterprise_events(ent_id, start_ms, end_ms)`. Extract `data = resp.get("result", {}).get("data") if isinstance(resp.get("result"), dict) else resp.get("result", [])` (defensive against either VCO event response shape). Attach `enterpriseId` and `enterpriseName` to each row.
- Default output path: `f"vco_events_{datetime.now(tz=timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"`. Otherwise `args.output`.
- Write CSV via `write_events_csv(...)`. Print `f"Done. Wrote {len(rows)} events to {path}"`.

Do NOT import from `vco_edge_export`, `metrics`, `output`, `crypto`, or `encoder`. This CLI must remain standalone and independently runnable, matching the style of `get_all_users.py`.
  </action>
  <verify>
Run all of the following from the repo root:

```
uv run python tools/event_report.py --help
```
→ Exits 0, help text contains `--vco-host`, `--vco-token`, `--days`, `--output`, `--enterprise-ids`.

```
uv run python tools/event_report.py --version
```
→ Prints `event_report.py 0.1.0` and exits 0.

```
python -c "from tools.event_report import build_parser, api_call, get_enterprise_events, normalize_token, VCOAuthError, compute_interval_ms, write_events_csv; print('ok')"
```
→ Prints `ok` with no import errors.

Also run:

```
python -c "from tools.event_report import compute_interval_ms; s,e = compute_interval_ms(7); assert e - s == 7*86400*1000; print(s, e)"
```
→ Prints two integers, exits 0.
  </verify>
  <done>
- `tools/__init__.py` exists (empty file, 0 bytes is fine).
- `tools/event_report.py` exists and is importable as `tools.event_report`.
- `--help`, `--version`, and a dry `compute_interval_ms(7)` invocation all succeed as shown in `<verify>`.
- No changes to any existing root scripts (`vco_edge_export.py`, `get_all_users.py`, `decrypt_metrics.py`, `compare_exports.py`, `bw_license_analysis.py`, `metrics.py`, `output.py`, `encoder.py`, `crypto.py`).
- No files created under `doc/`.
  </done>
</task>

<task type="auto">
  <name>Task 2: Add mocked pytest coverage and a minimal README bump</name>
  <files>tests/test_event_report.py, README.md</files>
  <action>
**1. Create `tests/test_event_report.py`** modeled directly on `tests/test_cli.py` and `tests/test_metrics_api.py`. `tests/conftest.py` already patches `VCO_TOKEN` and `VCO_HOST` before any test module imports, so `tools.event_report` will load cleanly with test credentials.

Include, at minimum, these test functions/classes:

- CLI parsing (mirror `tests/test_cli.py` style):
  - `test_default_values` — `parse_args([])` yields `days == 7`, `vco_host is None`, `vco_token is None`, `output is None`, `enterprise_ids is None`.
  - `test_days_custom` — `--days 30` yields `days == 30`.
  - `test_days_invalid_type` — `--days abc` raises `SystemExit`.
  - `test_vco_host_flag` — `--vco-host vco.example.com` yields `vco_host == "vco.example.com"`.
  - `test_vco_token_flag` — `--vco-token "Token abc123"` yields `vco_token == "Token abc123"`.
  - `test_output_flag` — `--output /tmp/x.csv` yields `output == "/tmp/x.csv"`.
  - `test_enterprise_ids_flag` — `--enterprise-ids 1 2 3` yields `enterprise_ids == [1, 2, 3]`.
  - `test_help_contains_flags` — `parser.format_help()` contains `--vco-host`, `--vco-token`, `--days`, `--output`.

- Pure helpers:
  - `test_compute_interval_ms_default_seven_days` — assert `end - start == 7 * 86_400_000`.
  - `test_compute_interval_ms_custom_days` — for `days=30`, assert `end - start == 30 * 86_400_000`.
  - `test_compute_interval_ms_uses_provided_now` — pass an explicit `datetime(2026, 1, 1, tzinfo=timezone.utc)`; assert exact millisecond math.
  - `test_write_events_csv_empty_rows_writes_header_only` — write to `tmp_path / "events.csv"`; assert the file has exactly one header line (no data rows) and includes at least `"id"` and `"event"` columns.
  - `test_write_events_csv_writes_union_of_keys` — pass rows `[{"a": 1, "b": 2}, {"b": 3, "c": 4}]`; assert header union includes `a`, `b`, `c` and both rows are written.

- API wrapper (mirror `tests/test_metrics_api.py` style — mock `tools.event_report.api_call`):
  - `test_get_enterprise_events_params` —
    ```
    with patch("tools.event_report.api_call") as mock_api_call:
        mock_api_call.return_value = {}
        get_enterprise_events(42, 1_000, 2_000)
        mock_api_call.assert_called_once()
        method, params = mock_api_call.call_args[0][0], mock_api_call.call_args[0][1]
        assert method == "event/getEnterpriseEvents"
        assert params["enterpriseId"] == 42
        assert params["interval"] == {"start": 1_000, "end": 2_000}
        assert params["limit"] == 2048
    ```
  - `test_get_enterprise_events_custom_limit` — passing `limit=100` results in `params["limit"] == 100`.
  - `test_get_enterprise_events_returns_api_result` — mock returns a canned dict; assert `get_enterprise_events(...)` returns it unchanged.
  - `test_get_enterprise_ids_shape` — patch `tools.event_report.api_call` to return `{"result": [{"id": 1, "name": "Ent1", "logicalId": "abc"}]}`; assert `get_enterprise_ids()` returns `[{"id": 1, "name": "Ent1", "logicalId": "abc"}]`.

- Auth error surfaces (mock `requests.post`, mirror `vco_edge_export` semantics):
  - `test_api_call_raises_vco_auth_error_on_401` — patch `tools.event_report.requests.post` to return a `MagicMock(status_code=401, headers={}, json=lambda: {})` and call `api_call("x", {})` inside `pytest.raises(VCOAuthError)`.
  - `test_api_call_returns_empty_on_generic_http_error` — patch `requests.post` to a response whose `raise_for_status()` raises `requests.exceptions.HTTPError` and whose `status_code` is `400`; assert `api_call(...) == {}` (does not raise).

Use `from unittest.mock import patch, MagicMock` and standard `pytest` idioms. No new fixtures needed — rely on the existing conftest-level env patch.

**2. Update `README.md` (minimal — one bullet only)** under the existing `## Scripts` section, after `### get_all_users.py`, add:

```
### tools/event_report.py

Exports enterprise events from a VCO via JSON-RPC `event/getEnterpriseEvents`. Reads `VCO_HOST`/`VCO_TOKEN` from `.env` (same as `vco_edge_export.py`).

```bash
# Last 7 days (default)
uv run python tools/event_report.py

# Custom window
uv run python tools/event_report.py --days 30

# Override credentials
uv run python tools/event_report.py --vco-host vco.example.com --vco-token "Token abc..."
```
```

Do NOT touch `USAGE.md`, `doc/*`, `.env.example`, or `pyproject.toml`. Do NOT add an entry to the "VCO API Methods Used" table (we're keeping the README bump minimal per the intent).
  </action>
  <verify>
From the repo root:

```
uv run pytest tests/test_event_report.py -v
```
→ All new tests pass. No live network traffic (all HTTP is mocked via `patch`).

```
uv run pytest tests/ -q
```
→ Full suite still passes (regression check: existing tests unaffected since no root modules changed).

```
grep -n "tools/event_report.py" README.md
```
→ Matches the new Scripts subsection.

```
grep -rn "SKIP_95TH\|OBFUSCATED" doc/
```
→ Returns whatever it already returned before (no new hits from our changes). We didn't touch `doc/`.
  </verify>
  <done>
- `tests/test_event_report.py` exists with at least the tests enumerated in `<action>` and all pass.
- Full `pytest tests/` suite is green (no regressions).
- `README.md` has a single new `### tools/event_report.py` subsection under `## Scripts` describing how to run the script; nothing about output filenames is added under `doc/`.
- No files added or modified under `doc/`.
- No modifications to `.env`, `.env.example`, `USAGE.md`, `pyproject.toml`, or any existing root `.py` script.
  </done>
</task>

</tasks>

<verification>
Phase-level (i.e. this quick task) is complete when:

1. `tools/` directory exists with `__init__.py` and `event_report.py`.
2. `uv run python tools/event_report.py --help` works and shows the four documented flags plus `--enterprise-ids`.
3. `uv run pytest tests/` is green end-to-end.
4. `git diff --name-only` shows only these paths modified/added:
   - `tools/__init__.py` (new)
   - `tools/event_report.py` (new)
   - `tests/test_event_report.py` (new)
   - `README.md` (modified — Scripts section only)
   - `.planning/quick/260915-kmy-.../260915-kmy-PLAN.md` (this plan file, if not already committed)
5. `grep -rn "SKIP_95TH\|OBFUSCATED" doc/` unchanged; no new file under `doc/`; no output-filename tables added under `doc/`.
6. No existing root `.py` script has any diff.
</verification>

<success_criteria>
- New standalone CLI `tools/event_report.py` fetches VCO enterprise events over JSON-RPC and writes a CSV, reusing the auth/JSON-RPC/retry/error conventions already in `vco_edge_export.py` but without importing from it.
- Default window is the last 7 days; `--days N` overrides it; `--vco-host` and `--vco-token` override `.env`.
- Pytest coverage exercises CLI parsing, pure helpers (`compute_interval_ms`, `write_events_csv`), and the JSON-RPC wrapper (`get_enterprise_events`, `get_enterprise_ids`, `api_call` auth-error path) — all with mocked HTTP, no live VCO required.
- Existing root scripts, `doc/*`, `USAGE.md`, `.env.example`, and `pyproject.toml` are untouched.
- CLAUDE.md documentation rules are honored: nothing new under `doc/` references `SKIP_95TH` or `OBFUSCATED`, and no output file details are added under `doc/`.
</success_criteria>

<output>
This is a quick task, not a milestone phase. Do NOT create a phase SUMMARY under `.planning/phases/`. When both tasks are complete, the executor can leave a short completion note in the same quick directory if desired (e.g. `.planning/quick/260915-kmy-.../260915-kmy-DONE.md`), but it is not required. Do NOT update ROADMAP.md.
</output>
