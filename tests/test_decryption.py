"""Tests for decrypt_metrics.py — standalone decryption script.

Covers: DEC-01 (standalone, no project imports, CLI) and DEC-02 (roundtrip
byte-for-byte correctness).

Test classes:
    TestDecryptArchive         — core decrypt_archive() function behaviour
    TestDecryptionKeyIdentity  — embedded key matches crypto module key
    TestDecryptCLI             — CLI interface and standalone verification
    TestAutoDetect             — _detect_format() auto-detection (DEC-03)
    TestDecodeCombinedCsv      — decode_combined_csv() integration (DEC-04)
"""

import base64
import binascii
import csv
import hashlib
import math
import re
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

import decrypt_metrics
from crypto import FERNET_KEY as CRYPTO_FERNET_KEY
from decrypt_metrics import FERNET_KEY, decrypt_archive
from encoder import encode_record_hash, SENTINEL_HASH, STRUCT_FORMAT, STRUCT_VERSION
from output import create_encrypted_archive


# ── helpers ───────────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).parent.parent
_TEST_UUID = "550e8400-e29b-41d4-a716-446655440000"


def _make_encrypted_zip(tmp_path):
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


def _make_simple_combined_csv(tmp_path, uuid=_TEST_UUID) -> Path:
    """Create a minimal combined CSV with one edge and one month."""
    csv_path = tmp_path / "vco116.combined.csv"
    months_data = [{"label": "07-2026", "95th": 100.0, "peak": 200.0}]
    record_hash = encode_record_hash(months_data, uuid)
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["Edge UUID", "Edge Name", "Record Hash"],
        )
        writer.writeheader()
        writer.writerow(
            {"Edge UUID": uuid, "Edge Name": "edge1", "Record Hash": record_hash}
        )
    return csv_path


class TestDecryptArchive:
    """Tests for the decrypt_archive() function."""

    def _make_encrypted_zip(self, tmp_path):
        """Create an encrypted archive containing 2 CSV files."""
        return _make_encrypted_zip(tmp_path)

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
        """Create an encrypted archive; returns zip_path only."""
        return _make_encrypted_zip(tmp_path)[0]

    def _make_combined_csv(self, tmp_path) -> Path:
        """Create a minimal combined CSV with one edge and one month."""
        return _make_simple_combined_csv(tmp_path)

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
        assert "Decrypted 2 files" in result.stdout

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
            r"\bimport encoder\b",
            r"\bfrom encoder\b",
        ]

        for line in code_lines:
            for pattern in bad_patterns:
                assert not re.search(pattern, line), (
                    f"Found forbidden project import in decrypt_metrics.py:\n  {line!r}"
                )

    def test_cli_csv_input_exits_zero(self, tmp_path):
        """Running decrypt_metrics.py on a combined CSV exits 0."""
        csv_path = self._make_combined_csv(tmp_path)
        result = subprocess.run(
            [sys.executable, "decrypt_metrics.py", str(csv_path)],
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Expected exit 0 but got {result.returncode}.\n"
            f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )
        assert "Decoded 1 file" in result.stdout


# ── decode_record_hash unit tests ─────────────────────────────────────────────


