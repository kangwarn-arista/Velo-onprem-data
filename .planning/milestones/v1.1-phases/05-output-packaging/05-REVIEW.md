---
phase: 05-output-packaging
reviewed: 2026-08-08T03:57:29Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - output.py
  - tests/test_output.py
  - tests/test_output_wiring.py
  - vco_edge_export.py
findings:
  critical: 2
  warning: 3
  info: 2
  total: 7
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-08-08T03:57:29Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Four files reviewed: the new `output.py` module, two test files for it, and the updated `vco_edge_export.py`. The output module itself is small and mostly correct, but contains two data-correctness defects. The wiring test file (`test_output_wiring.py`) is structurally broken — all three argument-shape tests are tautological and test nothing about real code paths. `vco_edge_export.py` has two additional quality warnings.

---

## Critical Issues

### CR-01: `edge_info_list` has no deduplication — duplicate VCO edges cause fan-out rows in metrics CSVs

**File:** `vco_edge_export.py:347-356` (dedup present for edge_status_df) vs `vco_edge_export.py:325-331` (no dedup for edge_info_list); downstream impact at `output.py:98-100`

**Issue:** `edge_status_df` is explicitly deduplicated on duplicate `(Customer Name, Edge Name)` pairs (lines 347-356 of `vco_edge_export.py`). The parallel collection `edge_info_list` — which feeds the metrics pipeline — receives no deduplication at all. If the VCO API returns the same edge in multiple API responses (e.g., the same edge appearing under two enterprises, or the API returning duplicate entries), `edge_info_list` accumulates duplicate entries. Each duplicate triggers a separate `get_edge_link_series` call, appending a second `metrics_results` record for the same `(enterprise_name, edge_name, month_label)` triple. When `write_month_csvs` merges `merged_df` (1 row per edge) against `metrics_df` (2 rows for that edge) with `how="left"`, pandas fans out: the output CSV gains a duplicate row for that edge with no warning. This is a silent data integrity failure — the output row count inflates and per-edge values appear twice.

Reproduced:
```
Input rows: 1, Output rows after merge: 2
```

**Fix:** Add deduplication to `edge_info_list` after the collection loop (or deduplicate `metrics_results` before passing to `write_month_csvs`):

```python
# After the enterprise loop, before the metrics pipeline
seen_edges = set()
deduped_edge_info_list = []
for ei in edge_info_list:
    key = (ei["enterprise_id"], ei["edge_id"])
    if key not in seen_edges:
        seen_edges.add(key)
        deduped_edge_info_list.append(ei)
    else:
        logging.warning(
            "Duplicate edge id=%s name='%s' — skipping duplicate metrics collection",
            ei["edge_id"], ei["edge_name"],
        )
edge_info_list = deduped_edge_info_list
```

Alternatively, deduplicate `metrics_df` inside `write_month_csvs` before the merge:

```python
metrics_df = (
    pd.DataFrame(month_metrics)
    .rename(columns={"enterprise_name": "Customer Name", "edge_name": "Edge Name"})
    [["Customer Name", "Edge Name", "monthly_tx_95th_mbps",
      "monthly_rx_95th_mbps", "monthly_total_95th_mbps"]]
    .drop_duplicates(subset=["Customer Name", "Edge Name"])  # guard against fan-out
)
```

---

### CR-02: `extract_vco_name` returns `None` for scheme-less URLs, violating its `str` return annotation

**File:** `output.py:32`

**Issue:** `urllib.parse.urlparse(url).hostname` returns `None` — not a string — whenever the URL has no scheme (e.g., `"vco.example.com"`, `"vco.example.com/portal/"`, or `""`). The function is annotated `-> str` and the docstring says it returns a hostname string. Callers receive `None` silently; f-string interpolation then produces filenames like `"None.07-2026.csv"` and zip archives named `"None_metrics_20260101_120000.zip"`. No test covers this case. The practical trigger path is `vco_url` holding a value without `https://` (a common misconfiguration in `.env` files).

Verified:
```python
>>> urlparse("vco.example.com").hostname
None  # type NoneType
>>> urlparse("").hostname
None
```

**Fix:** Add an explicit guard and raise `ValueError` so callers know immediately:

```python
def extract_vco_name(vco_url: str) -> str:
    parsed = urlparse(vco_url)
    if not parsed.hostname:
        raise ValueError(
            f"Cannot extract hostname from VCO URL {vco_url!r}. "
            "Ensure VCO_URL includes a scheme (e.g. 'https://vco.example.com/portal/')."
        )
    return parsed.hostname
```

Also add a test in `test_output.py`:

```python
def test_scheme_less_url_raises():
    """extract_vco_name raises ValueError for a URL without a scheme."""
    import pytest
    with pytest.raises(ValueError, match="scheme"):
        extract_vco_name("vco.example.com/portal/")
```

---

## Warnings

### WR-01: All three argument-shape tests in `test_output_wiring.py` are tautological — they test nothing about real code

**File:** `tests/test_output_wiring.py:33-72`

