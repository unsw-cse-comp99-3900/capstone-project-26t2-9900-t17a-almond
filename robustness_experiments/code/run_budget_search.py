from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from robustness_experiments.code.code_perturbations import (
    OPERATORS,
    PROJECT_ROOT,
    PerturbationResult,
    dataset_slug,
    discover_sources,
    generation_status,
    normalize_counts,
    safe_stem,
)


@dataclass(frozen=True)
class WinnerXFG:
    category: str
    key_line: int
    vulnerability_probability: float


@dataclass(frozen=True)
class TargetCoverage:
    """Coverage of a baseline target after Joern rebuilds a source variant."""

    status: str
    verified: bool | str
    mapped_source_lines: tuple[int, ...]
    variant_target: WinnerXFG | None
    variant_winner: WinnerXFG | None
    winner_changed: bool | str
    target_probability_decreased: bool | str


CSV_FIELDS = [
    "sample_id",
    "source_file",
    "action",
    "target_mode",
    "winner_xfg_category",
    "winner_xfg_key_line",
    "winner_xfg_probability",
    "target_rank",
    "target_xfg_category",
    "target_xfg_key_line",
    "target_xfg_probability",
    "target_window_lines",
    "targeted_source_lines",
    "mapped_target_source_lines",
    "target_coverage_verified",
    "target_coverage_status",
    "variant_winner_xfg_category",
    "variant_winner_xfg_key_line",
    "variant_winner_xfg_probability",
    "target_xfg_probability_after",
    "target_xfg_probability_delta",
    "winner_xfg_changed",
    "target_probability_decreased",
    "count",
    "applied_count",
    "generation_status",
    "run_status",
    "flipped",
    "flip_direction",
    "attack_target_label",
    "baseline_eligible",
    "attack_success",
    "base_label",
    "variant_label",
    "base_probability",
    "variant_probability",
    "delta_probability",
    "base_nodes",
    "variant_nodes",
    "delta_nodes",
    "base_edges",
    "variant_edges",
    "delta_edges",
    "baseline_run_dir",
    "variant_run_dir",
    "variant_artifact_id",
    "variant_file",
    "notes",
    "error",
]

BASELINE_ELIGIBILITY_FIELDS = [
    "sample_id",
    "source_file",
    "baseline_status",
    "base_label",
    "base_probability",
    "baseline_eligible",
    "eligibility_reason",
    "baseline_run_dir",
    "winner_xfg_category",
    "winner_xfg_key_line",
    "winner_xfg_probability",
    "winner_xfg_candidates",
    "error",
]

BASELINE_PREDICTION_FIELDS = [
    "sample_id",
    "source_file",
    "function",
    "status",
    "probability",
    "predicted_label",
    "pdg_nodes",
    "pdg_edges",
    "xfg_count",
    "runtime_ms",
    "key_line_counts",
    "error",
]

BASELINE_SUMMARY_FIELDS = ["sample", "function", "status", "label", "prob", "nodes", "edges", "xfg_count"]

PERTURBATION_RESULT_FIELDS = [
    "sample_id",
    "action",
    "strategy",
    "seed",
    "requested_count",
    "applied_count",
    "valid",
    "baseline_nodes",
    "baseline_edges",
    "perturbed_nodes",
    "perturbed_edges",
    "delta_nodes",
    "delta_edges",
    "baseline_xfg_count",
    "perturbed_xfg_count",
    "baseline_probability",
    "perturbed_probability",
    "delta_probability",
    "baseline_label",
    "perturbed_label",
    "flipped",
    "flip_direction",
    "attack_target_label",
    "baseline_eligible",
    "attack_success",
    "runtime_ms",
    "operations",
    "validation_errors",
    "error",
    "variant_artifact_id",
    "target_mode",
    "winner_xfg_category",
    "winner_xfg_key_line",
    "winner_xfg_probability",
    "target_rank",
    "target_xfg_category",
    "target_xfg_key_line",
    "target_xfg_probability",
    "target_window_lines",
    "targeted_source_lines",
    "mapped_target_source_lines",
    "target_coverage_verified",
    "target_coverage_status",
    "variant_winner_xfg_category",
    "variant_winner_xfg_key_line",
    "variant_winner_xfg_probability",
    "target_xfg_probability_after",
    "target_xfg_probability_delta",
    "winner_xfg_changed",
    "target_probability_decreased",
]

COMPARISON_FIELDS = [
    "sample",
    "action",
    "function",
    "status",
    "base_label",
    "variant_label",
    "flipped",
    "flip_direction",
    "attack_target_label",
    "baseline_eligible",
    "attack_success",
    "base_prob",
    "variant_prob",
    "delta_prob",
    "base_nodes",
    "variant_nodes",
    "delta_nodes",
    "base_edges",
    "variant_edges",
    "delta_edges",
    "base_xfg_count",
    "variant_xfg_count",
    "error",
    "target_mode",
    "winner_xfg_category",
    "winner_xfg_key_line",
    "winner_xfg_probability",
    "target_rank",
    "target_xfg_category",
    "target_xfg_key_line",
    "target_xfg_probability",
    "target_window_lines",
    "targeted_source_lines",
    "mapped_target_source_lines",
    "target_coverage_verified",
    "target_coverage_status",
    "variant_winner_xfg_category",
    "variant_winner_xfg_key_line",
    "variant_winner_xfg_probability",
    "target_xfg_probability_after",
    "target_xfg_probability_delta",
    "winner_xfg_changed",
    "target_probability_decreased",
]

ACTION_SUMMARY_FIELDS = [
    "action",
    "count",
    "flips",
    "attack_successes",
    "reverse_flips",
    "avg_delta_prob",
    "min_delta_prob",
    "max_delta_prob",
    "avg_delta_nodes",
    "avg_delta_edges",
    "attempted",
    "failed",
]

