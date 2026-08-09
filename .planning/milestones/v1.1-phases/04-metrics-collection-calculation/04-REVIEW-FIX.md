---
phase: 04
fixed_at: 2026-08-07T05:41:22Z
review_path: .planning/phases/04-metrics-collection-calculation/04-REVIEW.md
iteration: 1
findings_in_scope: 9
fixed: 9
skipped: 0
status: all_fixed
---

# Phase 04: Code Review Fix Report

**Fixed at:** 2026-08-07T05:41:22Z
**Source review:** .planning/phases/04-metrics-collection-calculation/04-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 9
- Fixed: 9
- Skipped: 0

## Fixed Issues

### CR-01: All JSON-RPC errors misclassified as authentication failures

**Files modified:** `vco_edge_export.py`
**Commit:** 56dd9e0
**Applied fix:** Differentiated auth errors from general JSON-RPC errors in `api_call()`. The `if "error" in result` block now extracts the error code and message, checks for auth-related keywords (authentication, unauthorized, token, permission), and only raises `VCOAuthError` for auth failures. Non-auth JSON-RPC errors are logged and return an empty dict, matching the existing error handling pattern.

### CR-02: `aggregate_link_samples` crashes when a link's series value is `None`

**Files modified:** `metrics.py`
**Commit:** ebc17d8
**Applied fix:** Changed `link.get("series", [])` to `link.get("series") or []` in `aggregate_link_samples()`. The `or []` pattern coerces both missing keys and explicit `None` values to empty lists, preventing `TypeError: object of type 'NoneType' has no len()` on line 127.

### CR-03: No error handling in metrics collection loop

**Files modified:** `vco_edge_export.py`
**Commit:** a4c5a53
**Applied fix:** Wrapped the per-edge per-month metrics collection body in a try/except block. `VCOAuthError` is re-raised immediately (auth failures should still terminate). All other exceptions are caught and logged via `logging.warning()` with edge name, enterprise name, and month label, allowing the loop to continue processing remaining edges.

### WR-01: Null `edge_id` from API silently creates invalid downstream API calls

**Files modified:** `vco_edge_export.py`
**Commit:** b225dfb
**Applied fix:** Added a null check for `edge.get("id")` before appending to `edge_info_list`. When `edge_id` is `None`, logs a warning with the edge name and skips metrics collection for that edge. The edge status row is still appended regardless (it doesn't require a numeric ID).

### WR-02: `.get("result", [])` does not guard against `None` result value

**Files modified:** `vco_edge_export.py`
**Commit:** 3acfcf6
**Applied fix:** Changed `response.get("result", [])` to `response.get("result") or []` in the metrics collection loop. The `or []` pattern coerces `None` results to empty lists, preventing `TypeError` when passed to `compute_edge_month_metrics`.

### WR-03: `--months` flag has no upper bound validation

**Files modified:** `vco_edge_export.py`
**Commit:** 5eeae78
**Applied fix:** Extended the `--months` validation from `args.months < 1` to `args.months < 1 or args.months > 12`. Updated the error message to indicate the valid range (1-12). This prevents users from accidentally triggering thousands of API calls with unreasonable month counts.

### WR-04: `get_target_months` silently accepts invalid `num_months` values

**Files modified:** `metrics.py`
**Commit:** 0e983f1
**Applied fix:** Added `ValueError` validation at the top of `get_target_months()`: `if num_months < 1: raise ValueError(...)`. This surfaces misconfiguration early rather than silently returning an empty list for zero or negative values.

### WR-05: Test environment variable pollution across modules

**Files modified:** `tests/conftest.py`, `tests/test_metrics_api.py`, `tests/test_cli.py`
**Commit:** 6e51101
**Applied fix:** Created `tests/conftest.py` that sets VCO_TOKEN and VCO_URL using `unittest.mock.patch.dict(os.environ, ...)` with proper cleanup in `pytest_unconfigure()`. Removed module-level `os.environ` assignments from `test_metrics_api.py` and `test_cli.py`. Since pytest loads conftest.py before test modules, the env vars are set in time for `vco_edge_export`'s module-level imports while ensuring cleanup after the test session.

### WR-06: Duplicate `urllib3` warning suppression

**Files modified:** `vco_edge_export.py`
**Commit:** 4e0cb97
**Applied fix:** Removed the redundant `requests.packages.urllib3.disable_warnings()` call on line 17. The remaining `urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)` on line 16 is sufficient and more explicit about which warning is suppressed.

---

_Fixed: 2026-08-07T05:41:22Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
