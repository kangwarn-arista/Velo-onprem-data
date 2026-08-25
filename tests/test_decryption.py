"""Tests for decrypt_metrics.py — standalone decryption script.

Covers: DEC-01 (standalone, no project imports, CLI) and DEC-02 (roundtrip
byte-for-byte correctness).

Test classes:
    TestDecryptArchive         — core decrypt_archive() function behaviour
    TestDecryptionKeyIdentity  — embedded key matches crypto module key
    TestDecryptCLI             — CLI interface and standalone verification
"""

import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

import decrypt_metrics
from crypto import FERNET_KEY as CRYPTO_FERNET_KEY
from decrypt_metrics import FERNET_KEY, decrypt_archive
from output import create_encrypted_archive


# ── helpers ───────────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).parent.parent


class TestDecryptArchive:
    """Tests for the decrypt_archive() function."""

    def _make_encrypted_zip(self, tmp_path):
        """Create an encrypted archive containing 2 CSV files.

        Returns:
            Tuple of (zip_path: Path, csv_dir: Path)
        """
        csv_dir = tmp_path / "csvs"
        csv_dir.mkdir()
        (csv_dir / "vco.test.com.06-2026.csv").write_text("col1,col2\n1,2\n")
        (csv_dir / "vco.test.com.07-2026.csv").write_text("col1,col2\n3,4\n")
        zip_path = tmp_path / "export.zip"
        create_encrypted_archive(
            str(csv_dir), str(zip_path), metadata={"version": "1.4"}
        )
        return zip_path, csv_dir

    def test_roundtrip_produces_csv_files(self, tmp_path):
        """Decrypting an encrypted archive produces the expected number of CSV files."""
        zip_path, _ = self._make_encrypted_zip(tmp_path)
        out_dir = tmp_path / "output"

        result = decrypt_archive(str(zip_path), str(out_dir))

        csv_files = sorted(result.glob("*.csv"))
        assert len(csv_files) == 2

    def test_decrypted_content_matches_originals(self, tmp_path):
        """Decrypted CSV bytes are identical to the originals (DEC-02)."""
        zip_path, csv_dir = self._make_encrypted_zip(tmp_path)
        out_dir = tmp_path / "output"

        result = decrypt_archive(str(zip_path), str(out_dir))

        for original in sorted(csv_dir.iterdir()):
            if not original.is_file():
                continue
            decrypted = result / original.name
            assert decrypted.exists(), f"Expected {original.name} in output"
            assert decrypted.read_bytes() == original.read_bytes(), (
                f"Content mismatch for {original.name}"
            )

    def test_default_output_dir_strips_zip_extension(self, tmp_path):
        """When output_dir is omitted, the output dir defaults to the zip stem."""
        zip_path, _ = self._make_encrypted_zip(tmp_path)

        result = decrypt_archive(str(zip_path))

        expected = zip_path.parent / zip_path.stem  # "export" (no .zip)
        assert result == expected

    def test_custom_output_dir(self, tmp_path):
        """Passing an explicit output_dir places CSV files there."""
        zip_path, _ = self._make_encrypted_zip(tmp_path)
        custom_dir = tmp_path / "custom"

        result = decrypt_archive(str(zip_path), str(custom_dir))

        assert result == custom_dir
        csv_files = list(custom_dir.glob("*.csv"))
        assert len(csv_files) == 2

    def test_missing_data_enc_raises_keyerror(self, tmp_path):
        """A zip without data.enc raises KeyError."""
        plain_zip = tmp_path / "plain.zip"
        with zipfile.ZipFile(str(plain_zip), "w") as zf:
            zf.writestr("readme.txt", "no encrypted payload here")

        with pytest.raises(KeyError):
            decrypt_archive(str(plain_zip))

    def test_nonexistent_file_raises_filenotfounderror(self, tmp_path):
        """Passing a nonexistent path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            decrypt_archive("/nonexistent/path/that/does/not/exist.zip")

    def test_output_dir_is_created(self, tmp_path):
        """decrypt_archive creates the output directory (including parents) if absent."""
        zip_path, _ = self._make_encrypted_zip(tmp_path)
        nested_dir = tmp_path / "deeply" / "nested" / "output"
        assert not nested_dir.exists()

        decrypt_archive(str(zip_path), str(nested_dir))

        assert nested_dir.exists()

    def test_returns_path_object(self, tmp_path):
        """decrypt_archive return type is pathlib.Path."""
        zip_path, _ = self._make_encrypted_zip(tmp_path)
        result = decrypt_archive(str(zip_path), str(tmp_path / "out"))
        assert isinstance(result, Path)

    def test_corrupt_data_enc_raises_invalidtoken(self, tmp_path):
        """A zip whose data.enc is not a valid Fernet token raises InvalidToken."""
        from cryptography.fernet import InvalidToken

        bad_zip = tmp_path / "bad.zip"
        with zipfile.ZipFile(str(bad_zip), "w") as zf:
            zf.writestr("data.enc", "not-a-fernet-token")

        with pytest.raises(InvalidToken):
            decrypt_archive(str(bad_zip))

    def test_not_a_zip_raises_badzipfile(self, tmp_path):
        """A non-zip file raises zipfile.BadZipFile."""
        not_a_zip = tmp_path / "file.zip"
        not_a_zip.write_bytes(b"this is not a zip file")

        with pytest.raises(zipfile.BadZipFile):
            decrypt_archive(str(not_a_zip))


# ── key identity ──────────────────────────────────────────────────────────────


class TestDecryptionKeyIdentity:
    """Verify embedded key matches the crypto module key."""

    def test_embedded_key_matches_crypto_module(self):
        """decrypt_metrics.FERNET_KEY must equal crypto.FERNET_KEY byte-for-byte.

        This ensures that data encrypted by the main pipeline can always be
        decrypted by the standalone script (DEC-01 + DEC-02).
        """
        assert FERNET_KEY == CRYPTO_FERNET_KEY


# ── CLI tests ─────────────────────────────────────────────────────────────────


class TestDecryptCLI:
    """Tests for the __main__ CLI interface."""

    def _make_encrypted_zip(self, tmp_path):
        csv_dir = tmp_path / "csvs"
        csv_dir.mkdir()
        (csv_dir / "vco.test.com.06-2026.csv").write_text("col1,col2\n1,2\n")
        (csv_dir / "vco.test.com.07-2026.csv").write_text("col1,col2\n3,4\n")
        zip_path = tmp_path / "export.zip"
        create_encrypted_archive(
            str(csv_dir), str(zip_path), metadata={"version": "1.4"}
        )
        return zip_path

    def test_cli_success_exit_code(self, tmp_path):
        """Running decrypt_metrics.py on a valid archive exits 0."""
        zip_path = self._make_encrypted_zip(tmp_path)
        result = subprocess.run(
            [sys.executable, "decrypt_metrics.py", str(zip_path)],
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Expected exit 0 but got {result.returncode}.\n"
            f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )
        assert "Decrypted" in result.stdout

    def test_cli_success_prints_file_count(self, tmp_path):
        """CLI stdout includes the number of decrypted files."""
        zip_path = self._make_encrypted_zip(tmp_path)
        result = subprocess.run(
            [sys.executable, "decrypt_metrics.py", str(zip_path)],
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        assert "2" in result.stdout  # 2 CSV files

    def test_cli_no_args_exits_nonzero(self):
        """Running with no arguments exits with a non-zero code."""
        result = subprocess.run(
            [sys.executable, "decrypt_metrics.py"],
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_cli_nonexistent_file_exits_nonzero(self):
        """Running with a nonexistent file path exits with code 1."""
        result = subprocess.run(
            [sys.executable, "decrypt_metrics.py", "/no/such/file.zip"],
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1

    def test_standalone_no_project_imports(self):
        """decrypt_metrics.py source has no imports from project modules.

        Uses word-boundary regex to avoid false positives from the
        ``cryptography`` package import (DEC-01 standalone requirement).
        """
        source_path = _PROJECT_ROOT / "decrypt_metrics.py"
        source_lines = source_path.read_text().splitlines()

        # Exclude comment lines
        code_lines = [
            line for line in source_lines
            if not line.lstrip().startswith("#")
        ]

        # Word-boundary patterns prevent "from cryptography" from matching
        # "from crypto" (which would be a false positive).
        bad_patterns = [
            r"\bimport crypto\b",
            r"\bfrom crypto\b",
            r"\bimport output\b",
            r"\bfrom output\b",
        ]

        for line in code_lines:
            for pattern in bad_patterns:
                assert not re.search(pattern, line), (
                    f"Found forbidden project import in decrypt_metrics.py:\n  {line!r}"
                )