ACTION_METRIC_FIELDS = [
    "action",
    "attempted",
    "successful",
    "failed",
    "flips",
    "attack_successes",
    "reverse_flips",
    "mean_delta_probability",
    "mean_absolute_delta_probability",
    "max_absolute_delta_probability",
    "mean_runtime_ms",
]


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_deepwukong(
    source_file: Path,
    output_dir: Path,
    deepwukong_root: Path,
    config_path: Path,
    timeout_seconds: int,
) -> tuple[bool, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(deepwukong_root / "scripts" / "run_demo_pipeline.py"),
        "--input",
        str(source_file),
        "--output",
        str(output_dir),
        "--config",
        str(config_path),
        "--no-timestamp-output",
    ]
    (output_dir / "host_command.txt").write_text(" ".join(f'"{part}"' if " " in part else part for part in cmd) + "\n", encoding="utf-8")
    proc = subprocess.run(
        cmd,
        cwd=str(deepwukong_root),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout_seconds,
    )
    (output_dir / "host_stdout.log").write_text(proc.stdout, encoding="utf-8")
    (output_dir / "host_stderr.log").write_text(proc.stderr, encoding="utf-8")
    if proc.returncode != 0:
        detail = (proc.stderr.strip() or proc.stdout.strip())[-4000:]
        return False, detail
    prediction_path = output_dir / "predictions.json"
    if not prediction_path.is_file():
        return False, f"missing predictions.json under {output_dir}"
    return True, ""


def prediction_from_run(run_dir: Path) -> dict[str, Any] | None:
    prediction_path = run_dir / "predictions.json"
    if not prediction_path.is_file():
        return None
    payload = read_json(prediction_path)
    return payload.get("prediction")


def winner_xfgs_from_run(run_dir: Path) -> list[WinnerXFG]:
    """Return all scored XFGs ordered by descending vulnerability probability."""
    prediction_path = run_dir / "predictions.json"
    if not prediction_path.is_file():
        return []

    payload = read_json(prediction_path)
    details = payload.get("details")
    if not isinstance(details, dict):
        return []
    features = details.get("features")
    if not isinstance(features, dict):
        return []
    xfg = features.get("xfg")
    if not isinstance(xfg, dict):
        return []
    predictions = xfg.get("xfg_predictions")
    if not isinstance(predictions, list):
        return []

    candidates: list[WinnerXFG] = []
    for item in predictions:
        if not isinstance(item, dict):
            continue
        key_line = row_int(item.get("key_line"))
        probability = row_number(item.get("vulnerability_probability"))
        if key_line is None or probability is None:
            continue
        candidates.append(
            WinnerXFG(
                category=str(item.get("category") or "unknown"),
                key_line=key_line,
                vulnerability_probability=probability,
            )
        )
    if not candidates:
        return []

    return sorted(
        candidates,
        key=lambda item: (-item.vulnerability_probability, item.key_line, item.category),
    )


def winner_xfg_from_run(run_dir: Path) -> WinnerXFG | None:
    """Return the maximum-probability XFG for backwards-compatible reporting."""
    candidates = winner_xfgs_from_run(run_dir)
    return candidates[0] if candidates else None


def distinct_source_targets(candidates: list[WinnerXFG], top_k: int) -> list[WinnerXFG]:
    """Keep the strongest XFG at each source line so source variants are distinct."""
    selected: list[WinnerXFG] = []
    seen_lines: set[int] = set()
    for candidate in candidates:
        if candidate.key_line in seen_lines:
            continue
        selected.append(candidate)
        seen_lines.add(candidate.key_line)
        if len(selected) == top_k:
            break
    return selected


def row_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def row_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def compare_predictions(base: dict[str, Any] | None, variant: dict[str, Any] | None) -> dict[str, Any]:
    if not base or not variant:
        return {
            "flipped": "",
            "flip_direction": "",
            "attack_target_label": 0,
            "attack_success": "",
            "base_label": "",
            "variant_label": "",
            "base_probability": "",
            "variant_probability": "",
            "delta_probability": "",
            "base_nodes": "",
            "variant_nodes": "",
            "delta_nodes": "",
            "base_edges": "",
            "variant_edges": "",
            "delta_edges": "",
        }

    base_label = row_int(base.get("predicted_label"))
    variant_label = row_int(variant.get("predicted_label"))
    base_probability = row_number(base.get("vulnerability_probability"))
    variant_probability = row_number(variant.get("vulnerability_probability"))
    base_nodes = row_int(base.get("num_nodes"))
    variant_nodes = row_int(variant.get("num_nodes"))
    base_edges = row_int(base.get("num_edges"))
    variant_edges = row_int(variant.get("num_edges"))
    flip_direction = (
        f"{base_label}->{variant_label}"
        if base_label is not None and variant_label is not None and base_label != variant_label
        else ""
    )
    return {
        "flipped": bool(base_label != variant_label) if base_label is not None and variant_label is not None else "",
        "flip_direction": flip_direction,
        "attack_target_label": 0,
        "attack_success": bool(base_label == 1 and variant_label == 0)
        if base_label is not None and variant_label is not None
        else "",
        "base_label": base_label if base_label is not None else "",
        "variant_label": variant_label if variant_label is not None else "",
        "base_probability": base_probability if base_probability is not None else "",
        "variant_probability": variant_probability if variant_probability is not None else "",
        "delta_probability": (variant_probability - base_probability) if base_probability is not None and variant_probability is not None else "",
        "base_nodes": base_nodes if base_nodes is not None else "",
        "variant_nodes": variant_nodes if variant_nodes is not None else "",
        "delta_nodes": (variant_nodes - base_nodes) if base_nodes is not None and variant_nodes is not None else "",
        "base_edges": base_edges if base_edges is not None else "",
        "variant_edges": variant_edges if variant_edges is not None else "",
        "delta_edges": (variant_edges - base_edges) if base_edges is not None and variant_edges is not None else "",
    }


def source_window_lines(source_text: str, key_line: int, radius: int) -> tuple[int, ...]:
    """Return a clipped source-line window around an XFG key line."""
    line_count = max(1, len(source_text.splitlines()))
    start = max(1, key_line - radius)
    end = min(line_count, key_line + radius)
    return tuple(range(start, end + 1))


