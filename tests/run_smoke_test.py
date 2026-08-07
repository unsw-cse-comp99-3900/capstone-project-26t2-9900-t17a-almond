#!/usr/bin/env python3
"""Run the integrated archive and live-inference Smoke Test."""

from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_full_test import CHECKPOINT_PATH, INFERENCE_SCRIPT, SOURCE_PATH, run_inference


ARCHIVE_NAME = "deepwukong-rtx5060-cu128-experimental.tar"
ARCHIVE_RELATIVE_PATH = (
    Path("baselines") / "deepwukong" / "module_tranning" / ARCHIVE_NAME
)
RUNTIME_ARCHIVE_PATH = PROJECT_ROOT / ARCHIVE_RELATIVE_PATH
EXPECTED_ARCHIVE_SIZE = 4_766_494_208
EXPECTED_ARCHIVE_SHA256 = (
    "0482EA09F89569072427344B1DADA5E72878DF2E7BC99F878F5895B17DAF6B1D"
)


def calculate_sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    """Return an uppercase digest without loading the 4.439 GiB TAR into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def validate_runtime_archive(
    path: Path = RUNTIME_ARCHIVE_PATH,
    progress: Callable[[str], None] | None = None,
) -> list[str]:
    """Return terminal-ready errors when the runtime TAR is absent or incomplete."""
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


def validate_prediction(prediction: dict[str, Any]) -> list[str]:
    """Return validation errors for the minimum live-inference output contract."""
    errors: list[str] = []
    if not str(prediction.get("predicted_label", "")).strip():
        errors.append("predicted_label is missing")

    try:
        probability = float(prediction["vulnerability_probability"])
        if not 0.0 <= probability <= 1.0:
            errors.append("vulnerability_probability is outside the range 0..1")
    except (KeyError, TypeError, ValueError):
        errors.append("vulnerability_probability is missing or invalid")

    for field in ("num_nodes", "num_edges"):
        try:
            if int(prediction[field]) <= 0:
                errors.append(f"{field} is not positive")
        except (KeyError, TypeError, ValueError):
            errors.append(f"{field} is missing or invalid")
    return errors


def missing_inputs() -> list[Path]:
    return [path for path in (SOURCE_PATH, CHECKPOINT_PATH, INFERENCE_SCRIPT) if not path.is_file()]


def main() -> int:
    print(f"Verifying runtime archive: {RUNTIME_ARCHIVE_PATH}", flush=True)
    archive_errors = validate_runtime_archive(
        RUNTIME_ARCHIVE_PATH,
        progress=lambda message: print(message, flush=True),
    )
    if archive_errors:
        print(
            "\n[ERROR] Run Smoke Test stopped: runtime archive verification failed.",
            file=sys.stderr,
        )
        for error in archive_errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Runtime archive verification passed.\n", flush=True)

    missing = missing_inputs()
    if missing:
        print(
            "\n[ERROR] Run Smoke Test stopped: required inference files are missing.",
            file=sys.stderr,
        )
        for path in missing:
            print(f"- {path}", file=sys.stderr)
        return 1

    sample_id = SOURCE_PATH.stem
    print(f"Smoke Test sample: {sample_id}", flush=True)
    print("Running one baseline inference (Joern -> PDG/XFG -> DeepWuKong)...", flush=True)
    with tempfile.TemporaryDirectory(prefix="almond_smoke_test_") as temporary_dir:
        prediction, error = run_inference(SOURCE_PATH, Path(temporary_dir), sample_id)

    if prediction is None:
        print(
            f"\n[ERROR] Run Smoke Test failed: {error or 'baseline inference failed'}",
            file=sys.stderr,
            flush=True,
        )
        return 1

    errors = validate_prediction(prediction)
    if errors:
        print(
            "\n[ERROR] Run Smoke Test failed: the inference output was incomplete:",
            file=sys.stderr,
            flush=True,
        )
        for error in errors:
            print(f"- {error}", file=sys.stderr, flush=True)
        return 1

    print("Smoke Test passed.", flush=True)
    print(f"Predicted label: {prediction['predicted_label']}", flush=True)
    print(f"Vulnerability probability: {float(prediction['vulnerability_probability']):.6f}", flush=True)
    print(f"Graph size: {prediction['num_nodes']} nodes, {prediction['num_edges']} edges", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
