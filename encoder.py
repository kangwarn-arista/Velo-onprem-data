"""Record Hash encoder for field-level obfuscation mode (OBFUSCATED=1).

Packs per-month bandwidth metrics into a fixed-length 344-character Record Hash
using binary struct packing, XOR obfuscation with Edge UUID, and base64 encoding.

Encoding pipeline:
  1. Parse each month label into uint16: (year - 2000) << 4 | month, or 0 for "last30d"
  2. Replace NaN metric values with -1.0 sentinel (math.isnan check)
  3. Pack into STRUCT_FORMAT: version(H), month_count(B), 12 slots of (month_year H, 95th d, peak d),
     unused slots zeroed (month_year=0, metrics=-1.0), then 37x padding
  4. Derive XOR key: SHA-256(edge_uuid.encode('utf-8')).digest() repeated 8x to 256 bytes
  5. XOR packed bytes with key
  6. base64.b64encode result, decode to ascii string

Security note: This is obfuscation-grade (reversible by anyone with the UUID), NOT security-grade.
Uses only Python stdlib: struct, base64, hashlib, math.
"""

import base64
import hashlib
import math
import struct

STRUCT_VERSION: int = 1
STRUCT_FORMAT: str = "!HB" + "Hdd" * 12 + "37x"
MAX_MONTHS: int = 12

# Sentinel for edges with empty/missing UUID — all-zeros 256 bytes → 344-char base64
SENTINEL_HASH: str = base64.b64encode(b"\x00" * 256).decode("ascii")


def _encode_month_year(label: str) -> int:
    """Encode a month label to a uint16 value.

    "last30d"  → 0
    "MM-YYYY"  → (year - 2000) << 4 | month
    """
    if label == "last30d":
        return 0
    month_str, year_str = label.split("-")
    month = int(month_str)
    year = int(year_str)
    if not (1 <= month <= 12):
        raise ValueError(
            f"Invalid month {month!r} in label {label!r}; expected 1-12"
        )
    return ((year - 2000) << 4) | month


def _derive_xor_key(uuid_str: str) -> bytes:
    """Derive a 256-byte XOR key from SHA-256(uuid_str).

    SHA-256 produces 32 bytes; repeated 8 times to reach 256 bytes.
    """
    digest = hashlib.sha256(uuid_str.encode("utf-8")).digest()
    return digest * 8


def encode_record_hash(months_data: list[dict], edge_uuid: str) -> str:
    """Encode bandwidth metrics into a 344-character Record Hash.

    Args:
        months_data: List of dicts with keys "label", "95th", "peak".
                     Max 12 entries. Label format: "MM-YYYY" or "last30d".
        edge_uuid:   Edge UUID string for XOR key derivation.
                     If empty, None, or whitespace → returns SENTINEL_HASH.

    Returns:
        344-character base64-encoded obfuscated string.

    Raises:
        ValueError: If len(months_data) > MAX_MONTHS.
    """
    # Guard: missing/empty/whitespace/NaN UUID → return sentinel
    if edge_uuid is None:
        return SENTINEL_HASH
    try:
        if math.isnan(float(edge_uuid)):
            return SENTINEL_HASH
    except (TypeError, ValueError):
        pass  # non-numeric string — proceed normally
    if not str(edge_uuid).strip():
        return SENTINEL_HASH

    if len(months_data) > MAX_MONTHS:
        raise ValueError(
            f"months_data has {len(months_data)} entries; MAX_MONTHS is {MAX_MONTHS}"
        )

    # Build struct args: version, month_count, then 12 month-slots
    args: list = [STRUCT_VERSION, len(months_data)]

    for i in range(MAX_MONTHS):
        if i < len(months_data):
            entry = months_data[i]
            month_year = _encode_month_year(entry["label"])
            p95 = float(entry["95th"])
            peak = float(entry["peak"])
            # Replace NaN with sentinel -1.0 (NaN is ambiguous on decode)
            if math.isnan(p95):
                p95 = -1.0
            if math.isnan(peak):
                peak = -1.0
        else:
            # Unused slot: zeroed month_year, sentinel metrics
            month_year = 0
            p95 = -1.0
            peak = -1.0

        args.extend([month_year, p95, peak])

    packed = struct.pack(STRUCT_FORMAT, *args)
    xor_key = _derive_xor_key(str(edge_uuid))
    obfuscated = bytes(a ^ b for a, b in zip(packed, xor_key))
    return base64.b64encode(obfuscated).decode("ascii")