def map_source_lines(original: str, variant: str, source_lines: tuple[int, ...]) -> tuple[int, ...]:
    """Map original line numbers through a source edit using stable equal blocks."""
    before = original.splitlines()
    after = variant.splitlines()
    if not before or not after:
        return ()

    mapping: dict[int, int] = {}
    matcher = SequenceMatcher(a=before, b=after, autojunk=False)
    for tag, before_start, before_end, after_start, after_end in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(before_end - before_start):
                mapping[before_start + offset + 1] = after_start + offset + 1
        elif tag == "replace" and after_start < after_end:
            before_width = max(1, before_end - before_start)
            after_width = after_end - after_start
            for offset in range(before_width):
                mapped_offset = min(after_width - 1, offset * after_width // before_width)
                mapping[before_start + offset + 1] = after_start + mapped_offset + 1
        elif tag == "delete":
            fallback = min(max(1, after_start + 1), len(after))
            for index in range(before_start, before_end):
                mapping[index + 1] = fallback

    mapped: list[int] = []
    for line in source_lines:
        mapped_line = mapping.get(line, min(max(1, line), len(after)))
        if mapped_line not in mapped:
            mapped.append(mapped_line)
    return tuple(mapped)


def nearest_xfg(
    candidates: list[WinnerXFG], category: str, anchor_lines: tuple[int, ...]
) -> WinnerXFG | None:
    """Find the closest rebuilt XFG in the same category as the baseline target."""
    same_category = [candidate for candidate in candidates if candidate.category == category]
    if not same_category or not anchor_lines:
        return None
    return min(
        same_category,
        key=lambda candidate: (
            min(abs(candidate.key_line - line) for line in anchor_lines),
            -candidate.vulnerability_probability,
            candidate.key_line,
        ),
    )


def target_coverage_from_run(
    original: str,
    variant: str,
    baseline_winner: WinnerXFG | None,
    target: WinnerXFG | None,
    selected_source_lines: tuple[int, ...],
    variant_run_dir: Path | None,
    radius: int,
) -> TargetCoverage:
    """Verify that the rebuilt graph still has an XFG around the edited target window."""
    if target is None:
        return TargetCoverage("not_targeted", "", (), None, None, "", "")
    if variant_run_dir is None:
        return TargetCoverage("not_run", "", (), None, None, "", "")

    candidates = winner_xfgs_from_run(variant_run_dir)
    variant_winner = candidates[0] if candidates else None
    anchor_lines = tuple(dict.fromkeys((target.key_line, *selected_source_lines)))
    mapped_lines = map_source_lines(original, variant, anchor_lines)
    variant_target = nearest_xfg(candidates, target.category, mapped_lines)
    covered = bool(
        variant_target is not None
        and any(abs(variant_target.key_line - line) <= radius for line in mapped_lines)
    )

    mapped_winner_line = (
        map_source_lines(original, variant, (baseline_winner.key_line,))[0]
        if baseline_winner is not None
        else None
    )
    winner_changed: bool | str = ""
    if baseline_winner is not None:
        winner_changed = bool(
            variant_winner is None
            or mapped_winner_line is None
            or variant_winner.category != baseline_winner.category
            or abs(variant_winner.key_line - mapped_winner_line) > radius
        )

    target_probability_decreased: bool | str = ""
    if variant_target is not None:
        target_probability_decreased = variant_target.vulnerability_probability < target.vulnerability_probability

    return TargetCoverage(
        status="covered" if covered else "target_not_covered",
        verified=covered,
        mapped_source_lines=mapped_lines,
        variant_target=variant_target,
        variant_winner=variant_winner,
        winner_changed=winner_changed,
        target_probability_decreased=target_probability_decreased,
    )


def variant_name_for(row: dict[str, Any]) -> str:
    target_rank = row.get("target_rank")
    target_suffix = f"__t{target_rank}" if target_rank not in {None, "", 0} else ""
    return f"{row['sample_id']}__{row['action']}{target_suffix}__c{row['count']}"


def compact_sample_id(source: Path, max_length: int = 36) -> str:
    """Keep nested re-targeting paths under the Windows path-length limit."""
    return compact_path_component(safe_stem(source), max_length=max_length)


def compact_path_component(value: str, max_length: int = 32) -> str:
    """Return a deterministic short filesystem component while retaining uniqueness."""
    if len(value) <= max_length:
        return value
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    prefix_length = max_length - len(digest) - 2
    return f"{value[:prefix_length]}__{digest}"


def variant_artifact_id_for(row: dict[str, Any]) -> str:
    """Use a short artifact id for deep nested source-to-graph pipeline paths."""
    existing = row.get("variant_artifact_id")
    return str(existing) if existing else compact_path_component(variant_name_for(row))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] = CSV_FIELDS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_info(run_dir_value: Any) -> dict[str, Any]:
    """Load report fields from a DeepWuKong predictions.json directory."""
    empty = {
        "function": "unknown",
        "runtime_ms": "",
        "xfg_count": "",
        "key_line_counts": "",
    }
    if not run_dir_value:
        return empty

    prediction_path = Path(str(run_dir_value)) / "predictions.json"
    if not prediction_path.is_file():
        return empty
    try:
        payload = read_json(prediction_path)
    except (OSError, json.JSONDecodeError):
        return empty

    prediction = payload.get("prediction") if isinstance(payload.get("prediction"), dict) else {}
    details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
    features = details.get("features") if isinstance(details.get("features"), dict) else {}
    xfg = features.get("xfg") if isinstance(features.get("xfg"), dict) else {}
    return {
        "function": str(prediction.get("function_name") or "unknown"),
        "runtime_ms": details.get("runtime_ms", ""),
        "xfg_count": xfg.get("xfg_count", ""),
        "key_line_counts": json.dumps(xfg.get("key_line_counts", {}), ensure_ascii=False) if xfg else "",
    }


def is_scored_result(row: dict[str, Any]) -> bool:
    if row.get("run_status") not in {"ran", "run_partial"}:
        return False
    required = ("base_probability", "variant_probability", "delta_probability", "delta_nodes", "delta_edges")
    return all(row_number(row.get(field)) is not None for field in required)


def mean(values: list[float]) -> float | str:
    return sum(values) / len(values) if values else ""