class TestDecodeRecordHash:
    """Unit tests for decrypt_metrics.decode_record_hash."""

    UUID = "550e8400-e29b-41d4-a716-446655440000"

    def test_normal_single_month(self):
        """Encode one month then decode → same label and exact metric values."""
        months_data = [{"label": "07-2026", "95th": 100.0, "peak": 200.0}]
        record_hash = encode_record_hash(months_data, self.UUID)
        result = decrypt_metrics.decode_record_hash(record_hash, self.UUID)
        assert len(result) == 1
        assert result[0]["label"] == "07-2026"
        assert result[0]["95th"] == 100.0
        assert result[0]["peak"] == 200.0

    def test_sentinel_hash_returns_placeholder(self):
        """SENTINEL_HASH input returns a single placeholder dict with NaN metrics."""
        result = decrypt_metrics.decode_record_hash(SENTINEL_HASH, self.UUID)
        assert len(result) == 1
        assert result[0]["label"] == ""
        assert math.isnan(result[0]["95th"])
        assert math.isnan(result[0]["peak"])

    def test_multi_month_returns_correct_count(self):
        """Encoding 3 months then decoding produces exactly 3 dicts in order."""
        months_data = [
            {"label": "06-2026", "95th": 10.0, "peak": 20.0},
            {"label": "07-2026", "95th": 30.0, "peak": 40.0},
            {"label": "08-2026", "95th": 50.0, "peak": 60.0},
        ]
        record_hash = encode_record_hash(months_data, self.UUID)
        result = decrypt_metrics.decode_record_hash(record_hash, self.UUID)
        assert len(result) == 3
        assert result[0]["label"] == "06-2026"
        assert result[1]["label"] == "07-2026"
        assert result[2]["label"] == "08-2026"

    def test_last30d_label_roundtrips(self):
        """'last30d' label encodes as month_year=0 and decodes back to 'last30d'."""
        months_data = [{"label": "last30d", "95th": 99.0, "peak": 199.0}]
        record_hash = encode_record_hash(months_data, self.UUID)
        result = decrypt_metrics.decode_record_hash(record_hash, self.UUID)
        assert result[0]["label"] == "last30d"

    def test_invalid_base64_raises(self):
        """A non-base64 string raises binascii.Error."""
        with pytest.raises(binascii.Error):
            decrypt_metrics.decode_record_hash("not-valid-base64!!!", self.UUID)

    def test_wrong_version_raises_valueerror(self):
        """A hash with version field != STRUCT_VERSION raises ValueError mentioning 'version'."""
        args = [99, 0]  # version=99 (wrong), month_count=0
        for _ in range(12):
            args.extend([0, -1.0, -1.0])
        packed = struct.pack(STRUCT_FORMAT, *args)
        xor_key = hashlib.sha256(self.UUID.encode("utf-8")).digest() * 8
        obfuscated = bytes(a ^ b for a, b in zip(packed, xor_key))
        bad_hash = base64.b64encode(obfuscated).decode("ascii")
        with pytest.raises(ValueError, match="version"):
            decrypt_metrics.decode_record_hash(bad_hash, self.UUID)

    def test_invalid_month_count_raises_valueerror(self):
        """A hash with month_count > MAX_MONTHS raises ValueError mentioning 'month_count'."""
        args = [STRUCT_VERSION, 255]  # version=1 (correct), month_count=255 (> MAX_MONTHS)
        for _ in range(12):
            args.extend([0, -1.0, -1.0])
        packed = struct.pack(STRUCT_FORMAT, *args)
        xor_key = hashlib.sha256(self.UUID.encode("utf-8")).digest() * 8
        obfuscated = bytes(a ^ b for a, b in zip(packed, xor_key))
        bad_hash = base64.b64encode(obfuscated).decode("ascii")
        with pytest.raises(ValueError, match="month_count"):
            decrypt_metrics.decode_record_hash(bad_hash, self.UUID)


# ── round-trip tests ──────────────────────────────────────────────────────────


class TestRoundTrip:
    """encode_record_hash → decode_record_hash round-trip fidelity tests."""

    UUID = "550e8400-e29b-41d4-a716-446655440000"

    def _encode_then_decode(self, months_data: list[dict]) -> list[dict]:
        """Helper: encode with encoder then decode with decrypt_metrics."""
        record_hash = encode_record_hash(months_data, self.UUID)
        return decrypt_metrics.decode_record_hash(record_hash, self.UUID)

    def test_roundtrip_zero_metrics(self):
        """Zero metric values survive encode/decode unchanged (not confused with NaN sentinel)."""
        months_in = [{"label": "07-2026", "95th": 0.0, "peak": 0.0}]
        result = self._encode_then_decode(months_in)
        assert result[0]["label"] == "07-2026"
        assert result[0]["95th"] == 0.0
        assert result[0]["peak"] == 0.0

    def test_roundtrip_max_metrics(self):
        """Maximum metric value (100000.0) round-trips exactly."""
        months_in = [{"label": "07-2026", "95th": 100000.0, "peak": 100000.0}]
        result = self._encode_then_decode(months_in)
        assert result[0]["95th"] == 100000.0
        assert result[0]["peak"] == 100000.0

    def test_roundtrip_normal_metrics(self):
        """Normal float metrics (1234.56, 5678.9) survive round-trip within float precision."""
        months_in = [{"label": "07-2026", "95th": 1234.56, "peak": 5678.9}]
        result = self._encode_then_decode(months_in)
        assert result[0]["95th"] == pytest.approx(1234.56)
        assert result[0]["peak"] == pytest.approx(5678.9)

    def test_roundtrip_partial_months(self):
        """NaN metrics encode as -1.0 sentinel and decode back to NaN."""
        months_in = [{"label": "07-2026", "95th": float("nan"), "peak": float("nan")}]
        result = self._encode_then_decode(months_in)
        assert math.isnan(result[0]["95th"])
        assert math.isnan(result[0]["peak"])

    def test_roundtrip_mixed_nan_and_value(self):
        """Mixed row: NaN 95th decodes to NaN, non-NaN peak decodes to original value."""
        months_in = [{"label": "07-2026", "95th": float("nan"), "peak": 500.0}]
        result = self._encode_then_decode(months_in)
        assert math.isnan(result[0]["95th"])
        assert result[0]["peak"] == 500.0

    def test_roundtrip_twelve_months(self):
        """All 12 months encode and decode with correct labels and metric values."""
        months_in = [
            {"label": f"{i:02d}-2026", "95th": float(i * 100), "peak": float(i * 200)}
            for i in range(1, 13)
        ]
        result = self._encode_then_decode(months_in)
        assert len(result) == 12
        for i, row in enumerate(result):
            assert row["label"] == f"{i + 1:02d}-2026"
            assert row["95th"] == pytest.approx(float((i + 1) * 100))
            assert row["peak"] == pytest.approx(float((i + 1) * 200))


