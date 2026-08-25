---
phase: 03-decryption-tooling
type: code-review
depth: standard
status: findings
files_reviewed: 2
files_reviewed_list:
  - decrypt_metrics.py
  - tests/test_decryption.py
finding_count: 11
critical: 0
warning: 6
info: 5
reviewed_at: 2026-08-22
---

# Phase 03: Code Review Report

**Reviewed:** 2026-08-22
**Depth:** standard
**Files Reviewed:** 2 (`decrypt_metrics.py`, `tests/test_decryption.py`)
**Status:** issues_found

## Summary

`decrypt_metrics.py` is a short, focused script with a clean structure. The core
decryption logic is correct, the docstring contract accurately reflects the
implementation, and the key-identity test is a good guard against drift between
the two key copies. No correctness-breaking or data-loss bugs were found.

Cross-referencing `output.py` confirms the archive format assumption (outer zip
containing `data.enc` + optional `_metadata.json`) is accurate.

The zip-slip concern with `extractall` (see WR-04) is mitigated at runtime
because the project pins Python 3.13, which includes path-traversal hardening in
`zipfile`. However, the script is documented as "standalone" and carries no Python
version annotation of its own, making that mitigation implicit rather than
guaranteed.

The main weaknesses are (1) incomplete exception handling in the CLI that produces
raw tracebacks for predictable error conditions, (2) a return-value contract that
is inconsistent between the two branches of `output_dir` handling, and (3)
meaningful gaps in test coverage of error paths.

---

## Warnings

### WR-01: `BadZipFile` not caught in CLI — produces raw traceback

**File:** `decrypt_metrics.py:68` (raised inside `decrypt_archive`), `decrypt_metrics.py:98-112` (CLI handler)
**Issue:** When the caller passes a file that exists on disk but is not a valid zip
(e.g. a plain CSV, a PDF, or a truncated download), `zipfile.ZipFile(resolved, "r")`
raises `zipfile.BadZipFile`. The CLI `try/except` block catches only
`FileNotFoundError`, `KeyError`, and `InvalidToken`; `BadZipFile` escapes to the
top level and prints a raw Python traceback instead of a user-readable message.
The same unhandled traceback occurs if the outer zip is structurally valid but the
`data.enc` member is itself a malformed zip after decryption.

**Fix:**
```python
# In decrypt_archive, document the additional raise:
# Raises:
#     zipfile.BadZipFile: If zip_path or the inner encrypted payload is not a valid zip.

# In __main__:
import zipfile as _zipfile   # add at top of file

try:
    out_dir = decrypt_archive(zip_arg, out_arg)
except FileNotFoundError as exc:
    print(f"Error: {exc}", file=sys.stderr)
    sys.exit(1)
except KeyError as exc:
    print(f"Error: {exc}", file=sys.stderr)
    sys.exit(1)
except _zipfile.BadZipFile:
    print(
        "Error: the file is not a valid zip archive or the archive is corrupt.",
        file=sys.stderr,
    )
    sys.exit(1)
except InvalidToken:
    print(
        "Error: decryption failed — the archive may be corrupt or "
        "was not produced by this tool.",
        file=sys.stderr,
    )
    sys.exit(1)
```

---

### WR-02: `OSError` not caught in CLI — directory creation failure is unhandled

**File:** `decrypt_metrics.py:78`, `decrypt_metrics.py:98-112`
**Issue:** `out_path.mkdir(parents=True, exist_ok=True)` raises `OSError` (or its
subclass `PermissionError`) when the caller lacks write permission to create the
output directory. This exception is not caught in the CLI handler and surfaces as a
raw traceback, inconsistent with how the other expected failure modes are presented.

**Fix:** Add an `OSError` handler alongside the existing ones:
```python
except OSError as exc:
    print(f"Error: cannot create output directory — {exc}", file=sys.stderr)
    sys.exit(1)
```

---

### WR-03: Return value is not always absolute — inconsistent contract between branches