def report_dataset_name(input_path: Path, sources: list[Path]) -> str:
    parts = {part.lower() for part in input_path.parts}
    for kind in ("cwe119", "cvefixes", "devign"):
        if kind not in parts:
            continue
        splits = {source.parent.name.lower() for source in sources}
        if len(splits) == 1 and next(iter(splits)) in {"vulnerable", "fixed"}:
            return f"{kind}_{next(iter(splits))}"
        return kind
    return dataset_slug(input_path)


def copy_prediction_json(source_run_dir: Any, destination: Path) -> None:
    if not source_run_dir:
        return
    source = Path(str(source_run_dir)) / "predictions.json"
    if not source.is_file():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def write_report_readme(
    output_root: Path,
    dataset: str,
    samples: int,
    eligible_samples: int,
    baseline_non_vulnerable: int,
    attempts: int,
    successful: int,
    attack_successes: int,
    label_flips: int,
    target_mode: str,
) -> None:
    report = f"""# {output_root.name}

This is an automatically generated DeepWuKong code-perturbation report. It uses
the same report layout as the archived `run_20260717_code_*_round1` experiments.

## Result

- Dataset: `{dataset}`
- Target mode: `{target_mode}`
- Samples: {samples}
- Eligible baseline-positive samples: {eligible_samples}
- Baseline non-vulnerable predictions skipped: {baseline_non_vulnerable}
- Perturbation attempts: {attempts}
- Successful runs: {successful}
- Attack successes (`1 -> 0` only): {attack_successes}
- All label flips (audit only): {label_flips}

## Contents

- `baseline_predictions.csv` and `baseline_summary.csv`: one baseline result per sample.
- `baseline_eligibility.csv`: baseline-positive eligibility and skipped baseline predictions.
- `perturbation_results.csv`: all source perturbation attempts, including winner-XFG metadata.
- `prediction_comparison.csv`: baseline-versus-variant rows used by `dashboard.html`.
- `action_summary.csv` and `action_metrics.csv`: per-action aggregates.
- `summary.json` and `details.json`: machine-readable report metadata and row details.
- `runs/baseline/*.json` and `runs/perturbed/*.json`: flattened DeepWuKong predictions.
- `budget_search.csv` and `budget_search.json`: original minimal-flip-search records.
"""
    (output_root / "README.md").write_text(report, encoding="utf-8")


