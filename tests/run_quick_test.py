#!/usr/bin/env python3
"""Run one live DeepWuKong inference as a lightweight pipeline smoke test."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_full_test import CHECKPOINT_PATH, INFERENCE_SCRIPT, SOURCE_PATH, run_inference
from scripts.verify_runtime_archive import DEFAULT_ARCHIVE_PATH, validate_runtime_archive


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
    print(f"Verifying runtime archive: {DEFAULT_ARCHIVE_PATH}", flush=True)
    archive_errors = validate_runtime_archive(
        DEFAULT_ARCHIVE_PATH,
        progress=lambda message: print(message, flush=True),
    )
    if archive_errors:
        print("Quick test cannot start because the runtime download is incomplete:", file=sys.stderr)
        for error in archive_errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Runtime archive verification passed.\n", flush=True)

    missing = missing_inputs()
    if missing:
        print("Quick test cannot start because required files are missing:", file=sys.stderr)
        for path in missing:
            print(f"- {path}", file=sys.stderr)
        return 1

    sample_id = SOURCE_PATH.stem
    print(f"Quick test: {sample_id}", flush=True)
    print("Running one baseline inference (Joern -> PDG/XFG -> DeepWuKong)...", flush=True)
    with tempfile.TemporaryDirectory(prefix="almond_quick_test_") as temporary_dir:
        prediction, error = run_inference(SOURCE_PATH, Path(temporary_dir), sample_id)

    if prediction is None:
        print(f"Quick test failed: {error or 'baseline inference failed'}", file=sys.stderr, flush=True)
        return 1

    errors = validate_prediction(prediction)
    if errors:
        print("Quick test failed: the inference output was incomplete:", file=sys.stderr, flush=True)
        for error in errors:
            print(f"- {error}", file=sys.stderr, flush=True)
        return 1

    print("Quick test passed.", flush=True)
    print(f"Predicted label: {prediction['predicted_label']}", flush=True)
    print(f"Vulnerability probability: {float(prediction['vulnerability_probability']):.6f}", flush=True)
    print(f"Graph size: {prediction['num_nodes']} nodes, {prediction['num_edges']} edges", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
