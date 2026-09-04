"""Tests for pipeline encryption wiring and temp directory cleanup.

Covers: OBFUSCATED env var branching (3-mode: 0=plain, 1=plain, 2=Fernet),
temp directory cleanup after archive creation in both encrypted and
unencrypted paths.
"""

import os
import zipfile

from unittest.mock import patch

from vco_edge_export import package_and_cleanup


# ── OBFUSCATED branching ──────────────────────────────────────────────────


class TestObfuscatedBranching:
    """Tests for OBFUSCATED env var routing."""

    def _make_csv_dir(self, tmp_path):
        """Create a directory with dummy CSV files."""
        csv_dir = tmp_path / "output"
        csv_dir.mkdir()
        (csv_dir / "vco.test.com.07-2026.csv").write_text("col1,col2\n1,2\n")
        return csv_dir

    def test_default_calls_plain_zip(self, tmp_path):
        """When OBFUSCATED is unset (default), the pipeline calls create_zip_archive."""
        csv_dir = self._make_csv_dir(tmp_path)
        zip_path = str(tmp_path / "out.zip")
        metadata = {"version": "1.0"}

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OBFUSCATED", None)
            with patch("vco_edge_export.create_encrypted_archive", wraps=__import__("output").create_encrypted_archive) as mock_enc, \
                 patch("vco_edge_export.create_zip_archive", wraps=__import__("output").create_zip_archive) as mock_zip:
                package_and_cleanup(str(csv_dir), zip_path, metadata)

        mock_zip.assert_called_once()
        mock_enc.assert_not_called()

    def test_obfuscated_zero_calls_plain_zip(self, tmp_path):
        """When OBFUSCATED is '0', the pipeline calls create_zip_archive."""
        csv_dir = self._make_csv_dir(tmp_path)
        zip_path = str(tmp_path / "out.zip")
        metadata = {"version": "1.0"}

        with patch.dict(os.environ, {"OBFUSCATED": "0"}):
            with patch("vco_edge_export.create_encrypted_archive", wraps=__import__("output").create_encrypted_archive) as mock_enc, \
                 patch("vco_edge_export.create_zip_archive", wraps=__import__("output").create_zip_archive) as mock_zip:
                package_and_cleanup(str(csv_dir), zip_path, metadata)

        mock_zip.assert_called_once()
        mock_enc.assert_not_called()

    def test_obfuscated_one_calls_plain_zip(self, tmp_path):
        """When OBFUSCATED is '1', the pipeline calls create_zip_archive (field-level mode)."""
        csv_dir = self._make_csv_dir(tmp_path)
        zip_path = str(tmp_path / "out.zip")
        metadata = {"version": "1.0"}

        with patch.dict(os.environ, {"OBFUSCATED": "1"}):
            with patch("vco_edge_export.create_encrypted_archive", wraps=__import__("output").create_encrypted_archive) as mock_enc, \
                 patch("vco_edge_export.create_zip_archive", wraps=__import__("output").create_zip_archive) as mock_zip:
                package_and_cleanup(str(csv_dir), zip_path, metadata)

        mock_zip.assert_called_once()
        mock_enc.assert_not_called()

    def test_obfuscated_two_calls_encrypted(self, tmp_path):
        """When obfuscation_mode='2', the pipeline calls create_encrypted_archive (Fernet path)."""
        csv_dir = self._make_csv_dir(tmp_path)
        zip_path = str(tmp_path / "out.zip")
        metadata = {"version": "1.0"}

        with patch("vco_edge_export.create_encrypted_archive", wraps=__import__("output").create_encrypted_archive) as mock_enc, \
             patch("vco_edge_export.create_zip_archive", wraps=__import__("output").create_zip_archive) as mock_zip:
            package_and_cleanup(str(csv_dir), zip_path, metadata, obfuscation_mode="2")

        mock_enc.assert_called_once()
        mock_zip.assert_not_called()


# ── Temp directory cleanup ────────────────────────────────────────────────


class TestTempDirectoryCleanup:
    """Tests for temp directory removal after archive creation."""

    def _make_csv_dir(self, tmp_path):
        """Create a directory with dummy CSV files."""
        csv_dir = tmp_path / "output"
        csv_dir.mkdir()
        (csv_dir / "vco.test.com.07-2026.csv").write_text("col1,col2\n1,2\n")
        return csv_dir

    def test_encrypted_path_cleans_temp_dir(self, tmp_path):
        """After archive creation (encrypted path, OBFUSCATED=2), the source output_dir no longer exists."""
        csv_dir = self._make_csv_dir(tmp_path)
        zip_path = str(tmp_path / "out.zip")
        metadata = {"version": "1.0"}

        with patch.dict(os.environ, {"OBFUSCATED": "2"}):
            package_and_cleanup(str(csv_dir), zip_path, metadata)

        assert not csv_dir.exists()

    def test_unencrypted_path_cleans_temp_dir(self, tmp_path):
        """After archive creation (unencrypted path), the source output_dir no longer exists."""
        csv_dir = self._make_csv_dir(tmp_path)
        zip_path = str(tmp_path / "out.zip")
        metadata = {"version": "1.0"}

        with patch.dict(os.environ, {"OBFUSCATED": "0"}):
            package_and_cleanup(str(csv_dir), zip_path, metadata)

        assert not csv_dir.exists()

    def test_zip_file_survives_cleanup(self, tmp_path):
        """The zip file itself still exists after cleanup."""
        csv_dir = self._make_csv_dir(tmp_path)
        zip_path = str(tmp_path / "out.zip")
        metadata = {"version": "1.0"}

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OBFUSCATED", None)
            package_and_cleanup(str(csv_dir), zip_path, metadata)

        assert os.path.exists(zip_path)
