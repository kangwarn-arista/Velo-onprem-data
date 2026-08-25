"""Tests for crypto module and encrypted archive structure.

Covers: FERNET_KEY validity, encrypt_blob/decrypt_blob roundtrip,
binary-blob checks, create_encrypted_archive two-file structure.
"""

import base64
import json
import zipfile

import pytest

from crypto import FERNET_KEY, decrypt_blob, encrypt_blob
from output import create_encrypted_archive


# ── crypto module ─────────────────────────────────────────────────────────


class TestFernetKey:
    """Tests for the embedded Fernet key constant."""

    def test_key_is_valid_base64(self):
        """FERNET_KEY is a 44-byte URL-safe base64 Fernet key."""
        assert isinstance(FERNET_KEY, bytes)
        assert len(FERNET_KEY) == 44
        decoded = base64.urlsafe_b64decode(FERNET_KEY)
        assert len(decoded) == 32


class TestEncryptBlob:
    """Tests for encrypt_blob and decrypt_blob."""

    def test_encrypt_returns_different_bytes(self):
        """encrypt_blob returns bytes different from the input."""
        data = b"sensitive metric data"
        encrypted = encrypt_blob(data)
        assert isinstance(encrypted, bytes)
        assert encrypted != data

    def test_roundtrip(self):
        """decrypt_blob(encrypt_blob(data)) returns original data byte-for-byte."""
        data = b"edge-01,4.2,3.1,7.3\nedge-02,1.0,0.5,1.5\n"
        assert decrypt_blob(encrypt_blob(data)) == data

    def test_encrypted_does_not_contain_plaintext(self):
        """encrypt_blob output does not contain the original plaintext."""
        data = b"plaintext csv content"
        encrypted = encrypt_blob(data)
        assert encrypted != data
        assert data not in encrypted


# ── create_encrypted_archive ──────────────────────────────────────────────


class TestCreateEncryptedArchive:
    """Tests for the encrypted archive two-file structure."""

    def _make_csv_dir(self, tmp_path):
        """Create a directory with 2 dummy CSV files."""
        csv_dir = tmp_path / "csvs"
        csv_dir.mkdir()
        (csv_dir / "vco.test.com.06-2026.csv").write_text("col1,col2\n1,2\n")
        (csv_dir / "vco.test.com.07-2026.csv").write_text("col1,col2\n3,4\n")
        return csv_dir

    def test_creates_zip_file(self, tmp_path):
        """create_encrypted_archive produces a zip file at the specified path."""
        csv_dir = self._make_csv_dir(tmp_path)
        zip_path = str(tmp_path / "output.zip")
        metadata = {"version": "1.0", "vco_host": "vco.test.com"}

        create_encrypted_archive(str(csv_dir), zip_path, metadata=metadata)

        assert (tmp_path / "output.zip").exists()

    def test_archive_contains_exactly_two_members(self, tmp_path):
        """Encrypted archive contains exactly 2 members: _metadata.json and data.enc."""
        csv_dir = self._make_csv_dir(tmp_path)
        zip_path = str(tmp_path / "output.zip")
        metadata = {"version": "1.0"}

        create_encrypted_archive(str(csv_dir), zip_path, metadata=metadata)

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = sorted(zf.namelist())
        assert names == ["_metadata.json", "data.enc"]

    def test_data_enc_is_not_a_zipfile(self, tmp_path):
        """data.enc inside the archive cannot be opened as a zip (BadZipFile)."""
        csv_dir = self._make_csv_dir(tmp_path)
        zip_path = str(tmp_path / "output.zip")
        metadata = {"version": "1.0"}

        create_encrypted_archive(str(csv_dir), zip_path, metadata=metadata)

        with zipfile.ZipFile(zip_path, "r") as zf:
            enc_data = zf.read("data.enc")

        import io

        with pytest.raises(zipfile.BadZipFile):
            zipfile.ZipFile(io.BytesIO(enc_data), "r")

    def test_metadata_matches_input(self, tmp_path):
        """_metadata.json inside the archive matches the metadata dict passed in."""
        csv_dir = self._make_csv_dir(tmp_path)
        zip_path = str(tmp_path / "output.zip")
        metadata = {"version": "1.4", "vco_host": "vco.test.com", "generated_at": "2026-08-22"}

        create_encrypted_archive(str(csv_dir), zip_path, metadata=metadata)

        with zipfile.ZipFile(zip_path, "r") as zf:
            stored = json.loads(zf.read("_metadata.json"))
        assert stored == metadata

    def test_returns_zip_path(self, tmp_path):
        """create_encrypted_archive returns the zip_path string."""
        csv_dir = self._make_csv_dir(tmp_path)
        zip_path = str(tmp_path / "output.zip")
        metadata = {"version": "1.0"}

        result = create_encrypted_archive(str(csv_dir), zip_path, metadata=metadata)

        assert result == zip_path

    def test_data_enc_decrypts_to_valid_zip(self, tmp_path):
        """data.enc can be decrypted back to a valid zip containing the original CSVs."""
        csv_dir = self._make_csv_dir(tmp_path)
        zip_path = str(tmp_path / "output.zip")

        create_encrypted_archive(str(csv_dir), zip_path, metadata={"v": "1"})

        with zipfile.ZipFile(zip_path, "r") as zf:
            enc_data = zf.read("data.enc")

        import io

        decrypted = decrypt_blob(enc_data)
        with zipfile.ZipFile(io.BytesIO(decrypted), "r") as inner_zf:
            names = sorted(inner_zf.namelist())
        assert "vco.test.com.06-2026.csv" in names
        assert "vco.test.com.07-2026.csv" in names

    def test_no_metadata_produces_single_member(self, tmp_path):
        """Without metadata, archive contains only data.enc."""
        csv_dir = self._make_csv_dir(tmp_path)
        zip_path = str(tmp_path / "output.zip")

        create_encrypted_archive(str(csv_dir), zip_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
        assert names == ["data.enc"]