def write_standard_report(
    output_root: Path,
    rows: list[dict[str, Any]],
    baseline_records: list[dict[str, Any]],
    input_path: Path,
    sources: list[Path],
    target_mode: str,
    counts: list[int],
    actions: list[str],
    winner_xfg_top_k: int,
    target_window_radius: int,
) -> str:
    """Write the archived code-run report layout without rerunning DeepWuKong."""
    dataset = report_dataset_name(input_path, sources)
    baseline_info = {
        str(record["sample_id"]): run_info(record.get("baseline_run_dir")) for record in baseline_records
    }
    baseline_rows: list[dict[str, Any]] = []
    baseline_summary_rows: list[dict[str, Any]] = []
    for record in baseline_records:
        sample_id = str(record["sample_id"])
        info = baseline_info[sample_id]
        baseline_ok = row_number(record.get("base_probability")) is not None
        status = "success" if baseline_ok else "failed"
        baseline_rows.append(
            {
                "sample_id": sample_id,
                "source_file": record.get("source_file", ""),
                "function": info["function"],
                "status": status,
                "probability": record.get("base_probability", ""),
                "predicted_label": record.get("base_label", ""),
                "pdg_nodes": record.get("base_nodes", ""),
                "pdg_edges": record.get("base_edges", ""),
                "xfg_count": info["xfg_count"],
                "runtime_ms": info["runtime_ms"],
                "key_line_counts": info["key_line_counts"],
                "error": record.get("error", "") if not baseline_ok else "",
            }
        )
        baseline_summary_rows.append(
            {
                "sample": sample_id,
                "function": info["function"],
                "status": status,
                "label": record.get("base_label", ""),
                "prob": record.get("base_probability", ""),
                "nodes": record.get("base_nodes", ""),
                "edges": record.get("base_edges", ""),
                "xfg_count": info["xfg_count"],
            }
        )

    perturbation_rows: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []
    for row in rows:
        sample_id = str(row["sample_id"])
        variant_name = variant_name_for(row)
        variant_info = run_info(row.get("variant_run_dir"))
        scored = is_scored_result(row)
        status = "success" if scored else "failed"
        target_fields = {
            "target_mode": row.get("target_mode", ""),
            "winner_xfg_category": row.get("winner_xfg_category", ""),
            "winner_xfg_key_line": row.get("winner_xfg_key_line", ""),
            "winner_xfg_probability": row.get("winner_xfg_probability", ""),
            "target_rank": row.get("target_rank", ""),
            "target_xfg_category": row.get("target_xfg_category", ""),
            "target_xfg_key_line": row.get("target_xfg_key_line", ""),
            "target_xfg_probability": row.get("target_xfg_probability", ""),
            "target_window_lines": row.get("target_window_lines", ""),
            "targeted_source_lines": row.get("targeted_source_lines", ""),
            "mapped_target_source_lines": row.get("mapped_target_source_lines", ""),
            "target_coverage_verified": row.get("target_coverage_verified", ""),
            "target_coverage_status": row.get("target_coverage_status", ""),
            "variant_winner_xfg_category": row.get("variant_winner_xfg_category", ""),
            "variant_winner_xfg_key_line": row.get("variant_winner_xfg_key_line", ""),
            "variant_winner_xfg_probability": row.get("variant_winner_xfg_probability", ""),
            "target_xfg_probability_after": row.get("target_xfg_probability_after", ""),
            "target_xfg_probability_delta": row.get("target_xfg_probability_delta", ""),
            "winner_xfg_changed": row.get("winner_xfg_changed", ""),
            "target_probability_decreased": row.get("target_probability_decreased", ""),
        }
        outcome_fields = {
            "flip_direction": row.get("flip_direction", ""),
            "attack_target_label": row.get("attack_target_label", 0),
            "baseline_eligible": row.get("baseline_eligible", ""),
            "attack_success": row.get("attack_success", ""),
        }
        perturbation_rows.append(
            {
                "sample_id": sample_id,
                "action": row["action"],
                "strategy": "code_perturbation",
                "seed": "",
                "requested_count": row["count"],
                "applied_count": row.get("applied_count", ""),
                "valid": scored,
                "baseline_nodes": row.get("base_nodes", ""),
                "baseline_edges": row.get("base_edges", ""),
                "perturbed_nodes": row.get("variant_nodes", ""),
                "perturbed_edges": row.get("variant_edges", ""),
                "delta_nodes": row.get("delta_nodes", ""),
                "delta_edges": row.get("delta_edges", ""),
                "baseline_xfg_count": baseline_info.get(sample_id, run_info(None))["xfg_count"],
                "perturbed_xfg_count": variant_info["xfg_count"],
                "baseline_probability": row.get("base_probability", ""),
                "perturbed_probability": row.get("variant_probability", ""),
                "delta_probability": row.get("delta_probability", ""),
                "baseline_label": row.get("base_label", ""),
                "perturbed_label": row.get("variant_label", ""),
                "flipped": row.get("flipped", ""),
                "runtime_ms": variant_info["runtime_ms"],
                "operations": row.get("notes", ""),
                "validation_errors": "" if scored else row.get("generation_status", ""),
                "error": row.get("error", ""),
                "variant_artifact_id": row.get("variant_artifact_id", ""),
                **outcome_fields,
                **target_fields,
            }
        )
        comparison = {
            "sample": sample_id,
            "action": f"{row['action']}{f'__t{row["target_rank"]}' if row.get('target_rank') else ''}__c{row['count']}",
            "function": baseline_info.get(sample_id, run_info(None))["function"],
            "status": status,
            "base_label": row.get("base_label", ""),
            "variant_label": row.get("variant_label", ""),
            "flipped": row.get("flipped", ""),
            "base_prob": row.get("base_probability", ""),
            "variant_prob": row.get("variant_probability", ""),
            "delta_prob": row.get("delta_probability", ""),
            "base_nodes": row.get("base_nodes", ""),
            "variant_nodes": row.get("variant_nodes", ""),
            "delta_nodes": row.get("delta_nodes", ""),
            "base_edges": row.get("base_edges", ""),
            "variant_edges": row.get("variant_edges", ""),
            "delta_edges": row.get("delta_edges", ""),
            "base_xfg_count": baseline_info.get(sample_id, run_info(None))["xfg_count"],
            "variant_xfg_count": variant_info["xfg_count"],
            "error": row.get("error", ""),
            **outcome_fields,
            **target_fields,
        }
        comparison_rows.append(comparison)
        detail_rows.append(
            {
                "dataset": dataset,
                "sample_id": sample_id,
                "action": row["action"],
                "count": row["count"],
                "variant_name": variant_name,
                "source_file": row.get("source_file", ""),
                "variant_file": row.get("variant_file", ""),
                "baseline_run_dir": row.get("baseline_run_dir", ""),
                "variant_run_dir": row.get("variant_run_dir", ""),
                "variant_artifact_id": row.get("variant_artifact_id", ""),
                "status": status,
                "flipped": row.get("flipped", ""),
                "notes": row.get("notes", ""),
                "error": row.get("error", ""),
                **outcome_fields,
                **target_fields,
            }
        )

    action_summary_rows: list[dict[str, Any]] = []
    action_metric_rows: list[dict[str, Any]] = []
    for action in sorted({str(row["action"]) for row in rows}):
        action_rows = [row for row in rows if row["action"] == action]
        action_scored = [row for row in action_rows if is_scored_result(row)]
        probability_deltas = [row_number(row.get("delta_probability")) for row in action_scored]
        node_deltas = [row_number(row.get("delta_nodes")) for row in action_scored]
        edge_deltas = [row_number(row.get("delta_edges")) for row in action_scored]
        probabilities = [value for value in probability_deltas if value is not None]
        nodes = [value for value in node_deltas if value is not None]
        edges = [value for value in edge_deltas if value is not None]
        flips = sum(row.get("flipped") is True for row in action_scored)
        attack_successes = sum(row.get("attack_success") is True for row in action_scored)
        reverse_flips = sum(row.get("flip_direction") == "0->1" for row in action_scored)
        attempted = len(action_rows)
        successful = len(action_scored)
        action_summary_rows.append(
            {
                "action": action,
                "count": attempted,
                "flips": flips,
                "attack_successes": attack_successes,
                "reverse_flips": reverse_flips,
                "avg_delta_prob": mean(probabilities),
                "min_delta_prob": min(probabilities) if probabilities else "",
                "max_delta_prob": max(probabilities) if probabilities else "",
                "avg_delta_nodes": mean(nodes),
                "avg_delta_edges": mean(edges),
                "attempted": attempted,
                "failed": attempted - successful,
            }
        )
        runtimes = [
            row_number(run_info(row.get("variant_run_dir"))["runtime_ms"])
            for row in action_scored
        ]
        runtime_values = [value for value in runtimes if value is not None]
        action_metric_rows.append(
            {
                "action": action,
                "attempted": attempted,
                "successful": successful,
                "failed": attempted - successful,
                "flips": flips,
                "attack_successes": attack_successes,
                "reverse_flips": reverse_flips,
                "mean_delta_probability": mean(probabilities),
                "mean_absolute_delta_probability": mean([abs(value) for value in probabilities]),
                "max_absolute_delta_probability": max((abs(value) for value in probabilities), default=""),
                "mean_runtime_ms": mean(runtime_values),
            }
        )

    for record in baseline_records:
        copy_prediction_json(record.get("baseline_run_dir"), output_root / "runs" / "baseline" / f"{record['sample_id']}.json")
    for row in rows:
        if row.get("variant_run_dir"):
            artifact_id = variant_artifact_id_for(row)
            copy_prediction_json(row["variant_run_dir"], output_root / "runs" / "perturbed" / f"{artifact_id}.json")

    attack_success_rows = [row for row in comparison_rows if row.get("attack_success") is True]
    label_flips = [row for row in comparison_rows if row.get("flipped") is True]
    reverse_flips = [row for row in comparison_rows if row.get("flip_direction") == "0->1"]

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": output_root.name,
        "source_experiment": str(output_root),
        "dataset": dataset,
        "strategy": "code_perturbation_budget_search",
        "target_mode": target_mode,
        "winner_xfg_top_k": winner_xfg_top_k if target_mode == "winner-xfg" else 0,
        "target_window_radius": target_window_radius if target_mode == "winner-xfg" else 0,
        "seed": "",
        "count": ",".join(str(count) for count in counts),
        "threshold": 0.5,
        "device": "configured_by_demo_config",
        "samples_discovered": len(sources),
        "baselines_completed": sum(row["status"] == "success" for row in baseline_rows),
        "baseline_positive_samples": sum(record.get("baseline_eligible") is True for record in baseline_records),
        "baseline_non_vulnerable_samples": sum(record.get("eligibility_reason") == "baseline_predicted_non_vulnerable" for record in baseline_records),
        "perturbations_attempted": len(rows),
        "perturbations_successful": sum(row["status"] == "success" for row in comparison_rows),
        "label_flips": len(label_flips),
        "attack_successes": len(attack_success_rows),
        "reverse_label_flips": len(reverse_flips),
        "target_not_covered": sum(row.get("target_coverage_status") == "target_not_covered" for row in rows),
        "actions": actions,
    }

    write_csv(output_root / "baseline_predictions.csv", baseline_rows, BASELINE_PREDICTION_FIELDS)
    write_csv(output_root / "baseline_summary.csv", baseline_summary_rows, BASELINE_SUMMARY_FIELDS)
    write_csv(output_root / "baseline_eligibility.csv", baseline_records, BASELINE_ELIGIBILITY_FIELDS)
    write_csv(output_root / "perturbation_results.csv", perturbation_rows, PERTURBATION_RESULT_FIELDS)
    write_csv(output_root / "prediction_comparison.csv", comparison_rows, COMPARISON_FIELDS)
    write_csv(output_root / "action_summary.csv", action_summary_rows, ACTION_SUMMARY_FIELDS)
    write_csv(output_root / "action_metrics.csv", action_metric_rows, ACTION_METRIC_FIELDS)
    write_json(output_root / "summary.json", {
        "metadata": metadata,
        "baseline_predictions": baseline_summary_rows,
        "baseline_eligibility": baseline_records,
        "action_summary": action_summary_rows,
        "action_metrics": action_metric_rows,
        "label_flips": label_flips,
        "attack_successes": attack_success_rows,
        "reverse_label_flips": reverse_flips,
    })
    write_json(output_root / "details.json", {
        "metadata": metadata,
        "baseline_eligibility": baseline_records,
        "details": detail_rows,
        "label_flips": label_flips,
        "attack_successes": attack_success_rows,
        "reverse_label_flips": reverse_flips,
    })
    write_report_readme(
        output_root,
        dataset,
        len(sources),
        metadata["baseline_positive_samples"],
        metadata["baseline_non_vulnerable_samples"],
        len(rows),
        metadata["perturbations_successful"],
        metadata["attack_successes"],
        metadata["label_flips"],
        target_mode,
    )

    if not any(row["status"] == "success" for row in comparison_rows):
        return "dashboard skipped: no successful baseline-versus-variant comparisons"
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "robustness_experiments" / "visualize_results.py"),
        "--run-dir",
        str(output_root),
    ]
    proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), text=True, encoding="utf-8", errors="replace", capture_output=True)
    if proc.returncode == 0:
        return "dashboard written"
    return f"dashboard failed: {(proc.stderr.strip() or proc.stdout.strip())[-1000:]}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search for minimal perturbation counts that flip DeepWuKong predictions.")
    parser.add_argument("--input", type=Path, default=PROJECT_ROOT / "input_sources" / "devign")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    parser.add_argument("--run-round", type=int, default=1)
    parser.add_argument("--deepwukong-root", type=Path, default=PROJECT_ROOT / "baselines" / "deepwukong")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "baselines" / "deepwukong" / "configs" / "demo_config.json")
    parser.add_argument("--actions", nargs="+", default=list(OPERATORS), choices=sorted(OPERATORS))
    parser.add_argument("--action", dest="actions", nargs="+", choices=sorted(OPERATORS), help=argparse.SUPPRESS)
    parser.add_argument(
        "--target-mode",
        choices=["global", "winner-xfg"],
        default="global",
        help="Use global candidates, or independently target the highest-scoring baseline XFG source windows.",
    )
    parser.add_argument(
        "--winner-xfg-top-k",
        type=int,
        default=3,
        help="Number of distinct high-probability XFG source lines to test in winner-XFG mode (default: 3).",
    )
    parser.add_argument(
        "--target-window-radius",
        type=int,
        default=3,
        help="Maximum source-line distance used to verify a rebuilt XFG still covers a target window (default: 3).",
    )
    parser.add_argument("--counts", nargs="+", type=int, default=[1, 2, 3, 5])
    parser.add_argument("--count", dest="counts", nargs="+", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--no-run", action="store_true", help="Generate variants and rows without invoking DeepWuKong.")
    args = parser.parse_args()
    args.counts = normalize_counts(args.counts)
    if args.run_round < 1:
        parser.error("--run-round must be at least 1")
    if args.winner_xfg_top_k < 1:
        parser.error("--winner-xfg-top-k must be at least 1")
    if args.target_window_radius < 0:
        parser.error("--target-window-radius cannot be negative")
    if args.no_run and args.target_mode == "winner-xfg":
        parser.error("--target-mode winner-xfg requires a baseline DeepWuKong inference; remove --no-run")
    if args.output is None:
        target_marker = "_winner_xfg" if args.target_mode == "winner-xfg" else ""
        run_name = (
            f"run_{datetime.now().strftime('%Y%m%d')}_code_"
            f"{dataset_slug(args.input)}{target_marker}_round{args.run_round}"
        )
        args.output = PROJECT_ROOT / "outputs" / run_name
    return args


def main() -> int:
    args = parse_args()
    input_path = args.input.resolve()
    output_root = args.output.resolve()
    deepwukong_root = args.deepwukong_root.resolve()
    config_path = args.config.resolve()
    sources_dir = output_root / "sources"
    baseline_root = output_root / "runs" / "baseline"
    perturbed_root = output_root / "runs" / "perturbed"
    rows: list[dict[str, Any]] = []
    attack_successes: list[dict[str, Any]] = []
    baseline_records: list[dict[str, Any]] = []

    sources = discover_sources(input_path, recursive=args.recursive)
    if not sources:
        raise FileNotFoundError(f"No C/C++ sources found under: {input_path}")

    sources_dir.mkdir(parents=True, exist_ok=True)
    for source in sources:
        sample_id = compact_sample_id(source)
        baseline_run_dir = baseline_root / sample_id
        base_prediction: dict[str, Any] | None = None
        baseline_xfgs: list[WinnerXFG] = []
        winner_xfg: WinnerXFG | None = None
        baseline_error = ""
        if args.no_run:
            baseline_status = "not_run"
        else:
            ok, baseline_error = run_deepwukong(
                source_file=source,
                output_dir=baseline_run_dir,
                deepwukong_root=deepwukong_root,
                config_path=config_path,
                timeout_seconds=args.timeout_seconds,
            )
            baseline_status = "ran" if ok else "baseline_failed"
            base_prediction = prediction_from_run(baseline_run_dir) if ok else None
            baseline_xfgs = winner_xfgs_from_run(baseline_run_dir) if ok else []
            winner_xfg = baseline_xfgs[0] if baseline_xfgs else None
            if args.target_mode == "winner-xfg" and baseline_xfgs:
                selected_targets = distinct_source_targets(baseline_xfgs, args.winner_xfg_top_k)
                target_text = ", ".join(
                    f"t{rank}:{target.category}@{target.key_line}={target.vulnerability_probability:.6f}"
                    for rank, target in enumerate(selected_targets, start=1)
                )
                print(
                    f"WINNER_XFG_TARGETS {sample_id} {target_text}",
                    flush=True,
                )

        original = source.read_text(encoding="utf-8", errors="replace")
        base_label = row_int(base_prediction.get("predicted_label")) if base_prediction else None
        base_probability = row_number(base_prediction.get("vulnerability_probability")) if base_prediction else None
        base_nodes = row_int(base_prediction.get("num_nodes")) if base_prediction else None
        base_edges = row_int(base_prediction.get("num_edges")) if base_prediction else None
        baseline_eligible: bool | str
        if args.no_run:
            baseline_eligible = ""
            eligibility_reason = "not_evaluated_no_run"
        elif baseline_status != "ran" or base_label is None:
            baseline_eligible = False
            eligibility_reason = "baseline_failed"
        elif base_label == 1:
            baseline_eligible = True
            eligibility_reason = "baseline_predicted_vulnerable"
        else:
            baseline_eligible = False
            eligibility_reason = "baseline_predicted_non_vulnerable"

        baseline_records.append(
            {
                "sample_id": sample_id,
                "source_file": str(source),
                "baseline_status": baseline_status,
                "base_label": base_label if base_label is not None else "",
                "base_probability": base_probability if base_probability is not None else "",
                "base_nodes": base_nodes if base_nodes is not None else "",
                "base_edges": base_edges if base_edges is not None else "",
                "baseline_eligible": baseline_eligible,
                "eligibility_reason": eligibility_reason,
                "baseline_run_dir": str(baseline_run_dir) if not args.no_run else "",
                "winner_xfg_category": winner_xfg.category if winner_xfg else "",
                "winner_xfg_key_line": winner_xfg.key_line if winner_xfg else "",
                "winner_xfg_probability": winner_xfg.vulnerability_probability if winner_xfg else "",
                "winner_xfg_candidates": json.dumps(
                    [
                        {
                            "category": candidate.category,
                            "key_line": candidate.key_line,
                            "vulnerability_probability": candidate.vulnerability_probability,
                        }
                        for candidate in baseline_xfgs
                    ],
                    ensure_ascii=False,
                ),
                "error": baseline_error,
            }
        )

        # A source-level evasion attack is meaningful only when the baseline is vulnerable.
        if not args.no_run and baseline_eligible is not True:
            print(f"SKIP_BASELINE {sample_id} reason={eligibility_reason}", flush=True)
            continue

        if args.target_mode == "winner-xfg":
            target_candidates: list[WinnerXFG | None] = distinct_source_targets(
                baseline_xfgs, args.winner_xfg_top_k
            )
            if not target_candidates:
                target_candidates = [None]
        else:
            target_candidates = [None]

        for action_name in args.actions:
            action = OPERATORS[action_name]
            inactive_target_ranks: set[int] = set()
            seen_effective_counts: dict[int, set[int]] = {}
            seen_variant_sources: set[str] = set()
            action_succeeded = False
            for count in args.counts:
                active_target_seen = False
                for target_rank, target in enumerate(target_candidates, start=1):
                    if target_rank in inactive_target_ranks:
                        continue
                    active_target_seen = True
                    target_line = target.key_line if target else None
                    target_error = ""
                    if args.target_mode == "winner-xfg":
                        if target is None:
                            target_error = "baseline did not provide a usable XFG source target"
                        elif not action.winner_xfg_targetable:
                            target_error = f"action {action.name} has no winner-XFG-local implementation"

                    target_suffix = f"__t{target_rank}" if target is not None else ""
                    variant_label = f"{sample_id}__{action.name}{target_suffix}__c{count}"
                    variant_artifact_id = compact_path_component(variant_label)
                    variant_file = sources_dir / f"{variant_artifact_id}{source.suffix}"
                    variant_run_dir = perturbed_root / variant_artifact_id
                    if target_error:
                        result = PerturbationResult(original, 0, target_error)
                    elif target_line is None:
                        result = action.apply(original, count)
                    else:
                        result = action.apply(original, count, target_line)

                    gen_status = generation_status(result.applied_count, count)
                    run_status = "target_unavailable" if target_error else ("not_run" if args.no_run else baseline_status)
                    error = target_error or baseline_error
                    if result.applied_count > 0 and result.source_text in seen_variant_sources:
                        result = PerturbationResult(original, 0, "duplicate source variant for this action target")
                        gen_status = "duplicate_target_variant"
                        run_status = "duplicate_candidate"
                    elif result.applied_count > 0:
                        seen_variant_sources.add(result.source_text)

                    variant_prediction: dict[str, Any] | None = None
                    if result.applied_count > 0:
                        variant_file.write_text(result.source_text, encoding="utf-8", newline="")
                        if not args.no_run and baseline_status == "ran":
                            ok, error = run_deepwukong(
                                source_file=variant_file,
                                output_dir=variant_run_dir,
                                deepwukong_root=deepwukong_root,
                                config_path=config_path,
                                timeout_seconds=args.timeout_seconds,
                            )
                            if ok:
                                run_status = "run_partial" if gen_status == "partial" else "ran"
                                variant_prediction = prediction_from_run(variant_run_dir)
                            else:
                                run_status = "run_failed"

                    coverage = target_coverage_from_run(
                        original=original,
                        variant=result.source_text,
                        baseline_winner=winner_xfg,
                        target=target,
                        selected_source_lines=result.selected_source_lines,
                        variant_run_dir=variant_run_dir if variant_prediction is not None else None,
                        radius=args.target_window_radius,
                    )
                    comparison = compare_predictions(base_prediction, variant_prediction)
                    target_after = (
                        coverage.variant_target.vulnerability_probability
                        if coverage.variant_target is not None
                        else ""
                    )
                    row = {
                        "sample_id": sample_id,
                        "source_file": str(source),
                        "action": action.name,
                        "target_mode": args.target_mode,
                        "winner_xfg_category": winner_xfg.category if winner_xfg else "",
                        "winner_xfg_key_line": winner_xfg.key_line if winner_xfg else "",
                        "winner_xfg_probability": winner_xfg.vulnerability_probability if winner_xfg else "",
                        "target_rank": target_rank if target is not None else "",
                        "target_xfg_category": target.category if target else "",
                        "target_xfg_key_line": target.key_line if target else "",
                        "target_xfg_probability": target.vulnerability_probability if target else "",
                        "target_window_lines": ",".join(
                            str(line)
                            for line in source_window_lines(original, target.key_line, args.target_window_radius)
                        ) if target else "",
                        "targeted_source_lines": ",".join(str(line) for line in result.selected_source_lines),
                        "mapped_target_source_lines": ",".join(str(line) for line in coverage.mapped_source_lines),
                        "target_coverage_verified": coverage.verified,
                        "target_coverage_status": coverage.status,
                        "variant_winner_xfg_category": coverage.variant_winner.category if coverage.variant_winner else "",
                        "variant_winner_xfg_key_line": coverage.variant_winner.key_line if coverage.variant_winner else "",
                        "variant_winner_xfg_probability": coverage.variant_winner.vulnerability_probability if coverage.variant_winner else "",
                        "target_xfg_probability_after": target_after,
                        "target_xfg_probability_delta": (
                            target_after - target.vulnerability_probability
                            if isinstance(target_after, float) and target is not None
                            else ""
                        ),
                        "winner_xfg_changed": coverage.winner_changed,
                        "target_probability_decreased": coverage.target_probability_decreased,
                        "count": count,
                        "applied_count": result.applied_count,
                        "generation_status": gen_status,
                        "run_status": run_status,
                        "baseline_eligible": baseline_eligible,
                        "baseline_run_dir": str(baseline_run_dir) if not args.no_run else "",
                        "variant_run_dir": str(variant_run_dir) if result.applied_count > 0 and not args.no_run else "",
                        "variant_artifact_id": variant_artifact_id if result.applied_count > 0 else "",
                        "variant_file": str(variant_file) if result.applied_count > 0 else "",
                        "notes": result.notes,
                        "error": error,
                        **comparison,
                    }
                    rows.append(row)

                    if comparison.get("attack_success") is True:
                        attack_successes.append(row)
                        action_succeeded = True
                        print(
                            f"ATTACK_SUCCESS {sample_id} {action.name} target={target_rank} count={count}",
                            flush=True,
                        )
                        break

                    # If Joern did not rebuild an XFG around this target, raising the count cannot refine it.
                    if target is not None and coverage.status == "target_not_covered":
                        inactive_target_ranks.add(target_rank)
                    if result.applied_count <= 0:
                        inactive_target_ranks.add(target_rank)
                    elif result.applied_count in seen_effective_counts.setdefault(target_rank, set()):
                        inactive_target_ranks.add(target_rank)
                    else:
                        seen_effective_counts[target_rank].add(result.applied_count)
                        if result.applied_count < count:
                            inactive_target_ranks.add(target_rank)

                if action_succeeded or not active_target_seen:
                    break

    write_csv(output_root / "budget_search.csv", rows)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input": str(input_path),
        "output": str(output_root),
        "actions": args.actions,
        "target_mode": args.target_mode,
        "winner_xfg_top_k": args.winner_xfg_top_k if args.target_mode == "winner-xfg" else 0,
        "target_window_radius": args.target_window_radius if args.target_mode == "winner-xfg" else 0,
        "counts": args.counts,
        "no_run": args.no_run,
        "rows": len(rows),
        "attack_successes": len(attack_successes),
        "attack_success_rows": attack_successes,
        "label_flips": sum(row.get("flipped") is True for row in rows),
        "reverse_label_flips": sum(row.get("flip_direction") == "0->1" for row in rows),
        "baseline_eligibility": baseline_records,
    }
    summary["standard_report"] = write_standard_report(
        output_root=output_root,
        rows=rows,
        baseline_records=baseline_records,
        input_path=input_path,
        sources=sources,
        target_mode=args.target_mode,
        counts=args.counts,
        actions=args.actions,
        winner_xfg_top_k=args.winner_xfg_top_k,
        target_window_radius=args.target_window_radius,
    )
    write_json(output_root / "budget_search.json", summary)
    print(f"Rows: {len(rows)}")
    print(f"Attack successes (1->0): {len(attack_successes)}")
    print(f"All label flips: {summary['label_flips']}")
    print(f"CSV: {output_root / 'budget_search.csv'}")
    print(f"JSON: {output_root / 'budget_search.json'}")
    print(f"Standard report: {summary['standard_report']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
