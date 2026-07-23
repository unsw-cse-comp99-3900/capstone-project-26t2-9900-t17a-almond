from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from demo_b.code.code_perturbations import (
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


CSV_FIELDS = [
    "sample_id",
    "source_file",
    "action",
    "target_mode",
    "winner_xfg_category",
    "winner_xfg_key_line",
    "winner_xfg_probability",
    "targeted_source_lines",
    "count",
    "applied_count",
    "generation_status",
    "run_status",
    "flipped",
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
    "variant_file",
    "notes",
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
    "runtime_ms",
    "operations",
    "validation_errors",
    "error",
    "target_mode",
    "winner_xfg_category",
    "winner_xfg_key_line",
    "winner_xfg_probability",
    "targeted_source_lines",
]

COMPARISON_FIELDS = [
    "sample",
    "action",
    "function",
    "status",
    "base_label",
    "variant_label",
    "flipped",
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
    "targeted_source_lines",
]

ACTION_SUMMARY_FIELDS = [
    "action",
    "count",
    "flips",
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


def winner_xfg_from_run(run_dir: Path) -> WinnerXFG | None:
    """Return the baseline XFG responsible for the maximum vulnerability probability."""
    prediction_path = run_dir / "predictions.json"
    if not prediction_path.is_file():
        return None

    payload = read_json(prediction_path)
    details = payload.get("details")
    if not isinstance(details, dict):
        return None
    features = details.get("features")
    if not isinstance(features, dict):
        return None
    xfg = features.get("xfg")
    if not isinstance(xfg, dict):
        return None
    predictions = xfg.get("xfg_predictions")
    if not isinstance(predictions, list):
        return None

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
        return None

    return min(
        candidates,
        key=lambda item: (-item.vulnerability_probability, item.key_line, item.category),
    )


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
    return {
        "flipped": bool(base_label != variant_label) if base_label is not None and variant_label is not None else "",
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
    attempts: int,
    successful: int,
    flips: int,
    target_mode: str,
) -> None:
    report = f"""# {output_root.name}

This is an automatically generated DeepWuKong code-perturbation report. It uses
the same report layout as the archived `run_20260717_code_*_round1` experiments.

## Result

- Dataset: `{dataset}`
- Target mode: `{target_mode}`
- Samples: {samples}
- Perturbation attempts: {attempts}
- Successful runs: {successful}
- Label flips: {flips}

## Contents

- `baseline_predictions.csv` and `baseline_summary.csv`: one baseline result per sample.
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
    input_path: Path,
    sources: list[Path],
    target_mode: str,
    counts: list[int],
    actions: list[str],
) -> str:
    """Write the archived code-run report layout without rerunning DeepWuKong."""
    dataset = report_dataset_name(input_path, sources)
    first_row_by_sample: dict[str, dict[str, Any]] = {}
    for row in rows:
        first_row_by_sample.setdefault(str(row["sample_id"]), row)

    baseline_info = {
        sample_id: run_info(row.get("baseline_run_dir")) for sample_id, row in first_row_by_sample.items()
    }
    baseline_rows: list[dict[str, Any]] = []
    baseline_summary_rows: list[dict[str, Any]] = []
    for sample_id, row in first_row_by_sample.items():
        info = baseline_info[sample_id]
        baseline_ok = row_number(row.get("base_probability")) is not None
        status = "success" if baseline_ok else "failed"
        baseline_rows.append(
            {
                "sample_id": sample_id,
                "source_file": row.get("source_file", ""),
                "function": info["function"],
                "status": status,
                "probability": row.get("base_probability", ""),
                "predicted_label": row.get("base_label", ""),
                "pdg_nodes": row.get("base_nodes", ""),
                "pdg_edges": row.get("base_edges", ""),
                "xfg_count": info["xfg_count"],
                "runtime_ms": info["runtime_ms"],
                "key_line_counts": info["key_line_counts"],
                "error": row.get("error", "") if not baseline_ok else "",
            }
        )
        baseline_summary_rows.append(
            {
                "sample": sample_id,
                "function": info["function"],
                "status": status,
                "label": row.get("base_label", ""),
                "prob": row.get("base_probability", ""),
                "nodes": row.get("base_nodes", ""),
                "edges": row.get("base_edges", ""),
                "xfg_count": info["xfg_count"],
            }
        )

    perturbation_rows: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []
    for row in rows:
        sample_id = str(row["sample_id"])
        variant_name = f"{sample_id}__{row['action']}__c{row['count']}"
        variant_info = run_info(row.get("variant_run_dir"))
        scored = is_scored_result(row)
        status = "success" if scored else "failed"
        target_fields = {
            "target_mode": row.get("target_mode", ""),
            "winner_xfg_category": row.get("winner_xfg_category", ""),
            "winner_xfg_key_line": row.get("winner_xfg_key_line", ""),
            "winner_xfg_probability": row.get("winner_xfg_probability", ""),
            "targeted_source_lines": row.get("targeted_source_lines", ""),
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
                "baseline_xfg_count": baseline_info[sample_id]["xfg_count"],
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
                **target_fields,
            }
        )
        comparison = {
            "sample": sample_id,
            "action": f"{row['action']}__c{row['count']}",
            "function": baseline_info[sample_id]["function"],
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
            "base_xfg_count": baseline_info[sample_id]["xfg_count"],
            "variant_xfg_count": variant_info["xfg_count"],
            "error": row.get("error", ""),
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
                "status": status,
                "flipped": row.get("flipped", ""),
                "notes": row.get("notes", ""),
                "error": row.get("error", ""),
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
        attempted = len(action_rows)
        successful = len(action_scored)
        action_summary_rows.append(
            {
                "action": action,
                "count": attempted,
                "flips": flips,
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
                "mean_delta_probability": mean(probabilities),
                "mean_absolute_delta_probability": mean([abs(value) for value in probabilities]),
                "max_absolute_delta_probability": max((abs(value) for value in probabilities), default=""),
                "mean_runtime_ms": mean(runtime_values),
            }
        )

    for sample_id, row in first_row_by_sample.items():
        copy_prediction_json(row.get("baseline_run_dir"), output_root / "runs" / "baseline" / f"{sample_id}.json")
    for row in rows:
        if row.get("variant_run_dir"):
            variant_name = f"{row['sample_id']}__{row['action']}__c{row['count']}"
            copy_prediction_json(row["variant_run_dir"], output_root / "runs" / "perturbed" / f"{variant_name}.json")

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": output_root.name,
        "source_experiment": str(output_root),
        "dataset": dataset,
        "strategy": "code_perturbation_budget_search",
        "target_mode": target_mode,
        "seed": "",
        "count": ",".join(str(count) for count in counts),
        "threshold": 0.5,
        "device": "configured_by_demo_config",
        "samples_discovered": len(sources),
        "baselines_completed": sum(row["status"] == "success" for row in baseline_rows),
        "perturbations_attempted": len(rows),
        "perturbations_successful": sum(row["status"] == "success" for row in comparison_rows),
        "label_flips": sum(row.get("flipped") is True for row in comparison_rows),
        "actions": actions,
    }
    flips = [row for row in comparison_rows if row.get("flipped") is True]

    write_csv(output_root / "baseline_predictions.csv", baseline_rows, BASELINE_PREDICTION_FIELDS)
    write_csv(output_root / "baseline_summary.csv", baseline_summary_rows, BASELINE_SUMMARY_FIELDS)
    write_csv(output_root / "perturbation_results.csv", perturbation_rows, PERTURBATION_RESULT_FIELDS)
    write_csv(output_root / "prediction_comparison.csv", comparison_rows, COMPARISON_FIELDS)
    write_csv(output_root / "action_summary.csv", action_summary_rows, ACTION_SUMMARY_FIELDS)
    write_csv(output_root / "action_metrics.csv", action_metric_rows, ACTION_METRIC_FIELDS)
    write_json(output_root / "summary.json", {
        "metadata": metadata,
        "baseline_predictions": baseline_summary_rows,
        "action_summary": action_summary_rows,
        "action_metrics": action_metric_rows,
        "label_flips": flips,
    })
    write_json(output_root / "details.json", {"metadata": metadata, "details": detail_rows, "label_flips": flips})
    write_report_readme(
        output_root,
        dataset,
        len(sources),
        len(rows),
        metadata["perturbations_successful"],
        metadata["label_flips"],
        target_mode,
    )

    if not any(row["status"] == "success" for row in comparison_rows):
        return "dashboard skipped: no successful baseline-versus-variant comparisons"
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "demo_b" / "visualize_results.py"),
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
        help="Use existing global candidates, or rank candidates by the baseline winner XFG key line.",
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
    flips: list[dict[str, Any]] = []

    sources = discover_sources(input_path, recursive=args.recursive)
    if not sources:
        raise FileNotFoundError(f"No C/C++ sources found under: {input_path}")

    sources_dir.mkdir(parents=True, exist_ok=True)
    for source in sources:
        sample_id = safe_stem(source)
        baseline_run_dir = baseline_root / sample_id
        base_prediction: dict[str, Any] | None = None
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
            winner_xfg = winner_xfg_from_run(baseline_run_dir) if ok else None
            if args.target_mode == "winner-xfg" and winner_xfg is not None:
                print(
                    f"WINNER_XFG {sample_id} category={winner_xfg.category} "
                    f"key_line={winner_xfg.key_line} probability={winner_xfg.vulnerability_probability:.6f}",
                    flush=True,
                )

        original = source.read_text(encoding="utf-8", errors="replace")
        for action_name in args.actions:
            action = OPERATORS[action_name]
            seen_effective_counts: set[int] = set()
            for count in args.counts:
                variant_file = sources_dir / f"{sample_id}__{action.name}__c{count}{source.suffix}"
                variant_run_dir = perturbed_root / f"{sample_id}__{action.name}__c{count}"
                target_line: int | None = None
                target_error = ""
                if args.target_mode == "winner-xfg":
                    if winner_xfg is None:
                        target_error = "baseline did not provide an XFG key line for winner-XFG targeting"
                    elif not action.winner_xfg_targetable:
                        target_error = f"action {action.name} has no winner-XFG-local implementation"
                    else:
                        target_line = winner_xfg.key_line

                if target_error:
                    result = PerturbationResult(original, 0, target_error)
                elif target_line is None:
                    result = action.apply(original, count)
                else:
                    result = action.apply(original, count, target_line)
                gen_status = generation_status(result.applied_count, count)
                run_status = "target_unavailable" if target_error else ("not_run" if args.no_run else baseline_status)
                error = target_error or baseline_error
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

                comparison = compare_predictions(base_prediction, variant_prediction)
                row = {
                    "sample_id": sample_id,
                    "source_file": str(source),
                    "action": action.name,
                    "target_mode": args.target_mode,
                    "winner_xfg_category": winner_xfg.category if winner_xfg else "",
                    "winner_xfg_key_line": winner_xfg.key_line if winner_xfg else "",
                    "winner_xfg_probability": winner_xfg.vulnerability_probability if winner_xfg else "",
                    "targeted_source_lines": ",".join(str(line) for line in result.selected_source_lines),
                    "count": count,
                    "applied_count": result.applied_count,
                    "generation_status": gen_status,
                    "run_status": run_status,
                    "baseline_run_dir": str(baseline_run_dir) if not args.no_run else "",
                    "variant_run_dir": str(variant_run_dir) if result.applied_count > 0 and not args.no_run else "",
                    "variant_file": str(variant_file) if result.applied_count > 0 else "",
                    "notes": result.notes,
                    "error": error,
                    **comparison,
                }
                rows.append(row)

                if comparison.get("flipped") is True:
                    flips.append(row)
                    print(f"FLIP {sample_id} {action.name} count={count}", flush=True)
                    break

                if result.applied_count <= 0:
                    break
                if result.applied_count in seen_effective_counts:
                    break
                seen_effective_counts.add(result.applied_count)
                if result.applied_count < count:
                    break

    write_csv(output_root / "budget_search.csv", rows)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input": str(input_path),
        "output": str(output_root),
        "actions": args.actions,
        "target_mode": args.target_mode,
        "counts": args.counts,
        "no_run": args.no_run,
        "rows": len(rows),
        "flips": len(flips),
        "flip_rows": flips,
    }
    summary["standard_report"] = write_standard_report(
        output_root=output_root,
        rows=rows,
        input_path=input_path,
        sources=sources,
        target_mode=args.target_mode,
        counts=args.counts,
        actions=args.actions,
    )
    write_json(output_root / "budget_search.json", summary)
    print(f"Rows: {len(rows)}")
    print(f"Flips: {len(flips)}")
    print(f"CSV: {output_root / 'budget_search.csv'}")
    print(f"JSON: {output_root / 'budget_search.json'}")
    print(f"Standard report: {summary['standard_report']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