**Issue:** `test_extract_vco_name_called_with_vco_url`, `test_write_month_csvs_receives_correct_args`, and `test_create_zip_archive_called_with_zip_extension` all follow the same broken pattern: they patch the function in the `vco_edge_export` namespace, then **manually call the mock themselves**, then assert the mock was called. No code from `vco_edge_export.py` is ever invoked. A complete removal of the `extract_vco_name` / `write_month_csvs` / `create_zip_archive` calls from `vco_edge_export.py` would not break any of these tests. They test Python's mock library, not the wiring they claim to cover.

Example of the broken pattern:
```python
def test_extract_vco_name_called_with_vco_url():
    with patch("vco_edge_export.extract_vco_name") as mock_fn:
        mock_fn.return_value = "vco.test.com"
        mock_fn(vco_edge_export.vco_url)          # <-- test itself calls the mock
        mock_fn.assert_called_with(vco_edge_export.vco_url)  # trivially true
```

**Fix:** Replace these tests with integration-style tests that actually invoke the `__main__` pipeline (or the relevant output-packaging code block) under controlled conditions, using `unittest.mock.patch` on `get_edge_link_series` and `get_enterprise_ids` to prevent real API calls:

```python
def test_output_pipeline_uses_extract_vco_name(tmp_path, monkeypatch):
    """The --collect_95th path calls extract_vco_name with vco_url."""
    # Drive the actual code path instead of calling the mock manually
    with patch("vco_edge_export.extract_vco_name", return_value="vco.test.com") as mock_fn, \
         patch("vco_edge_export.write_month_csvs", return_value=[]), \
         patch("vco_edge_export.create_zip_archive", return_value="out.zip"):
        # invoke the output-packaging block with known inputs ...
        mock_fn.assert_called_once_with(vco_edge_export.vco_url)
```

---

### WR-02: `create_zip_archive` silently adds directory entries when `source_dir` contains subdirectories

**File:** `output.py:131-132`

**Issue:** `Path(source_dir).iterdir()` returns both files and directories. `zf.write(file, arcname=file.name)` called on a directory path adds a directory entry to the zip (no exception is raised), but the entry contains no file data. Downstream consumers that unzip and expect only CSV files will receive an unexpected empty directory entry. Additionally, if the `zip_path` were ever located inside `source_dir` (which does not occur in current usage but could in a refactor), the zip file would include itself during creation, producing a corrupt or bloated archive.

**Fix:** Filter to files only:

```python
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    for file in Path(source_dir).iterdir():
        if file.is_file():
            zf.write(file, arcname=file.name)
```

---

### WR-03: `api_call()` uses `print()` for errors instead of `logging`

**File:** `vco_edge_export.py:62, 84, 92, 95, 98`

**Issue:** `__main__` configures `logging.basicConfig(level=logging.INFO)` at line 227, but `api_call()` sends all error and rate-limit output through `print()`. This bypasses log-level control — callers cannot suppress these messages by adjusting the log level, and they are not captured by any log handler. New functions in this codebase (`get_edge_link_series`, `compute_edge_month_metrics` callers) correctly use `logging.warning()`. `api_call()` is inconsistent with the established pattern.

**Fix:** Replace `print()` calls inside `api_call()` with `logging` equivalents:

```python
# line 62 — rate limit
logging.warning("Rate limited (429) on %s, retrying in %ds (attempt %d/%d)",
                 method, retry_after, attempt + 1, max_retries)

# line 84 — JSON-RPC non-auth error
logging.error("API Error on '%s': %s", method, error_msg)

# line 92, 95 — HTTP / generic error
logging.error("API Error: %s", e)

# line 98 — max retries
logging.error("API Error: max retries exceeded for %s", method)
```

---

## Info

### IN-01: `test_output.py` has no coverage for the `None`-return path of `extract_vco_name`

**File:** `tests/test_output.py:18-45`

**Issue:** All five `TestExtractVcoName` tests use well-formed `https://` URLs. No test exercises a scheme-less URL (`"vco.example.com"`), an empty string, or any input that causes `urlparse().hostname` to return `None`. This gap allowed CR-02 to go undetected.

**Fix:** Add at least one negative test:

```python
def test_scheme_less_url_raises_value_error(self):
    """extract_vco_name raises ValueError for a URL missing the https:// scheme."""
    with pytest.raises(ValueError):
        extract_vco_name("vco.example.com/portal/")
```

---

### IN-02: `import os` is out of PEP 8 import order in `vco_edge_export.py`

**File:** `vco_edge_export.py:15`

**Issue:** `import os` appears at line 15, after third-party imports (`urllib3`, `requests`, `pandas`, `dotenv`, `requests.structures`). PEP 8 requires standard library imports before third-party imports. All other standard library imports (`argparse`, `io`, `json`, `logging`, `shutil`, `tempfile`, `time`, `datetime`) appear on lines 1-8.

**Fix:** Move `import os` to line 8 or earlier, grouped with the other standard library imports:

```python
import argparse
import io
import json
import logging
import os           # move here
import shutil
import tempfile
import time
from datetime import datetime
```

---

_Reviewed: 2026-08-08T03:57:29Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
