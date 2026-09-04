"""Standalone offline tool for recovering metric CSVs from archives.

This script is fully self-contained: it has no imports from the main project
(crypto.py, output.py, etc.).  It embeds the Fernet key directly and only
requires stdlib plus the ``cryptography`` package.

Usage:
    python decrypt_metrics.py <zip-file> [<zip-file> ...] [-o OUTPUT_DIR]

Args:
    zip-file    One or more zip files produced by vco_edge_export.py.
                The format of each zip is auto-detected:
                  - Encrypted (contains ``data.enc``) — Fernet decrypt + extract.
                  - Field-level obfuscated (contains ``*.combined.csv``) —
                    extract + decode Record Hash into per-month CSVs.
                  - Plain (per-month CSVs) — extract only.
    -o          Optional output directory.  Defaults to a directory named
                after each zip's stem in the zip's parent directory.

Supported archive formats:

Encrypted archive (OBFUSCATED=2, produced by output.py::create_encrypted_archive):
    outer.zip
    ├── data.enc          Fernet-encrypted inner zip bytes
    └── _metadata.json    (optional) archive metadata

    inner.zip (after decryption)
    └── *.csv             Original CSV files with metric data

Obfuscated archive (OBFUSCATED=1, produced by output.py::create_zip_archive):
    outer.zip
    ├── *.combined.csv    Single CSV with Record Hash column
    └── _metadata.json    (optional) archive metadata

Plain archive (OBFUSCATED=0, produced by output.py::create_zip_archive):
    outer.zip
    ├── *.MM-YYYY.csv     Per-month CSV files with cleartext metrics
    └── _metadata.json    (optional) archive metadata
"""

import base64
import binascii
import csv
import hashlib
import io
import math
import os
import struct
import sys
import warnings
import zipfile
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

# Embedded key — intentionally duplicated from crypto.py.
# This is obfuscation-grade protection; the key is in plaintext by design so
# that this script can operate fully offline without importing from the main
# project.
FERNET_KEY = b"YVrZTl2xyS7QHyqxwaP2xd5gwMUjoctoo8RKUwjNi-8="

# -- Record Hash constants -- copied verbatim from encoder.py (DEC-05: zero project imports) --
STRUCT_VERSION: int = 1
STRUCT_FORMAT: str = "!HB" + "Hdd" * 12 + "37x"
MAX_MONTHS: int = 12
SENTINEL_HASH: str = base64.b64encode(b"\x00" * 256).decode("ascii")


def _derive_xor_key(uuid_str: str) -> bytes:
    """Derive a 256-byte XOR key from SHA-256(uuid_str).

    SHA-256 produces 32 bytes; repeated 8 times to reach 256 bytes.
    """
    digest = hashlib.sha256(uuid_str.encode("utf-8")).digest()
    return digest * 8


def _decode_month_year(month_year_int: int) -> str:
    """Decode a packed uint16 month-year value to a label string.

    0            → "last30d"
    (year-2000) << 4 | month  → "MM-YYYY"
    """
    if month_year_int == 0:
        return "last30d"
    month = month_year_int & 0x0F
    year = (month_year_int >> 4) + 2000
    if not (1 <= month <= 12):
        raise ValueError(
            f"Decoded month {month!r} out of range [1, 12] "
            f"(month_year_int={month_year_int!r})"
        )
    return f"{month:02d}-{year}"


def _decode_metric(value: float) -> float:
    """Convert a packed metric value back to its logical value.

    -1.0 sentinel (stored for NaN inputs) → float("nan")
    Any other value                       → unchanged
    """
    if value == -1.0:
        return float("nan")
    return value


def _detect_zip_format(path: str) -> str:
    """Classify a zip archive by inspecting its contents.

    Returns:
        ``"encrypted"``  — contains ``data.enc`` (Fernet-encrypted payload).
        ``"obfuscated"`` — contains a ``*.combined.csv`` file.
        ``"plain"``      — per-month CSVs or other files.

    Raises:
        FileNotFoundError: If *path* does not exist on disk.
        zipfile.BadZipFile: If *path* is not a valid zip archive.
    """
    resolved = Path(path).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"No such file: {path}")
    if not zipfile.is_zipfile(path):
        raise zipfile.BadZipFile(f"Not a zip file: {path}")

    with zipfile.ZipFile(resolved, "r") as zf:
        names = zf.namelist()
        if "data.enc" in names:
            return "encrypted"
        if any(n.endswith(".combined.csv") for n in names):
            return "obfuscated"
        return "plain"


