"""Standalone offline tool for recovering metric CSVs from encrypted archives.

This script is fully self-contained: it has no imports from the main project
(crypto.py, output.py, etc.).  It embeds the Fernet key directly and only
requires stdlib plus the ``cryptography`` package.

Usage:
    python decrypt_metrics.py <encrypted-zip> [output-dir]

Args:
    encrypted-zip   Path to the encrypted zip file produced by the main export
                    pipeline.
    output-dir      Optional directory where decrypted CSV files are written.
                    Defaults to a directory named after the zip file (without
                    the .zip suffix) in the same parent folder.

Archive format (produced by output.py::create_encrypted_archive):
    outer.zip
    ├── data.enc          Fernet-encrypted inner zip bytes
    └── _metadata.json    (optional) archive metadata

    inner.zip (after decryption)
    └── *.csv             Original CSV files with metric data
"""

import io
import os
import sys
import zipfile
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

# Embedded key — intentionally duplicated from crypto.py.
# This is obfuscation-grade protection; the key is in plaintext by design so
# that this script can operate fully offline without importing from the main
# project.
FERNET_KEY = b"YVrZTl2xyS7QHyqxwaP2xd5gwMUjoctoo8RKUwjNi-8="


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

    with zipfile.ZipFile(io.BytesIO(decrypted_bytes), "r") as inner_zf:
        for member in inner_zf.infolist():
            member_path = (out_path / member.filename).resolve()
            if not str(member_path).startswith(str(out_path.resolve()) + os.sep):
                raise ValueError(
                    f"Attempted path traversal in archive member: {member.filename!r}"
                )
            inner_zf.extract(member, out_path)

    return out_path


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(
            "Usage: python decrypt_metrics.py <encrypted-zip> [output-dir]",
            file=sys.stderr,
        )
        sys.exit(1)

    zip_arg = args[0]
    out_arg = args[1] if len(args) > 1 else None

    try:
        out_dir = decrypt_archive(zip_arg, out_arg)
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

    csv_files = list(out_dir.glob("*.csv"))
    print(f"Decrypted {len(csv_files)} files to {out_dir}")