**File:** `decrypt_metrics.py:62-66`
**Issue:** When `output_dir` is `None`, `out_path` is derived from `resolved.parent`
(always absolute). When `output_dir` is provided, `out_path = Path(output_dir)`,
which is relative if a relative string is passed. The function therefore returns a
relative `Path` for one calling convention and an absolute `Path` for the other.
Callers that log or compare the returned path can silently get wrong results.

The existing `test_custom_output_dir` test does not catch this because `tmp_path`
is always absolute, so `Path(str(tmp_path / "custom"))` is still absolute.

**Fix:** Resolve `output_dir` to an absolute path:
```python
else:
    out_path = Path(output_dir).resolve()
```

---

### WR-04: `extractall` path-traversal protection is implicit, not documented

**File:** `decrypt_metrics.py:80-81`
**Issue:** `inner_zf.extractall(out_path)` is safe on Python 3.12+ because CPython
strips leading slashes and collapses `../` components internally. However, the
script's module docstring advertises it as a standalone tool requiring only
`stdlib + cryptography`, with no minimum Python version stated. If a user runs the
script under Python 3.10 or 3.11.3 or earlier, the built-in mitigation is absent
and a maliciously crafted archive could write files outside `out_path` (classic
zip-slip). The decryption layer provides no protection here since anyone with the
source code has the key.

**Fix — option A (preferred):** Add explicit member-path validation so the code is
safe regardless of Python version:
```python
import os

with zipfile.ZipFile(io.BytesIO(decrypted_bytes), "r") as inner_zf:
    for member in inner_zf.infolist():
        member_path = (out_path / member.filename).resolve()
        if not str(member_path).startswith(str(out_path.resolve()) + os.sep):
            raise ValueError(
                f"Attempted path traversal in archive member: {member.filename!r}"
            )
        inner_zf.extract(member, out_path)
```

**Fix — option B (minimal):** Add a `# requires Python >= 3.12` annotation to the
module docstring and/or add `python_requires = ">=3.12"` to `pyproject.toml`
(already set to `>=3.13`; just document it in the script itself).

---

### WR-05: No test for `InvalidToken` exception path

**File:** `tests/test_decryption.py` (missing test)
**Issue:** `decrypt_archive` explicitly raises `InvalidToken` (documented in its
docstring), and the CLI has a dedicated handler for it (lines 106-112). Neither the
`TestDecryptArchive` class nor `TestDecryptCLI` exercises this code path. A
regression that silently swallows decryption failures would go undetected.

**Fix:** Add a test that creates a valid outer zip containing `data.enc` with
garbage bytes and asserts `InvalidToken` is raised:
```python
def test_corrupt_data_enc_raises_invalidtoken(self, tmp_path):
    """A zip whose data.enc is not a valid Fernet token raises InvalidToken."""
    from cryptography.fernet import InvalidToken

    bad_zip = tmp_path / "bad.zip"
    with zipfile.ZipFile(str(bad_zip), "w") as zf:
        zf.writestr("data.enc", b"not-a-fernet-token")

    with pytest.raises(InvalidToken):
        decrypt_archive(str(bad_zip))
```

---

### WR-06: No test for `BadZipFile` — corrupt outer zip is untested

**File:** `tests/test_decryption.py` (missing test)
**Issue:** Passing a file that exists but is not a valid zip raises
`zipfile.BadZipFile`. No test verifies that this exception propagates correctly
from `decrypt_archive`, nor that the CLI handles it gracefully (which it currently
does not — see WR-01). Without this test, both the exception-propagation contract
and the CLI handler (once added) are untested.

**Fix:**
```python
def test_not_a_zip_raises_badzipfile(self, tmp_path):
    """A non-zip file raises zipfile.BadZipFile."""
    not_a_zip = tmp_path / "file.zip"
    not_a_zip.write_bytes(b"this is not a zip file")

    with pytest.raises(zipfile.BadZipFile):
        decrypt_archive(str(not_a_zip))
```

---

## Info

### IN-01: `_make_encrypted_zip` helper duplicated across two test classes