def decode_record_hash(record_hash: str, edge_uuid: str) -> list[dict]:
    """Decode a 344-character Record Hash back into per-month metric dicts.

    Reverses the encode_record_hash pipeline: base64-decode, XOR-unmask,
    struct-unpack, month-year decode, metric sentinel conversion.

    Args:
        record_hash: 344-character base64-encoded obfuscated string produced
                     by encode_record_hash, or SENTINEL_HASH for edges with
                     missing/empty UUID.
        edge_uuid:   Edge UUID string used to derive the XOR key.

    Returns:
        List of dicts with keys "label", "95th", "peak" — one entry per
        active month slot.  SENTINEL_HASH input returns a single placeholder:
        [{"label": "", "95th": NaN, "peak": NaN}].

    Raises:
        binascii.Error: If record_hash is not valid base64.
        ValueError:     If the struct version field does not match
                        STRUCT_VERSION, or if month_count is out of range
                        [0, MAX_MONTHS].
    """
    if record_hash == SENTINEL_HASH:
        return [{"label": "", "95th": float("nan"), "peak": float("nan")}]

    raw = base64.b64decode(record_hash)
    xor_key = _derive_xor_key(edge_uuid)
    plain = bytes(a ^ b for a, b in zip(raw, xor_key))

    try:
        unpacked = struct.unpack(STRUCT_FORMAT, plain)
    except struct.error as exc:
        raise ValueError(f"Failed to unpack record hash: {exc}") from exc

    version = unpacked[0]
    if version != STRUCT_VERSION:
        raise ValueError(
            f"Unsupported struct version {version!r}; expected {STRUCT_VERSION!r}"
        )

    month_count = unpacked[1]
    if not (0 <= month_count <= MAX_MONTHS):
        raise ValueError(
            f"Invalid month_count {month_count!r}; expected 0 <= month_count <= {MAX_MONTHS}"
        )

    result: list[dict] = []
    for i in range(month_count):
        month_year_int = unpacked[2 + i * 3]
        p95_raw = unpacked[3 + i * 3]
        peak_raw = unpacked[4 + i * 3]
        result.append({
            "label": _decode_month_year(month_year_int),
            "95th": _decode_metric(p95_raw),
            "peak": _decode_metric(peak_raw),
        })

    return result


