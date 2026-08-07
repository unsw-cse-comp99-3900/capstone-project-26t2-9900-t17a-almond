#!/usr/bin/env python3
"""Verify the separately delivered DeepWuKong Docker runtime archive."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_NAME = "deepwukong-rtx5060-cu128-experimental.tar"
ARCHIVE_RELATIVE_PATH = (
    Path("baselines") / "deepwukong" / "module_tranning" / ARCHIVE_NAME
)
DEFAULT_ARCHIVE_PATH = PROJECT_ROOT / ARCHIVE_RELATIVE_PATH
EXPECTED_ARCHIVE_SIZE = 4_766_494_208
EXPECTED_ARCHIVE_SHA256 = (
    "0482EA09F89569072427344B1DADA5E72878DF2E7BC99F878F5895B17DAF6B1D"
)


def calculate_sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    """Return an uppercase SHA-256 digest without loading the TAR into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def validate_runtime_archive(
    path: Path = DEFAULT_ARCHIVE_PATH,
    progress: Callable[[str], None] | None = None,
) -> list[str]:
    """Return actionable errors when the runtime TAR is absent or incomplete."""
    if not path.is_file():
        return [
            f"runtime archive is missing: {path}",
            "download it from the documented UNSW OneDrive folder and save it "
            f"as {ARCHIVE_RELATIVE_PATH}",
        ]

    actual_size = path.stat().st_size
    if actual_size != EXPECTED_ARCHIVE_SIZE:
        return [
            "runtime archive size mismatch: "
            f"expected {EXPECTED_ARCHIVE_SIZE:,} bytes, found {actual_size:,} bytes",
            "delete the incomplete file and download it again before running Docker",
        ]

    if progress is not None:
        progress(
            f"Archive size is correct ({actual_size:,} bytes); calculating SHA-256..."
        )
    actual_sha256 = calculate_sha256(path)
    if actual_sha256 != EXPECTED_ARCHIVE_SHA256:
        return [
            "runtime archive SHA-256 mismatch: "
            f"expected {EXPECTED_ARCHIVE_SHA256}, found {actual_sha256}",
            "do not load this file; delete it and download the verified archive again",
        ]
    if progress is not None:
        progress(f"Archive SHA-256 is correct ({actual_sha256}).")
    return []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check the DeepWuKong runtime TAR size and SHA-256."
    )
    parser.add_argument(
        "archive",
        nargs="?",
        type=Path,
        default=DEFAULT_ARCHIVE_PATH,
        help=f"archive path (default: {ARCHIVE_RELATIVE_PATH})",
    )
    args = parser.parse_args()
    archive = args.archive.resolve()
    print(f"Runtime archive: {archive}", flush=True)
    errors = validate_runtime_archive(archive, progress=lambda message: print(message, flush=True))
    if errors:
        print("Runtime archive verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"SHA-256: {EXPECTED_ARCHIVE_SHA256}")
    print("Runtime archive verification passed: the download is complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