# ── auto-detection tests ──────────────────────────────────────────────────────


class TestAutoDetect:
    """Tests for _detect_zip_format() auto-detection (DEC-03)."""

    def test_encrypted_zip_returns_encrypted(self, tmp_path):
        """A zip with data.enc is detected as 'encrypted' format."""
        csv_dir = tmp_path / "csvs"
        csv_dir.mkdir()
        (csv_dir / "vco.test.com.06-2026.csv").write_text("col1,col2\n1,2\n")
        zip_path = tmp_path / "export.zip"
        create_encrypted_archive(
            str(csv_dir), str(zip_path), metadata={"version": "1.4"}
        )
        assert decrypt_metrics._detect_zip_format(str(zip_path)) == "encrypted"

    def test_obfuscated_zip_returns_obfuscated(self, tmp_path):
        """A zip with *.combined.csv is detected as 'obfuscated' format."""
        csv_path = _make_simple_combined_csv(tmp_path)
        zip_path = tmp_path / "export.zip"
        import zipfile as _zf
        with _zf.ZipFile(zip_path, "w") as zf:
            zf.write(csv_path, csv_path.name)
        assert decrypt_metrics._detect_zip_format(str(zip_path)) == "obfuscated"

    def test_plain_zip_returns_plain(self, tmp_path):
        """A zip with per-month CSVs is detected as 'plain' format."""
        zip_path = tmp_path / "export.zip"
        import zipfile as _zf
        with _zf.ZipFile(zip_path, "w") as zf:
            zf.writestr("vco.test.com.06-2026.csv", "col1,col2\n1,2\n")
        assert decrypt_metrics._detect_zip_format(str(zip_path)) == "plain"


# ── decode_combined_csv integration tests ─────────────────────────────────────