def _float_to_int(value: float) -> int | float:
    """Convert a float to int when it has no fractional part."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def decode_combined_csv(csv_path: str, output_dir: str | None = None) -> Path:
    """Read a combined CSV, decode each Record Hash, write per-month CSVs.

    Reverses the field-level obfuscation produced by output.py::write_combined_csv.
    Each Record Hash is decoded to per-month metric dicts via decode_record_hash,
    producing one output CSV per unique month (matching the per-month file layout
    of ``write_month_csvs``).

    Output files follow the ``{vco_prefix}.{MM-YYYY}.csv`` naming convention
    (e.g., ``vco116.07-2026.csv``).  The *vco_prefix* is derived from the
    input filename by stripping the ``.combined`` suffix from its stem.

    Edges decoded as sentinel (empty UUID / SENTINEL_HASH) are included in
    every month file.  If the input contains only sentinel edges (no month
    data at all), a single ``{vco_prefix}.decoded.csv`` fallback file is
    written instead.

    Args:
        csv_path:   Path to the combined CSV file (utf-8-sig encoded), containing
                    an 'Edge UUID' column and a 'Record Hash' column.
        output_dir: Directory where per-month CSV files are written.  Defaults
                    to a directory named after the input file's stem inside the
                    input file's parent directory.

    Returns:
        Resolved :class:`~pathlib.Path` of the output directory containing
        the per-month CSV files.

    Raises:
        FileNotFoundError: If csv_path does not exist.
        ValueError:        If required columns are missing or an output path
                           would escape the output directory (path traversal).
    """
    resolved = Path(csv_path).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"No such file: {csv_path}")

    if output_dir is None:
        out_dir = resolved.parent / resolved.stem
    else:
        out_dir = Path(output_dir).resolve()

    out_dir.mkdir(parents=True, exist_ok=True)

    stem = resolved.stem
    vco_prefix = stem.removesuffix(".combined")

    # Read with utf-8-sig to strip BOM from column headers (Pitfall 4)
    with open(resolved, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise ValueError(f"CSV file has no header row: {csv_path!r}")
        required = {"Edge UUID", "Record Hash"}
        missing = required - set(reader.fieldnames)
        if missing:
            raise ValueError(
                f"CSV is missing required columns: {sorted(missing)!r}"
            )
        base_fields = [f for f in reader.fieldnames if f != "Record Hash"]
        out_fields = base_fields + ["Month-Year", "30 Days 95th", "30 Days P95 Peak"]

        month_rows: dict[str, list[dict]] = {}
        sentinel_rows: list[dict] = []

        for row in reader:
            edge_uuid = row.get("Edge UUID", "")
            record_hash = row.get("Record Hash", "")
            base_row = {k: row[k] for k in base_fields}

            try:
                months = decode_record_hash(record_hash, edge_uuid)
            except (ValueError, binascii.Error) as exc:
                warnings.warn(
                    f"Skipping row (Edge UUID={edge_uuid!r}): {exc}",
                    stacklevel=2,
                )
                months = [{"label": "", "95th": float("nan"), "peak": float("nan")}]

            for m in months:
                out_row = base_row.copy()
                out_row["Month-Year"] = m["label"]
                out_row["30 Days 95th"] = "" if math.isnan(m["95th"]) else _float_to_int(m["95th"])
                out_row["30 Days P95 Peak"] = "" if math.isnan(m["peak"]) else _float_to_int(m["peak"])

                if m["label"]:
                    month_rows.setdefault(m["label"], []).append(out_row)
                else:
                    sentinel_rows.append(out_row)

    expected_prefix = str(out_dir.resolve()).rstrip(os.sep) + os.sep

    def _write_csv(file_path: Path, rows: list[dict]) -> None:
        if not str(file_path.resolve()).startswith(expected_prefix):
            raise ValueError(
                f"Output path {file_path!r} would escape the output directory {out_dir!r}"
            )
        with open(file_path, "w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=out_fields)
            writer.writeheader()
            writer.writerows(rows)

    for month_label, rows in sorted(month_rows.items()):
        out_path = out_dir / f"{vco_prefix}.{month_label}.csv"
        _write_csv(out_path, rows + sentinel_rows)

    if not month_rows and sentinel_rows:
        out_path = out_dir / f"{vco_prefix}.decoded.csv"
        _write_csv(out_path, sentinel_rows)

    return out_dir


def extract_plain_zip(zip_path: str, output_dir: str | None = None) -> Path:
    """Extract a plain (unencrypted, unobfuscated) zip archive.

    Args:
        zip_path:   Path to the plain zip file.
        output_dir: Directory where files are extracted.  When ``None``,
                    defaults to the zip file's stem inside its parent directory.

    Returns:
        The resolved output directory path.

    Raises:
        FileNotFoundError: If ``zip_path`` does not exist.
        ValueError:        If a member attempts path traversal.
    """
    resolved = Path(zip_path).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"No such file: {zip_path}")

    if output_dir is None:
        out_path = resolved.parent / resolved.stem
    else:
        out_path = Path(output_dir).resolve()

    out_path.mkdir(parents=True, exist_ok=True)

    expected_prefix = str(out_path.resolve()).rstrip(os.sep) + os.sep
    with zipfile.ZipFile(resolved, "r") as zf:
        for member in zf.infolist():
            if member.filename.startswith("_"):
                continue
            member_path = (out_path / member.filename).resolve()
            if not str(member_path).startswith(expected_prefix):
                raise ValueError(
                    f"Attempted path traversal in archive member: {member.filename!r}"
                )
            zf.extract(member, out_path)

    return out_path


def extract_and_decode_obfuscated(zip_path: str, output_dir: str | None = None) -> Path:
    """Extract a zip containing a combined CSV and decode its Record Hashes.

    Extracts the ``*.combined.csv`` file from the zip into a temporary
    location, then delegates to :func:`decode_combined_csv` to produce
    per-month output CSVs.

    Args:
        zip_path:   Path to the zip file containing a combined CSV.
        output_dir: Directory where decoded per-month CSVs are written.
                    When ``None``, defaults to the zip file's stem inside
                    its parent directory.

    Returns:
        The resolved output directory path.

    Raises:
        FileNotFoundError: If ``zip_path`` does not exist.
        KeyError:          If no ``*.combined.csv`` member is found.
        ValueError:        If a member attempts path traversal.
    """
    resolved = Path(zip_path).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"No such file: {zip_path}")

    if output_dir is None:
        out_path = resolved.parent / resolved.stem
    else:
        out_path = Path(output_dir).resolve()

    out_path.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(resolved, "r") as zf:
        combined_members = [n for n in zf.namelist() if n.endswith(".combined.csv")]
        if not combined_members:
            raise KeyError(
                f"Archive '{zip_path}' has no '*.combined.csv' member."
            )

        expected_prefix = str(out_path.resolve()).rstrip(os.sep) + os.sep
        extracted_csvs: list[Path] = []
        for member_name in combined_members:
            member_path = (out_path / member_name).resolve()
            if not str(member_path).startswith(expected_prefix):
                raise ValueError(
                    f"Attempted path traversal in archive member: {member_name!r}"
                )
            zf.extract(member_name, out_path)
            extracted_csvs.append(member_path)

    final_out = out_path
    for csv_path in extracted_csvs:
        final_out = decode_combined_csv(str(csv_path), str(out_path))
        csv_path.unlink()

    return final_out


def decrypt_archive(zip_path: str, output_dir: str | None = None) -> Path:
    """Decrypt an encrypted metrics archive and extract CSV files.

    Args:
        zip_path:   Path to the encrypted outer zip file.
        output_dir: Directory where CSV files are extracted.  When ``None``,
                    defaults to the zip file's stem (e.g. ``export/`` for
                    ``export.zip``) inside the zip's parent directory.

    Returns:
        The resolved :class:`~pathlib.Path` of the output directory.

    Raises:
        FileNotFoundError:  If ``zip_path`` does not exist on disk.
        zipfile.BadZipFile: If ``zip_path`` or the inner payload is not a
                            valid zip archive.
        KeyError:           If the zip has no ``data.enc`` member.
        InvalidToken:       If ``data.enc`` cannot be decrypted with the
                            embedded key.
        ValueError:         If an archive member attempts path traversal.
    """
    resolved = Path(zip_path).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"No such file: {zip_path}")

    if output_dir is None:
        # Strip the .zip suffix: "export.zip" -> "export/"
        out_path = resolved.parent / resolved.stem
    else:
        out_path = Path(output_dir).resolve()

    with zipfile.ZipFile(resolved, "r") as outer_zf:
        if "data.enc" not in outer_zf.namelist():
            raise KeyError(
                f"Archive '{zip_path}' has no 'data.enc' member. "
                "Is this a valid encrypted metrics archive?"
            )
        encrypted_bytes = outer_zf.read("data.enc")

    decrypted_bytes = Fernet(FERNET_KEY).decrypt(encrypted_bytes)

    out_path.mkdir(parents=True, exist_ok=True)

    expected_prefix = str(out_path.resolve()).rstrip(os.sep) + os.sep
    with zipfile.ZipFile(io.BytesIO(decrypted_bytes), "r") as inner_zf:
        for member in inner_zf.infolist():
            member_path = (out_path / member.filename).resolve()
            if not str(member_path).startswith(expected_prefix):
                raise ValueError(
                    f"Attempted path traversal in archive member: {member.filename!r}"
                )
            inner_zf.extract(member, out_path)

    return out_path


def process_zip(zip_path: str, output_dir: str | None = None) -> Path:
    """Auto-detect a zip's format and extract/decrypt/decode accordingly.

    Args:
        zip_path:   Path to a zip file produced by vco_edge_export.py.
        output_dir: Optional output directory override.

    Returns:
        The resolved output directory path.
    """
    fmt = _detect_zip_format(zip_path)
    if fmt == "encrypted":
        return decrypt_archive(zip_path, output_dir)
    if fmt == "obfuscated":
        return extract_and_decode_obfuscated(zip_path, output_dir)
    return extract_plain_zip(zip_path, output_dir)


_FORMAT_LABELS = {
    "encrypted": "Decrypted",
    "obfuscated": "Decoded",
    "plain": "Extracted",
}


if __name__ == "__main__":
    import argparse as _argparse

    parser = _argparse.ArgumentParser(
        description="Recover metric CSVs from archives produced by vco_edge_export.py.",
    )
    parser.add_argument(
        "input_files",
        nargs="+",
        metavar="INPUT_FILE",
        help="One or more zip files (or legacy: a single combined CSV) to process.",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=None,
        metavar="DIR",
        help=(
            "Output directory. When processing a single zip, all files go here. "
            "When processing multiple zips, each gets a subdirectory named "
            "after its stem."
        ),
    )
    cli_args = parser.parse_args()

    errors = 0
    for input_arg in cli_args.input_files:
        if len(cli_args.input_files) > 1 and cli_args.output_dir:
            out_arg = str(Path(cli_args.output_dir) / Path(input_arg).stem)
        else:
            out_arg = cli_args.output_dir

        try:
            if zipfile.is_zipfile(input_arg):
                fmt = _detect_zip_format(input_arg)
                label = _FORMAT_LABELS[fmt]
                out_dir = process_zip(input_arg, out_arg)
            else:
                label = "Decoded"
                out_dir = decode_combined_csv(input_arg, out_arg)

            csv_files = list(out_dir.glob("*.csv"))
            print(f"{label} {len(csv_files)} files to {out_dir}")
        except FileNotFoundError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            errors += 1
        except KeyError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            errors += 1
        except zipfile.BadZipFile as exc:
            print(f"Error: {input_arg}: {exc}", file=sys.stderr)
            errors += 1
        except InvalidToken:
            print(
                f"Error: {input_arg}: decryption failed — the archive may be "
                f"corrupt or was not produced by this tool.",
                file=sys.stderr,
            )
            errors += 1
        except OSError as exc:
            print(f"Error: {input_arg}: {exc}", file=sys.stderr)
            errors += 1

    if errors:
        sys.exit(1)