**File:** `tests/test_decryption.py:34-48` and `tests/test_decryption.py:148-157`
**Issue:** The `_make_encrypted_zip` method is defined identically in both
`TestDecryptArchive` and `TestDecryptCLI`. Any future change to the test fixture
(adding a third CSV, changing metadata) requires two edits and risks divergence.
**Fix:** Extract to a module-level pytest fixture or a shared helper function:
```python
@pytest.fixture
def encrypted_zip(tmp_path):
    csv_dir = tmp_path / "csvs"
    csv_dir.mkdir()
    (csv_dir / "vco.test.com.06-2026.csv").write_text("col1,col2\n1,2\n")
    (csv_dir / "vco.test.com.07-2026.csv").write_text("col1,col2\n3,4\n")
    zip_path = tmp_path / "export.zip"
    create_encrypted_archive(str(csv_dir), str(zip_path), metadata={"version": "1.4"})
    return zip_path
```

---

### IN-02: Weak assertion in `test_cli_success_prints_file_count`

**File:** `tests/test_decryption.py:183`
**Issue:** `assert "2" in result.stdout` passes as long as the digit `"2"` appears
anywhere in stdout — including in the output path (e.g. `"/tmp/pytest-of-user/pytest-2/..."`).
The assertion is essentially unfalsifiable.
**Fix:** Assert the specific message fragment:
```python
assert "Decrypted 2 files" in result.stdout
```

---

### IN-03: No CLI test for the optional `[output-dir]` argument

**File:** `tests/test_decryption.py` (missing test)
**Issue:** `TestDecryptCLI` only tests the no-`output-dir` code path (default stem
directory). The `sys.argv` parsing at `decrypt_metrics.py:96` that handles the
second argument is never exercised from the CLI test suite.
**Fix:** Add one test that passes an explicit output directory and verifies the
CSV files land there:
```python
def test_cli_custom_output_dir(self, tmp_path):
    zip_path = self._make_encrypted_zip(tmp_path)
    out_dir = tmp_path / "custom_out"
    result = subprocess.run(
        [sys.executable, "decrypt_metrics.py", str(zip_path), str(out_dir)],
        cwd=str(_PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert len(list(out_dir.glob("*.csv"))) == 2
```

---

### IN-04: Hardcoded Fernet key in plaintext

**File:** `decrypt_metrics.py:37`
**Issue:** `FERNET_KEY` is stored in plaintext in the source file. The comment
correctly characterises this as "obfuscation-grade protection" and acknowledges the
design intent. This finding is recorded for audit-trail completeness: the key is
identical to `crypto.py`, meaning anyone with either source file can decrypt any
archive produced by the pipeline. The `TestDecryptionKeyIdentity` test ensures the
two copies stay in sync.
**Fix:** No code change required given the documented security model. Consider
noting the Python-version minimum (Python 3.13+) in the module docstring alongside
the key comment, so that the implicit security dependency on `extractall`
path-sanitization (see WR-04) is visible in the same location.

---

### IN-05: CLI uses manual `sys.argv` parsing instead of `argparse`

**File:** `decrypt_metrics.py:86-96`
**Issue:** The `__main__` block parses arguments with raw `sys.argv` slicing. There
is no `--help` flag, no type coercion, and no way to add optional flags (e.g. a
future `--key` override) without rewriting the parsing logic. For a single-script
tool this is low priority, but it reduces discoverability.
**Fix:** Replace with a minimal `argparse` parser:
```python
import argparse

parser = argparse.ArgumentParser(
    description="Decrypt an encrypted metrics archive and extract CSV files."
)
parser.add_argument("encrypted_zip", help="Path to the encrypted outer zip file.")
parser.add_argument(
    "output_dir", nargs="?", default=None,
    help="Directory where CSV files are extracted (default: zip stem)."
)
args = parser.parse_args()
zip_arg, out_arg = args.encrypted_zip, args.output_dir
```

---

_Reviewed: 2026-08-22_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
