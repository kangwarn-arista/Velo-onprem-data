"""Standalone offline tool for recovering metric CSVs from encrypted archives.

This script is fully self-contained: it has no imports from the main project
(crypto.py, output.py, etc.).  It embeds the Fernet key directly and only
requires stdlib plus the ``cryptography`` package.

Usage:
    python decrypt_metrics.py <input-path> [output-dir]

Args:
    input-path  Path to either:
                  - an encrypted zip file (Fernet, OBFUSCATED=2) — auto-detected
                    via zipfile.is_zipfile(); OR
                  - a combined CSV file (field-level, OBFUSCATED=1).
    output-dir  Optional directory where output files are written.
                Defaults to the same directory as the input file (for CSVs)
                or a directory named after the zip stem (for archives).

Archive format (produced by output.py::create_encrypted_archive):
    outer.zip
    ├── data.enc          Fernet-encrypted inner zip bytes
    └── _metadata.json    (optional) archive metadata

    inner.zip (after decryption)
    └── *.csv             Original CSV files with metric data

Combined CSV format (produced by output.py::write_combined_csv):
    Single CSV with one row per edge, containing a Record Hash column that
    encodes per-month metric data (Month-Year, 30 Days 95th, 30 Days P95 Peak).
    Decoded output replaces Record Hash with those three columns, producing
    one output row per edge per active month.
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


def _detect_format(path: str) -> str:
    """Return 'fernet' if path is a zip archive, else 'combined_csv'.

    Raises:
        FileNotFoundError: If *path* does not exist on disk.
    """
    if not Path(path).exists():
        raise FileNotFoundError(f"No such file: {path}")
    if zipfile.is_zipfile(path):
        return "fernet"
    return "combined_csv"


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


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(
            "Usage: python decrypt_metrics.py <input-path> [output-dir]",
            file=sys.stderr,
        )
        sys.exit(1)

    zip_arg = args[0]
    out_arg = args[1] if len(args) > 1 else None

    fmt = _detect_format(zip_arg)
    try:
        if fmt == "fernet":
            out_dir = decrypt_archive(zip_arg, out_arg)
            csv_files = list(out_dir.glob("*.csv"))
            print(f"Decrypted {len(csv_files)} files to {out_dir}")
        else:
            out_dir = decode_combined_csv(zip_arg, out_arg)
            csv_files = list(out_dir.glob("*.csv"))
            print(f"Decoded {len(csv_files)} files to {out_dir}")
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except zipfile.BadZipFile:
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
    except OSError as exc:
        print(f"Error: cannot create output directory — {exc}", file=sys.stderr)
        sys.exit(1)
