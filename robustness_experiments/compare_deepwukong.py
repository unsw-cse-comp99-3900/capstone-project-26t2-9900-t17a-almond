"""Compare DeepWuKong predictions for original and semantics-preserving variants.

DeepWuKong emits one score per XFG/program slice, whereas Demo B reports a
source-level result.  This module deliberately joins versions by ``sample_id``
and reduces all their XFG scores, so CSV row order and the number of generated
slices cannot affect the comparison.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Iterable

REQUIRED_COLUMNS = {"sample_id", "xfg_id", "vulnerability_probability"}


def read_predictions(path: Path) -> list[dict[str, str]]:
    """Read a normalized DeepWuKong prediction CSV and validate its schema."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - fields
        if missing:
            raise ValueError(f"{path}: missing required columns: {', '.join(sorted(missing))}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"{path}: prediction CSV is empty")
    return rows


def aggregate_xfgs(rows: Iterable[dict[str, str]], reducer: str) -> dict[str, dict[str, object]]:
    """Aggregate all XFG scores belonging to each source-level sample."""
    grouped: dict[str, list[float]] = defaultdict(list)
    labels: dict[str, str] = {}
    for row in rows:
        sample_id = row["sample_id"].strip()
        if not sample_id:
            raise ValueError("sample_id cannot be empty")
        try:
            probability = float(row["vulnerability_probability"])
        except ValueError as exc:
            raise ValueError(f"{sample_id}: invalid vulnerability_probability") from exc
        if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
            raise ValueError(f"{sample_id}: probability must be in [0, 1]")
        grouped[sample_id].append(probability)
        if row.get("true_label", "").strip():
            labels[sample_id] = row["true_label"].strip()

    reduction = max if reducer == "max" else sum
    return {
        sample_id: {
            "probability": reduction(scores) if reducer == "max" else reduction(scores) / len(scores),
            "xfg_count": len(scores),
            "true_label": labels.get(sample_id, ""),
        }
        for sample_id, scores in grouped.items()
    }


def compare(
    original: dict[str, dict[str, object]], perturbed: dict[str, dict[str, object]], threshold: float
) -> list[dict[str, object]]:
    """Return one source-level comparison row per sample present in both inputs."""
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be in [0, 1]")
    only_original = sorted(set(original) - set(perturbed))
    only_perturbed = sorted(set(perturbed) - set(original))
    if only_original or only_perturbed:
        details = []
        if only_original:
            details.append(f"only in original: {', '.join(only_original)}")
        if only_perturbed:
            details.append(f"only in perturbed: {', '.join(only_perturbed)}")
        raise ValueError("prediction inputs are not paired by sample_id (" + "; ".join(details) + ")")
    shared = sorted(original)
    if not shared:
        raise ValueError("no shared sample_id values between original and perturbed predictions")
    rows = []
    for sample_id in shared:
        before, after = original[sample_id], perturbed[sample_id]
        before_p, after_p = float(before["probability"]), float(after["probability"])
        before_label, after_label = int(before_p >= threshold), int(after_p >= threshold)
        rows.append({
            "sample_id": sample_id,
            "true_label": before["true_label"] or after["true_label"],
            "original_probability": f"{before_p:.6f}",
            "perturbed_probability": f"{after_p:.6f}",
            "probability_delta": f"{after_p - before_p:+.6f}",
            "original_label": before_label,
            "perturbed_label": after_label,
            "prediction_flipped": int(before_label != after_label),
            "original_xfg_count": before["xfg_count"],
            "perturbed_xfg_count": after["xfg_count"],
        })
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, rows: list[dict[str, object]], reducer: str, threshold: float) -> None:
    flips = sum(int(row["prediction_flipped"]) for row in rows)
    mean_delta = sum(float(row["probability_delta"]) for row in rows) / len(rows)
    path.write_text(
        "# DeepWuKong robustness comparison\n\n"
        f"- Samples compared: {len(rows)}\n"
        f"- XFG reducer: `{reducer}`\n"
        f"- Vulnerability threshold: {threshold:.2f}\n"
        f"- Prediction flips: {flips} ({flips / len(rows):.1%})\n"
        f"- Mean probability delta (perturbed − original): {mean_delta:+.6f}\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare DeepWuKong original/perturbed XFG predictions.")
    parser.add_argument("--original", type=Path, required=True, help="Normalized original-predictions CSV")
    parser.add_argument("--perturbed", type=Path, required=True, help="Normalized perturbed-predictions CSV")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--reducer", choices=("max", "mean"), default="max",
                        help="How XFG scores become a source-level score (default: max).")
    args = parser.parse_args()

    original = aggregate_xfgs(read_predictions(args.original), args.reducer)
    perturbed = aggregate_xfgs(read_predictions(args.perturbed), args.reducer)
    rows = compare(original, perturbed, args.threshold)
    write_csv(args.output_dir / "baseline_comparison.csv", rows)
    write_summary(args.output_dir / "baseline_comparison.txt", rows, args.reducer, args.threshold)


if __name__ == "__main__":
    main()