class TestDecodeCombinedCsv:
    """Integration tests for decode_combined_csv() (DEC-04)."""

    UUID = "550e8400-e29b-41d4-a716-446655440000"
    UUID2 = "660e8400-e29b-41d4-a716-446655440001"

    def _make_combined_csv(self, tmp_path, rows: list[dict]) -> Path:
        """Write a minimal combined CSV with multiple edges.

        Each dict in rows must have keys: "uuid", "name", "months_data".
        """
        csv_path = tmp_path / "vco116.combined.csv"
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(
                fh, fieldnames=["Edge UUID", "Edge Name", "Record Hash"]
            )
            writer.writeheader()
            for row in rows:
                if row["uuid"] == "":
                    record_hash = SENTINEL_HASH
                else:
                    record_hash = encode_record_hash(row["months_data"], row["uuid"])
                writer.writerow(
                    {
                        "Edge UUID": row["uuid"],
                        "Edge Name": row["name"],
                        "Record Hash": record_hash,
                    }
                )
        return csv_path

    def _make_simple_csv(self, tmp_path, months_data: list[dict]) -> Path:
        """Single-edge helper using default UUID and name."""
        return self._make_combined_csv(
            tmp_path,
            [{"uuid": self.UUID, "name": "edge1", "months_data": months_data}],
        )

    def test_returns_output_directory(self, tmp_path):
        """decode_combined_csv returns the output directory path."""
        csv_path = self._make_simple_csv(
            tmp_path, [{"label": "07-2026", "95th": 100.0, "peak": 200.0}]
        )
        out = decrypt_metrics.decode_combined_csv(str(csv_path))
        assert out.is_dir()

    def test_one_file_per_month(self, tmp_path):
        """1 edge × 2 months produces 2 separate CSV files."""
        csv_path = self._make_simple_csv(
            tmp_path,
            [
                {"label": "06-2026", "95th": 10.0, "peak": 20.0},
                {"label": "07-2026", "95th": 30.0, "peak": 40.0},
            ],
        )
        out = decrypt_metrics.decode_combined_csv(str(csv_path))
        csv_files = sorted(f.name for f in out.glob("*.csv"))
        assert csv_files == ["vco116.06-2026.csv", "vco116.07-2026.csv"]

    def test_per_month_file_has_correct_columns(self, tmp_path):
        """Per-month CSV has Month-Year, 30 Days 95th, 30 Days P95 Peak columns
        and does not have Record Hash."""
        csv_path = self._make_simple_csv(
            tmp_path, [{"label": "07-2026", "95th": 100.0, "peak": 200.0}]
        )
        out = decrypt_metrics.decode_combined_csv(str(csv_path))
        month_file = out / "vco116.07-2026.csv"
        with open(month_file, encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            assert "Month-Year" in reader.fieldnames
            assert "30 Days 95th" in reader.fieldnames
            assert "30 Days P95 Peak" in reader.fieldnames
            assert "Record Hash" not in reader.fieldnames

    def test_per_month_file_has_one_row_per_edge(self, tmp_path):
        """Each per-month file has one row per edge for that month."""
        csv_path = self._make_simple_csv(
            tmp_path,
            [
                {"label": "06-2026", "95th": 10.0, "peak": 20.0},
                {"label": "07-2026", "95th": 30.0, "peak": 40.0},
            ],
        )
        out = decrypt_metrics.decode_combined_csv(str(csv_path))
        for month_file in out.glob("*.csv"):
            with open(month_file, encoding="utf-8-sig") as fh:
                rows = list(csv.DictReader(fh))
            assert len(rows) == 1

    def test_output_filename_convention(self, tmp_path):
        """Output files follow {vco_prefix}.{MM-YYYY}.csv convention."""
        csv_path = self._make_simple_csv(
            tmp_path, [{"label": "07-2026", "95th": 100.0, "peak": 200.0}]
        )
        out = decrypt_metrics.decode_combined_csv(str(csv_path))
        csv_files = list(out.glob("*.csv"))
        assert len(csv_files) == 1
        assert csv_files[0].name == "vco116.07-2026.csv"

    def test_sentinel_only_produces_fallback_file(self, tmp_path):
        """An input with only sentinel edges writes a single fallback decoded file."""
        csv_path = self._make_combined_csv(
            tmp_path,
            [{"uuid": "", "name": "sentinel-edge", "months_data": []}],
        )
        out = decrypt_metrics.decode_combined_csv(str(csv_path))
        csv_files = list(out.glob("*.csv"))
        assert len(csv_files) == 1
        assert csv_files[0].name == "vco116.decoded.csv"
        with open(csv_files[0], encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == 1
        assert rows[0]["Month-Year"] == ""

    def test_sentinel_included_in_every_month_file(self, tmp_path):
        """Sentinel edges appear in every per-month file."""
        csv_path = self._make_combined_csv(
            tmp_path,
            [
                {
                    "uuid": self.UUID,
                    "name": "edge1",
                    "months_data": [
                        {"label": "06-2026", "95th": 10.0, "peak": 20.0},
                        {"label": "07-2026", "95th": 30.0, "peak": 40.0},
                    ],
                },
                {"uuid": "", "name": "sentinel-edge", "months_data": []},
            ],
        )
        out = decrypt_metrics.decode_combined_csv(str(csv_path))
        for month_file in sorted(out.glob("*.csv")):
            with open(month_file, encoding="utf-8-sig") as fh:
                rows = list(csv.DictReader(fh))
            assert len(rows) == 2
            names = {r["Edge Name"] for r in rows}
            assert "sentinel-edge" in names

    def test_multiple_edges_split_by_month(self, tmp_path):
        """2 edges across 2 months are split into per-month files correctly."""
        csv_path = self._make_combined_csv(
            tmp_path,
            [
                {
                    "uuid": self.UUID,
                    "name": "edge1",
                    "months_data": [
                        {"label": "06-2026", "95th": 10.0, "peak": 20.0},
                        {"label": "07-2026", "95th": 30.0, "peak": 40.0},
                    ],
                },
                {
                    "uuid": self.UUID2,
                    "name": "edge2",
                    "months_data": [
                        {"label": "07-2026", "95th": 50.0, "peak": 60.0},
                    ],
                },
            ],
        )
        out = decrypt_metrics.decode_combined_csv(str(csv_path))
        csv_files = sorted(out.glob("*.csv"), key=lambda p: p.name)
        assert len(csv_files) == 2

        with open(csv_files[0], encoding="utf-8-sig") as fh:
            rows_06 = list(csv.DictReader(fh))
        assert len(rows_06) == 1
        assert rows_06[0]["Edge Name"] == "edge1"

        with open(csv_files[1], encoding="utf-8-sig") as fh:
            rows_07 = list(csv.DictReader(fh))
        assert len(rows_07) == 2

    def test_output_dir_parameter(self, tmp_path):
        """Passing output_dir places per-month CSVs inside that directory."""
        csv_path = self._make_simple_csv(
            tmp_path, [{"label": "07-2026", "95th": 100.0, "peak": 200.0}]
        )
        custom_dir = tmp_path / "custom"
        out = decrypt_metrics.decode_combined_csv(str(csv_path), output_dir=str(custom_dir))
        assert out.resolve() == custom_dir.resolve()
        assert len(list(custom_dir.glob("*.csv"))) == 1

    def test_output_written_with_utf8_bom(self, tmp_path):
        """Per-month CSV files are written with UTF-8 BOM (utf-8-sig encoding)."""
        csv_path = self._make_simple_csv(
            tmp_path, [{"label": "07-2026", "95th": 100.0, "peak": 200.0}]
        )
        out = decrypt_metrics.decode_combined_csv(str(csv_path))
        for month_file in out.glob("*.csv"):
            raw_bytes = month_file.read_bytes()
            assert raw_bytes[:3] == b"\xef\xbb\xbf", (
                f"Expected UTF-8 BOM at start of {month_file.name}"
            )

    def test_default_output_dir_uses_input_stem(self, tmp_path):
        """When output_dir is omitted, output directory is named after the input stem."""
        csv_path = self._make_simple_csv(
            tmp_path, [{"label": "07-2026", "95th": 100.0, "peak": 200.0}]
        )
        out = decrypt_metrics.decode_combined_csv(str(csv_path))
        assert out.name == "vco116.combined"
        assert out.parent == csv_path.parent

    def test_metric_values_written_as_integers(self, tmp_path):
        """Whole-number metrics are written as integers (100, not 100.0) in CSV."""
        csv_path = self._make_simple_csv(
            tmp_path, [{"label": "07-2026", "95th": 100.0, "peak": 200.0}]
        )
        out = decrypt_metrics.decode_combined_csv(str(csv_path))
        month_file = out / "vco116.07-2026.csv"
        with open(month_file, encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        assert rows[0]["30 Days 95th"] == "100"
        assert rows[0]["30 Days P95 Peak"] == "200"

    def test_zero_metric_written_as_integer(self, tmp_path):
        """Zero metrics are written as '0', not '0.0'."""
        csv_path = self._make_simple_csv(
            tmp_path, [{"label": "07-2026", "95th": 0.0, "peak": 0.0}]
        )
        out = decrypt_metrics.decode_combined_csv(str(csv_path))
        month_file = out / "vco116.07-2026.csv"
        with open(month_file, encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        assert rows[0]["30 Days 95th"] == "0"
        assert rows[0]["30 Days P95 Peak"] == "0"

    def test_empty_csv_raises_valueerror(self, tmp_path):
        """An empty CSV file (no header row) raises ValueError."""
        empty_csv = tmp_path / "empty.csv"
        empty_csv.write_text("", encoding="utf-8-sig")
        with pytest.raises(ValueError, match="no header row"):
            decrypt_metrics.decode_combined_csv(str(empty_csv))

    def test_missing_required_columns_raises_valueerror(self, tmp_path):
        """A CSV with wrong column names raises ValueError mentioning missing columns."""
        bad_csv = tmp_path / "bad.csv"
        bad_csv.write_text("Col1,Col2\na,b\n", encoding="utf-8-sig")
        with pytest.raises(ValueError, match="missing required columns"):
            decrypt_metrics.decode_combined_csv(str(bad_csv))


# ── _decode_month_year unit tests ────────────────────────────────────────────


class TestDecodeMonthYear:
    """Unit tests for decrypt_metrics._decode_month_year validation."""

    def test_invalid_month_zero_with_nonzero_year_raises(self):
        """month_year_int=16 decodes month=0, year=2001 -- month out of range."""
        with pytest.raises(ValueError, match="out of range"):
            decrypt_metrics._decode_month_year(16)

    def test_invalid_month_thirteen_raises(self):
        """month_year_int=0x1D decodes month=13 -- month out of range."""
        # 0x1D = 29 → month = 29 & 0x0F = 13, year = (29 >> 4) + 2000 = 2001
        with pytest.raises(ValueError, match="out of range"):
            decrypt_metrics._decode_month_year(0x1D)
