---
phase: 02-output-encryption
reviewed: 2026-08-22T19:45:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - crypto.py
  - output.py
  - pyproject.toml
  - tests/test_encryption.py
  - tests/test_pipeline_encryption.py
  - vco_edge_export.py
findings:
  critical: 1
  warning: 2
  info: 1
  total: 4
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-08-22T19:45:00Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Phase 2 adds obfuscation-grade Fernet encryption to the CSV output pipeline. The core `crypto.py` module, the `create_encrypted_archive` function in `output.py`, and the `OBFUSCATED` env-var branching logic are implemented correctly. The deferred import of `encrypt_blob` inside `create_encrypted_archive` properly decouples the `cryptography` dependency from non-encryption consumers of `output.py`. Test coverage for the happy path is thorough.

However, the `package_and_cleanup` function contains a data-loss defect: its `try/finally` structure unconditionally deletes the source CSV directory even when archive creation fails. Since the CSVs represent potentially hours of API collection, this is a critical finding.

## Critical Issues

### CR-01: `package_and_cleanup` destroys source CSVs on archive-creation failure (data loss)

**File:** `vco_edge_export.py:271-286`
**Issue:** The function wraps archive creation in `try/finally` with `shutil.rmtree(output_dir)` in the `finally` block. Python's `finally` executes unconditionally -- whether the `try` body succeeds or raises. If `create_encrypted_archive` or `create_zip_archive` fails (disk full, encryption error, permission denied on `zip_path`), the source CSV directory is still deleted, then the original exception propagates. The archive was never written, and the source CSVs are gone. The data -- which may represent hours of API collection across hundreds of edges -- cannot be recovered without re-running the full export pipeline.

Concrete failure scenario: user's disk is nearly full. `create_encrypted_archive` writes the inner zip to a BytesIO buffer (in memory, succeeds), calls `encrypt_blob` (succeeds), then fails writing the outer zip to disk (`OSError: No space left on device`). The `finally` block runs `shutil.rmtree`, permanently deleting the only copy of the CSV data.

**Fix:** Remove the `finally` clause. Clean up only after successful archive creation so that a failure preserves the source data for manual recovery or retry:
```python
def package_and_cleanup(output_dir: str, zip_filename: str, metadata: dict) -> str:
    """Create a zip archive from output_dir and remove the source directory on success."""
    if os.getenv("OBFUSCATED") == "0":
        result = create_zip_archive(output_dir, zip_filename, metadata=metadata)
    else:
        result = create_encrypted_archive(output_dir, zip_filename, metadata=metadata)
    # Only clean up after successful archive creation
    try:
        shutil.rmtree(output_dir)
    except OSError as exc:
        logging.warning(
            "Failed to remove temp directory %s: %s",
            output_dir,
            exc,
        )
    return result
```

## Warnings

### WR-01: `package_and_cleanup` has no docstring

**File:** `vco_edge_export.py:271`
**Issue:** This public function has no docstring despite being the central packaging entry point that is imported and tested by `tests/test_pipeline_encryption.py`. Its contract -- particularly the cleanup semantics (when source data is preserved vs. deleted) and the `OBFUSCATED` env-var behavior -- is non-obvious and must be documented. Every other public function in the file (`api_call`, `normalize_token`, `build_parser`, etc.) has a docstring.

**Fix:** Add a docstring covering purpose, parameters, return value, env-var behavior, and cleanup guarantee:
```python
def package_and_cleanup(output_dir: str, zip_filename: str, metadata: dict) -> str:
    """Archive CSV files from output_dir into a zip and remove the source directory.

    When the ``OBFUSCATED`` environment variable is set to ``"0"``, creates a
    plain zip archive.  Otherwise (default), creates an encrypted archive
    with Fernet-encrypted ``data.enc`` payload.

    The source ``output_dir`` is removed after successful archive creation.
    If archive creation fails, the source directory is preserved so that
    data can be recovered without re-collecting from the API.

    Args:
        output_dir: Path to the directory containing CSV files to archive.
        zip_filename: Destination path for the output zip file.
        metadata: Dict written as ``_metadata.json`` inside the archive.

    Returns:
        The ``zip_filename`` string that was passed in.
    """
```

### WR-02: Unused `import pytest` in test_pipeline_encryption.py

**File:** `tests/test_pipeline_encryption.py:10`
**Issue:** `pytest` is imported but never referenced anywhere in the file. The `tmp_path` fixture is injected by pytest automatically and does not require an explicit `import pytest`. Unused imports add noise and may confuse linters or readers into thinking pytest-specific APIs (e.g., `pytest.raises`, `pytest.mark`) are used.

**Fix:** Remove line 10:
```python
# Delete this line:
import pytest
```

## Info

### IN-01: `package_and_cleanup` type hint for `metadata` is stricter than downstream functions

**File:** `vco_edge_export.py:271`
**Issue:** The `metadata` parameter is typed as `dict`, but both `create_zip_archive` and `create_encrypted_archive` accept `dict | None`. If a caller passes `None`, the code works correctly at runtime (the archive functions handle `None`), but static type checkers will not flag the inconsistency since `None` is excluded by the annotation. This mismatch makes the API contract ambiguous.

**Fix:** Align the type hint with the downstream functions:
```python
def package_and_cleanup(output_dir: str, zip_filename: str, metadata: dict | None = None) -> str:
```

---

_Reviewed: 2026-08-22T19:45:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
