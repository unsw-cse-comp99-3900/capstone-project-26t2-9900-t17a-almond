#!/usr/bin/env python3
"""
DeepWuKong Robustness Testing Console
T17A Almond - COMP9900

Main menu:
1. Run Full Test
2. Run Smoke Test
3. Results Summary
4. Perturbation Impact Analysis
5. Sample Detail Viewer
6. Open Web Dashboard
0. Exit

Current capabilities:
- Option 6 opens the experiment index, function-level PDG atlas, or latest
  random-versus-Winner-XFG comparison when one has been generated.
- Options 3 and 4 still allow selecting different run folders.
- Option 4 normalizes perturbation metrics across all supported run formats.
"""

from __future__ import annotations

import csv
import os
import re
import sys
import time
import webbrowser
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode
from urllib.request import urlopen

from robustness_experiments.graph.experiment_design import DEFAULT_GRAPH_BUDGETS


# ============================================================
# Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent
GRAPH_BUDGET_LABEL = "/".join(str(value) for value in DEFAULT_GRAPH_BUDGETS)

# Static browser entry points.
EXPERIMENT_DASHBOARD_HTML = PROJECT_ROOT / "outputs" / "index.html"
PDG_ATLAS_HTML = PROJECT_ROOT / "robustness_experiments" / "showcase" / "deepwukong_pdg_showcase.html"

# Run the full perturbation experiment inside the packaged DeepWuKong image.
START_TEST_COMMAND: Optional[List[str]] = [sys.executable, "scripts/run_full_test.py"]

# Run one baseline inference to verify the live pipeline without generating perturbations.
QUICK_TEST_COMMAND: Optional[List[str]] = [sys.executable, "tests/run_quick_test.py"]

# If you want to force one run folder as default, set it here.
# Example: DEFAULT_RUN_ID = "run_20260710_code_devign_round1"
DEFAULT_RUN_ID: Optional[str] = None

PREDICTION_COMPARISON_NAMES = [
    "prediction_comparison.csv",
    "comparison.csv",
    "results.csv",
]

ACTION_SUMMARY_NAMES = [
    "action_summary.csv",
    "perturbation_summary.csv",
    "impact_summary.csv",
]

BASELINE_SUMMARY_NAMES = [
    "baseline_summary.csv",
    "baseline.csv",
]

MANIFEST_NAMES = [
    "manifest.csv",
    "perturbation_manifest.csv",
]


# ============================================================
# Basic UI helpers
# ============================================================

def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def pause(message: str = "Press Enter to continue...") -> None:
    input(f"\n{message}")


def print_header(title: str) -> None:
    clear_screen()
    print("=" * 72)
    print(f" {title}")
    print("=" * 72)


def slow_print(lines: List[str], delay: float = 0.02) -> None:
    for line in lines:
        print(line)
        time.sleep(delay)


# ============================================================
# File helpers
# ============================================================

def read_csv(path: Optional[Path]) -> List[Dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def list_run_dirs() -> List[Path]:
    outputs_dir = PROJECT_ROOT / "outputs"
    if not outputs_dir.exists():
        return []

    candidates = [p for p in outputs_dir.iterdir() if p.is_dir()]
    candidates.sort(
        key=lambda p: (
            0 if p.name.lower().startswith("run") else 1,
            -p.stat().st_mtime,
        )
    )
    return candidates


def get_default_run_dir() -> Optional[Path]:
    if DEFAULT_RUN_ID:
        p = PROJECT_ROOT / "outputs" / DEFAULT_RUN_ID
        if p.exists():
            return p
    runs = list_run_dirs()
    return runs[0] if runs else None


def find_file(run_dir: Optional[Path], names: List[str]) -> Optional[Path]:
    if run_dir is None:
        return None

    for name in names:
        p = run_dir / name
        if p.exists():
            return p

    for name in names:
        matches = list(run_dir.rglob(name))
        if matches:
            matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return matches[0]

    return None


def find_manifest_file(run_dir: Optional[Path]) -> Optional[Path]:
    if run_dir is not None:
        artifacts_manifest_dir = PROJECT_ROOT / "artifacts" / "perturbed_sources" / run_dir.name
        for name in MANIFEST_NAMES:
            p = artifacts_manifest_dir / name
            if p.exists():
                return p

    artifacts_dir = PROJECT_ROOT / "artifacts"
    if artifacts_dir.exists():
        for name in MANIFEST_NAMES:
            matches = list(artifacts_dir.rglob(name))
            if matches:
                matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                return matches[0]

    return find_file(run_dir, MANIFEST_NAMES)


def run_file_status(run_dir: Path) -> Dict[str, Any]:
    prediction_file = find_file(run_dir, PREDICTION_COMPARISON_NAMES)
    prediction_rows = read_csv(prediction_file)
    return {
        "prediction_file": prediction_file,
        "prediction_count": len(prediction_rows),
    }


def choose_run_dir(title: str = "Choose a Run") -> Optional[Path]:
    runs = list_run_dirs()
    print_header(title)

    if not runs:
        print("No run folders were found under outputs/.")
        print("Please run the full test first or check your project folder.")
        pause()
        return None

    print("Available run folders:")
    print("-" * 72)
    for i, run_dir in enumerate(runs, start=1):
        status = run_file_status(run_dir)
        pred = f"prediction rows: {status['prediction_count']}"
        print(f"{i}. {run_dir.name:25} | {pred}")

    print("\n0. Back")
    choice = input("\nSelect a run: ").strip()

    if choice == "0":
        return None

    try:
        idx = int(choice)
        if 1 <= idx <= len(runs):
            return runs[idx - 1]
    except ValueError:
        pass

    print("Invalid run selection.")
    pause()
    return None


def load_run_data(run_dir: Optional[Path]) -> Dict[str, Any]:
    prediction_file = find_file(run_dir, PREDICTION_COMPARISON_NAMES)
    action_file = find_file(run_dir, ACTION_SUMMARY_NAMES)
    baseline_file = find_file(run_dir, BASELINE_SUMMARY_NAMES)
    manifest_file = find_manifest_file(run_dir)

    return {
        "run_dir": run_dir,
        "prediction_file": prediction_file,
        "action_file": action_file,
        "baseline_file": baseline_file,
        "manifest_file": manifest_file,
        "prediction_rows": read_csv(prediction_file),
        "action_rows": read_csv(action_file),
        "baseline_rows": read_csv(baseline_file),
        "manifest_rows": read_csv(manifest_file),
    }


def print_data_location(data: Dict[str, Any]) -> None:
    print("\nDetected data files:")
    print(f"- Run directory:          {data['run_dir'] if data['run_dir'] else 'Not found'}")
    print(f"- Prediction comparison:  {data['prediction_file'] if data['prediction_file'] else 'Not found'}")
    print(f"- Action summary:         {data['action_file'] if data['action_file'] else 'Not found'}")
    print(f"- Baseline summary:       {data['baseline_file'] if data['baseline_file'] else 'Not found'}")
    print(f"- Perturbation manifest:  {data['manifest_file'] if data['manifest_file'] else 'Not found'}")
    print(f"- Experiment dashboard:   {EXPERIMENT_DASHBOARD_HTML}")
    print(f"- Function PDG atlas:     {PDG_ATLAS_HTML}")


# ============================================================
# CSV data helpers
# ============================================================

def to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(str(value).strip())
    except ValueError:
        return default


def format_table_number(value: Any, width: int = 14) -> str:
    """Format numeric table cells compactly without breaking fixed-width columns."""
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return str(value or "")[:width].rjust(width)
    text = f"{number:.6f}" if number == 0 or abs(number) >= 0.0001 else f"{number:.3e}"
    return text[:width].rjust(width)


def pick_column(row: Dict[str, str], options: List[str]) -> Optional[str]:
    lower = {k.lower(): k for k in row.keys()}
    for option in options:
        if option.lower() in lower:
            return lower[option.lower()]
    return None


def detect_probability_columns(row: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
    original_options = [
        "original_prob", "orig_prob", "baseline_prob", "original_probability",
        "baseline_probability", "orig_probability", "original_score", "baseline_score",
        "original_confidence", "baseline_confidence",
    ]
    perturbed_options = [
        "perturbed_prob", "pert_prob", "new_prob", "perturbed_probability",
        "prediction_prob", "perturbed_score", "new_score",
        "perturbed_confidence", "new_confidence",
    ]
    return pick_column(row, original_options), pick_column(row, perturbed_options)


def get_delta_probability(row: Dict[str, str]) -> float:
    for key in ["delta_prob", "prob_delta", "confidence_change", "delta_confidence", "probability_change"]:
        if key in row and str(row.get(key, "")).strip() != "":
            return abs(to_float(row.get(key)))

    original_col, perturbed_col = detect_probability_columns(row)
    if original_col and perturbed_col:
        return abs(to_float(row.get(perturbed_col)) - to_float(row.get(original_col)))

    return 0.0


def is_flip(row: Dict[str, str]) -> bool:
    for key in ["flipped", "flip", "prediction_flip", "changed_label", "label_flip"]:
        if key in row:
            value = str(row.get(key, "")).strip().lower()
            return value in ["1", "true", "yes", "y"]

    original_col = pick_column(row, ["original_label", "orig_label", "baseline_label", "base_label"])
    perturbed_col = pick_column(row, ["perturbed_label", "new_label", "prediction_label", "variant_label"])

    if original_col and perturbed_col:
        return str(row.get(original_col)).strip() != str(row.get(perturbed_col)).strip()

    return False


def get_action(row: Dict[str, str]) -> str:
    for key in ["action", "perturbation", "perturbation_action", "method", "perturbation_type"]:
        if key in row and row[key]:
            return str(row[key])
    return "unknown"


def get_sample_id(row: Dict[str, str]) -> str:
    for key in ["sample_id", "id", "sample", "file_id", "source_id", "name"]:
        if key in row and row[key]:
            return str(row[key])
    return "unknown_sample"



def get_signed_delta_probability(row: Dict[str, str]) -> float:
    for key in [
        "delta_probability", "delta_prob", "prob_delta",
        "confidence_change", "delta_confidence", "probability_change",
    ]:
        if key in row and str(row.get(key, "")).strip() != "":
            return to_float(row.get(key))

    original_col, perturbed_col = detect_probability_columns(row)
    if original_col and perturbed_col:
        return to_float(row.get(perturbed_col)) - to_float(row.get(original_col))

    return 0.0


def first_value(row: Dict[str, str], keys: List[str]) -> Optional[str]:
    lower_map = {key.lower(): key for key in row.keys()}
    for key in keys:
        actual_key = lower_map.get(key.lower())
        if actual_key is not None:
            value = row.get(actual_key)
            if value is not None and str(value).strip() != "":
                return str(value).strip()
    return None


def optional_float(row: Dict[str, str], keys: List[str]) -> Optional[float]:
    value = first_value(row, keys)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def optional_int(row: Dict[str, str], keys: List[str]) -> Optional[int]:
    value = optional_float(row, keys)
    return int(value) if value is not None else None


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def base_action_name(row: Dict[str, str]) -> str:
    return re.sub(r"__c\d+$", "", get_action(row))


def is_scored(row: Dict[str, str]) -> bool:
    status = str(row.get("status", "")).strip().lower()
    if status and status != "success":
        return False
    original_col, perturbed_col = detect_probability_columns(row)
    return bool(original_col and perturbed_col and str(row.get(perturbed_col, "")).strip())


def mean_or_none(values: List[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def matching_prediction_rows(
    prediction_rows: List[Dict[str, str]],
    action: str,
    budget: Optional[str],
) -> List[Dict[str, str]]:
    matches = [row for row in prediction_rows if base_action_name(row) == action]
    if budget is not None:
        matches = [row for row in matches if str(row.get("budget", "")).strip() == budget]
    return matches


def synthesize_action_rows(prediction_rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    grouped: Dict[Tuple[str, str], List[Dict[str, str]]] = {}
    for row in prediction_rows:
        key = (base_action_name(row), str(row.get("budget", "")).strip())
        grouped.setdefault(key, []).append(row)

    summaries: List[Dict[str, str]] = []
    for (action, budget), rows in sorted(grouped.items()):
        scored_rows = [row for row in rows if is_scored(row)]
        summary = {
            "action": action,
            "attempted": str(len(rows)),
            "successful": str(len(scored_rows)),
            "failed": str(len(rows) - len(scored_rows)),
            "flips": str(sum(is_flip(row) for row in scored_rows)),
        }
        if budget:
            summary["budget"] = budget
        if any("attack_success" in row for row in scored_rows):
            summary["attack_successes"] = str(sum(truthy(row.get("attack_success")) for row in scored_rows))
        summaries.append(summary)
    return summaries


def normalize_action_metric(
    row: Dict[str, str],
    prediction_rows: List[Dict[str, str]],
) -> Dict[str, Any]:
    action = first_value(row, ["action", "perturbation", "method"]) or "unknown"
    budget = first_value(row, ["budget"])
    matching_rows = matching_prediction_rows(prediction_rows, action, budget)
    scored_rows = [item for item in matching_rows if is_scored(item)]

    count = optional_int(row, ["count", "variants", "num_variants"])
    attempted = optional_int(row, ["attempted"])
    successful = optional_int(row, ["successful", "scored"])
    failed = optional_int(row, ["failed"])

    if attempted is None:
        attempted = count if count is not None else len(matching_rows)
    if successful is None:
        if attempted is not None and failed is not None:
            successful = max(attempted - failed, 0)
        elif count is not None:
            successful = count
        else:
            successful = len(scored_rows)
    if failed is None:
        failed = max(attempted - successful, 0) if attempted is not None and successful is not None else None

    flips = optional_int(row, ["flips", "flip_count"])
    if flips is None:
        flips = sum(is_flip(item) for item in scored_rows)

    attack_successes = optional_int(row, ["attack_successes", "attack_success_count"])
    if attack_successes is None and any("attack_success" in item for item in scored_rows):
        attack_successes = sum(truthy(item.get("attack_success")) for item in scored_rows)

    deltas = [get_signed_delta_probability(item) for item in scored_rows]
    abs_deltas = [abs(value) for value in deltas]
    node_deltas = [to_float(item.get("delta_nodes")) for item in scored_rows if str(item.get("delta_nodes", "")).strip()]
    edge_deltas = [to_float(item.get("delta_edges")) for item in scored_rows if str(item.get("delta_edges", "")).strip()]
    applied_counts = [to_float(item.get("applied_count")) for item in scored_rows if str(item.get("applied_count", "")).strip()]

    mean_delta = optional_float(row, ["mean_delta_probability", "avg_delta_prob", "avg_confidence_change"])
    mean_abs_delta = optional_float(row, ["mean_absolute_delta_probability", "avg_absolute_delta_prob"])
    max_abs_delta = optional_float(row, ["max_absolute_delta_probability", "max_absolute_delta_prob"])
    max_delta = optional_float(row, ["max_delta_probability", "max_delta_prob", "max_confidence_change"])
    avg_delta_nodes = optional_float(row, ["avg_delta_nodes", "avg_node_delta", "mean_delta_nodes"])
    avg_delta_edges = optional_float(row, ["avg_delta_edges", "avg_edge_delta", "mean_delta_edges"])
    avg_applied = optional_float(row, ["mean_applied_count", "avg_applied_count"])

    if max_abs_delta is None:
        if abs_deltas:
            max_abs_delta = max(abs_deltas)
        elif max_delta is not None:
            max_abs_delta = abs(max_delta)

    scored = successful if successful is not None else len(scored_rows)
    return {
        "action": action,
        "budget": budget or "All",
        "attempted": attempted,
        "scored": scored,
        "failed": failed,
        "coverage_rate": scored / attempted if attempted else None,
        "flips": flips,
        "flip_rate": flips / scored if scored else None,
        "attack_successes": attack_successes,
        "attack_success_rate": attack_successes / scored if attack_successes is not None and scored else None,
        "mean_delta": mean_delta if mean_delta is not None else mean_or_none(deltas),
        "mean_abs_delta": mean_abs_delta if mean_abs_delta is not None else mean_or_none(abs_deltas),
        "max_abs_delta": max_abs_delta,
        "avg_delta_nodes": avg_delta_nodes if avg_delta_nodes is not None else mean_or_none(node_deltas),
        "avg_delta_edges": avg_delta_edges if avg_delta_edges is not None else mean_or_none(edge_deltas),
        "avg_applied": avg_applied if avg_applied is not None else mean_or_none(applied_counts),
    }


def normalized_action_metrics(
    action_rows: List[Dict[str, str]],
    prediction_rows: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    source_rows = action_rows or synthesize_action_rows(prediction_rows)
    return [normalize_action_metric(row, prediction_rows) for row in source_rows]


def format_count(value: Optional[int]) -> str:
    return "N/A" if value is None else str(value)


def format_rate(value: Optional[float]) -> str:
    return "N/A" if value is None else f"{value * 100:.2f}%"


def format_metric(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"{value:+.6f}" if abs(value) >= 0.0001 or value == 0 else f"{value:+.3e}"


def format_magnitude(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"{value:.6f}" if abs(value) >= 0.0001 or value == 0 else f"{value:.3e}"


def table_cell(value: Any, width: int, right: bool = False) -> str:
    text = str(value)
    if len(text) > width:
        text = text[: max(width - 3, 1)] + ("..." if width >= 4 else "")
    return text.rjust(width) if right else text.ljust(width)


def print_metric_table(headers: List[str], rows: List[List[str]], widths: List[int], right_from: int = 2) -> None:
    print(" ".join(table_cell(value, width, right=index >= right_from) for index, (value, width) in enumerate(zip(headers, widths))))
    print("-" * (sum(widths) + len(widths) - 1))
    for row in rows:
        print(" ".join(table_cell(value, width, right=index >= right_from) for index, (value, width) in enumerate(zip(row, widths))))


def print_normalized_impact_tables(metrics: List[Dict[str, Any]]) -> None:
    metrics = sorted(metrics, key=lambda item: (str(item["action"]), str(item["budget"])))

    execution_rows = [
        [
            metric["action"],
            metric["budget"],
            format_count(metric["attempted"]),
            format_count(metric["scored"]),
            format_count(metric["failed"]),
            format_count(metric["flips"]),
            format_rate(metric["flip_rate"]),
            format_count(metric["attack_successes"]),
            format_rate(metric["attack_success_rate"]),
        ]
        for metric in metrics
    ]

    print("\nExecution and outcome metrics")
    print_metric_table(
        ["Action", "Budget", "Attempted", "Scored", "Failed", "Flips", "FlipRate", "AtkSucc", "ASR"],
        execution_rows,
        [30, 6, 9, 7, 6, 5, 8, 7, 8],
    )

    probability_rows = [
        [
            metric["action"],
            metric["budget"],
            format_metric(metric["mean_delta"]),
            format_magnitude(metric["mean_abs_delta"]),
            format_magnitude(metric["max_abs_delta"]),
        ]
        for metric in metrics
    ]

    print("\nProbability-impact metrics")
    print_metric_table(
        ["Action", "Budget", "MeanDeltaP", "MeanAbsDeltaP", "MaxAbsDeltaP"],
        probability_rows,
        [30, 6, 12, 13, 12],
    )

    graph_rows = [
        [
            metric["action"],
            metric["budget"],
            format_magnitude(metric["avg_delta_nodes"]),
            format_magnitude(metric["avg_delta_edges"]),
            format_magnitude(metric["avg_applied"]),
        ]
        for metric in metrics
    ]

    print("\nGraph-impact metrics")
    print_metric_table(
        ["Action", "Budget", "AvgDeltaNodes", "AvgDeltaEdges", "AvgApplied"],
        graph_rows,
        [30, 6, 13, 13, 10],
    )


def build_overall_metrics(data: Dict[str, Any]) -> Dict[str, Any]:
    prediction_rows = data["prediction_rows"]
    manifest_rows = data["manifest_rows"]
    baseline_rows = data["baseline_rows"]

    samples = set()
    for row in prediction_rows or baseline_rows or manifest_rows:
        samples.add(get_sample_id(row))

    prediction_count = len(prediction_rows)
    variants = len(prediction_rows) if prediction_rows else len(manifest_rows)
    flips = sum(1 for row in prediction_rows if is_flip(row))
    flip_rate = flips / prediction_count * 100 if prediction_count else 0.0
    max_delta = max([get_delta_probability(row) for row in prediction_rows], default=0.0)

    return {
        "samples": len(samples),
        "perturbed_variants": variants,
        "prediction_rows": prediction_count,
        "flips": flips,
        "flip_rate": flip_rate,
        "max_delta": max_delta,
    }


# ============================================================
# Main pages
# ============================================================

def show_main_menu() -> None:
    print_header("DeepWuKong Robustness Testing Console")
    print("1. Run Full Test")
    print("2. Run Smoke Test")
    print("3. Results Summary")
    print("4. Perturbation Impact Analysis")
    print("5. Sample Detail Viewer")
    print("6. Open Web Dashboard")
    print("0. Exit")
    print("=" * 72)


def run_test() -> None:
    print_header("Run Full Test")

    slow_print([
        "Full Test Mode",
        "",
        "This test runs a live DeepWuKong perturbation experiment.",
        "The workflow is:",
        "1. Load every C/C++ source file under input_sources",
        "2. Apply all implemented source-level perturbation actions",
        "3. Run baseline and perturbed DeepWuKong predictions",
        f"4. Run random graph and Winner-XFG actions at nested budgets {GRAPH_BUDGET_LABEL}",
        "5. Repeat graph actions with 10 fixed seeds and generate integrated reports",
        "The current 60-sample Full Test takes about 5-6 hours; source-level inference dominates runtime.",
        "",
    ])

    if START_TEST_COMMAND:
        print("Running configured full test command:")
        print(" ".join(START_TEST_COMMAND))
        print("-" * 72)
        try:
            subprocess.run(START_TEST_COMMAND, cwd=PROJECT_ROOT, check=True)
            print("\nFull test command completed successfully.")
        except subprocess.CalledProcessError as e:
            print("\nFull test command failed.")
            print(f"Return code: {e.returncode}")
            print("You can still inspect prepared outputs if they exist.")
    else:
        print("No full test command is configured; using prepared result files.")
        time.sleep(0.8)

    run_dir = get_default_run_dir()
    data = load_run_data(run_dir)
    print_data_location(data)

    metrics = build_overall_metrics(data)
    print("\nTest Completed")
    print("-" * 72)
    print(f"Run folder:              {run_dir.name if run_dir else 'Not found'}")
    print(f"Samples detected:        {metrics['samples']}")
    print(f"Perturbed variants:      {metrics['perturbed_variants']}")
    print(f"Prediction rows:         {metrics['prediction_rows']}")
    print(f"Prediction flips:        {metrics['flips']}")
    print(f"Flip rate:               {metrics['flip_rate']:.2f}%")
    print(f"Max confidence change:   {metrics['max_delta']:.6f}")

    pause("Press Enter to open the detailed results menu...")
    results_menu(default_run_dir=run_dir)


def run_quick_test() -> None:
    print_header("Run Smoke Test")
    slow_print([
        "Quick Test Mode",
        "",
        "This smoke test first verifies the separately downloaded runtime TAR",
        "using its exact byte count and SHA-256 checksum. It then runs one live",
        "baseline prediction without generating perturbations or a result folder.",
        "",
    ])

    if not QUICK_TEST_COMMAND:
        print("No quick test command is configured.")
        pause()
        return

    print("Running quick test command:")
    print(" ".join(QUICK_TEST_COMMAND))
    print("-" * 72)
    try:
        subprocess.run(QUICK_TEST_COMMAND, cwd=PROJECT_ROOT, check=True)
        print("\nQuick test passed. The live inference pipeline is available.")
    except subprocess.CalledProcessError as error:
        print("\nQuick test failed. Check the messages above for the failing dependency or stage.")
        print(f"Return code: {error.returncode}")
    pause()


def show_results_summary(run_dir: Optional[Path] = None) -> None:
    if run_dir is None:
        run_dir = choose_run_dir("Results Summary - Select Run")
        if run_dir is None:
            return

    print_header(f"Results Summary - {run_dir.name}")
    data = load_run_data(run_dir)
    print_data_location(data)
    metrics = build_overall_metrics(data)

    print("\nOverall Robustness Summary")
    print("-" * 72)
    print(f"Total samples detected:        {metrics['samples']}")
    print(f"Total perturbed variants:      {metrics['perturbed_variants']}")
    print(f"Completed prediction rows:     {metrics['prediction_rows']}")
    print(f"Prediction flips detected:     {metrics['flips']}")
    print(f"Flip rate:                     {metrics['flip_rate']:.2f}%")
    print(f"Maximum confidence change:     {metrics['max_delta']:.6f}")

    if metrics["prediction_rows"] == 0:
        print("\nNo prediction comparison file was found for this run.")
    elif metrics["flips"] == 0:
        print("\nInterpretation:")
        print("No final label flip was detected in this run.")
        print("However, confidence change is still useful for analysing model sensitivity.")
    else:
        print("\nInterpretation:")
        print("At least one perturbation changed the final prediction label.")
        print("These samples should be inspected in detail.")

    pause()


def show_perturbation_impact_analysis(run_dir: Optional[Path] = None) -> None:
    if run_dir is None:
        run_dir = choose_run_dir("Perturbation Impact Analysis - Select Run")
        if run_dir is None:
            return

    print_header(f"Perturbation Impact Analysis - {run_dir.name}")
    data = load_run_data(run_dir)
    action_rows = data["action_rows"]
    prediction_rows = data["prediction_rows"]

    if not action_rows and not prediction_rows:
        print("No action summary or prediction comparison file was found for this run.")
        pause()
        return

    if action_rows:
        print("Action summary file detected.")
    else:
        print("No action summary file detected. Metrics are derived from prediction comparison rows.")

    print("-" * 72)
    print("Using normalized output format for all run folders.")
    print("This keeps the table headers consistent across code-level, graph-level, and attack runs.")

    metrics = normalized_action_metrics(action_rows, prediction_rows)
    print_normalized_impact_tables(metrics)

    print("\nMetric definitions:")
    print("- Attempted = total perturbation variants attempted.")
    print("- Scored = variants with successful prediction results.")
    print("- Failed = attempted variants without successful prediction results.")
    print("- FlipRate = flips / scored.")
    print("- ASR = attack success rate, shown as N/A if the run does not record attack success.")
    print("- MeanDeltaP = average signed probability change.")
    print("- MeanAbsDeltaP and MaxAbsDeltaP show the magnitude of confidence change.")
    print("- Graph metrics are N/A if the selected run does not record node/edge changes.")
    pause()


def show_sample_detail_viewer(run_dir: Optional[Path] = None) -> None:
    if run_dir is None:
        run_dir = choose_run_dir("Sample Detail Viewer - Select Run")
        if run_dir is None:
            return

    print_header(f"Sample Detail Viewer - {run_dir.name}")
    data = load_run_data(run_dir)
    rows = data["prediction_rows"] or data["manifest_rows"]

    if not rows:
        print("No sample-level result or manifest rows found for this run.")
        pause()
        return

    print("Available samples:")
    print("-" * 72)
    for idx, row in enumerate(rows[:20], start=1):
        sample_id = get_sample_id(row)
        action = get_action(row)
        flip = "Yes" if is_flip(row) else "No"
        delta = get_delta_probability(row)
        print(f"{idx:2d}. {sample_id[:35]:35} | {action[:22]:22} | Flip: {flip:3} | Delta: {delta:.6f}")

    print("\n0. Back")
    choice = input("\nSelect a sample: ").strip()
    if choice == "0":
        return

    try:
        idx = int(choice)
        if not 1 <= idx <= min(20, len(rows)):
            raise ValueError
    except ValueError:
        print("Invalid sample selection.")
        pause()
        return

    row = rows[idx - 1]
    print_header(f"Sample Detail - {run_dir.name}")

    print(f"Sample ID:          {get_sample_id(row)}")
    print(f"Perturbation:       {get_action(row)}")
    print(f"Prediction flip:    {'Yes' if is_flip(row) else 'No'}")
    print(f"Confidence change:  {get_delta_probability(row):.6f}")

    original_label_col = pick_column(row, ["original_label", "orig_label", "baseline_label"])
    perturbed_label_col = pick_column(row, ["perturbed_label", "new_label", "prediction_label"])
    original_prob_col, perturbed_prob_col = detect_probability_columns(row)

    if original_label_col:
        print(f"Original label:     {row.get(original_label_col)}")
    if perturbed_label_col:
        print(f"Perturbed label:    {row.get(perturbed_label_col)}")
    if original_prob_col:
        print(f"Original score:     {row.get(original_prob_col)}")
    if perturbed_prob_col:
        print(f"Perturbed score:    {row.get(perturbed_prob_col)}")

    print("\nRaw row data:")
    print("-" * 72)
    for key, value in row.items():
        print(f"{key}: {value}")

    pause()


def open_web_dashboard() -> None:
    options = [
        ("Experiment dashboard index", EXPERIMENT_DASHBOARD_HTML),
        ("Function-scoped PDG atlas", PDG_ATLAS_HTML),
    ]
    graph_dashboards = sorted(
        (PROJECT_ROOT / "outputs").glob("run_*/graph_comparison/dashboard.html"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if graph_dashboards:
        options.append(("Latest random vs Winner-XFG comparison", graph_dashboards[0]))
    while True:
        print_header("Open Web Dashboard")
        for index, (label, _) in enumerate(options, start=1):
            print(f"{index}. {label}")
        print("0. Back")

        choice = input("\nSelect a dashboard: ").strip()
        if choice == "0":
            return
        try:
            selected_index = int(choice)
        except ValueError:
            selected_index = -1
        if not 1 <= selected_index <= len(options):
            print("Invalid dashboard selection.")
            continue
        label, dashboard_path = options[selected_index - 1]

        if not dashboard_path.exists():
            print(f"\nERROR: {label} HTML file was not found:")
            print(dashboard_path)
            continue

        dashboard_base_url = os.environ.get("ALMOND_DASHBOARD_BASE_URL")
        if dashboard_base_url:
            relative_path = dashboard_path.relative_to(PROJECT_ROOT).as_posix()
            dashboard_url = f"{dashboard_base_url}/{relative_path}"
            browser_bridge_url = os.environ.get("ALMOND_BROWSER_BRIDGE_URL")
            if browser_bridge_url:
                try:
                    with urlopen(f"{browser_bridge_url}?{urlencode({'url': dashboard_url})}", timeout=3) as response:
                        if response.status != 200:
                            raise RuntimeError(f"bridge responded with HTTP {response.status}")
                    print(f"\nOpened {label} in the default host browser.")
                except Exception as e:
                    print(f"\nCould not open the default browser automatically: {e}")
                    print(f"Open this URL manually: {dashboard_url}")
            else:
                print(f"\n{label} is available on the host at:")
                print(dashboard_url)
                print("Use .\\start-almond.ps1 to open dashboards automatically.")
            continue

        try:
            webbrowser.open(dashboard_path.resolve().as_uri())
            print(f"\nOpened {label}.")
        except Exception as e:
            print("\nFailed to open browser automatically.")
            print(f"Error: {e}")
            print("Please open the file manually.")


# ============================================================
# Results submenu after Run Full Test
# ============================================================

def show_results_menu(run_dir: Optional[Path]) -> None:
    title = "Test Completed - Results Menu"
    if run_dir:
        title += f" ({run_dir.name})"
    print_header(title)
    print("1. Overall Robustness Summary")
    print("2. Perturbation Impact Analysis")
    print("3. Sample-Level Prediction Table")
    print("4. Confidence Change Ranking")
    print("5. Sample Detail Viewer")
    print("6. Open Web Dashboard")
    print("7. Change Run Folder")
    print("0. Back to Main Menu")
    print("=" * 72)


def show_sample_level_prediction_table(run_dir: Optional[Path]) -> None:
    if run_dir is None:
        print("No run folder selected.")
        pause()
        return

    print_header(f"Sample-Level Prediction Table - {run_dir.name}")
    rows = load_run_data(run_dir)["prediction_rows"]

    if not rows:
        print("No prediction comparison rows found.")
        pause()
        return

    print("Sample ID                           Action                   Flip   Delta")
    print("-" * 72)
    for row in rows[:20]:
        sample_id = get_sample_id(row)[:35]
        action = get_action(row)[:22]
        flip = "Yes" if is_flip(row) else "No"
        delta = get_delta_probability(row)
        print(f"{sample_id:35} {action:22} {flip:5} {delta:.6f}")

    print("\nShowing first 20 rows only.")
    pause()


def show_confidence_change_ranking(run_dir: Optional[Path]) -> None:
    if run_dir is None:
        print("No run folder selected.")
        pause()
        return

    print_header(f"Confidence Change Ranking - {run_dir.name}")
    rows = load_run_data(run_dir)["prediction_rows"]

    if not rows:
        print("No prediction comparison rows found.")
        pause()
        return

    ranked = sorted(rows, key=get_delta_probability, reverse=True)

    print("Rank   Sample ID                         Action                   Flip   Delta")
    print("-" * 72)
    for i, row in enumerate(ranked[:10], start=1):
        sample_id = get_sample_id(row)[:32]
        action = get_action(row)[:22]
        flip = "Yes" if is_flip(row) else "No"
        delta = get_delta_probability(row)
        print(f"{i:4d}   {sample_id:32} {action:22} {flip:5} {delta:.6f}")

    print("\nInterpretation:")
    print("These are the samples where perturbations changed model confidence most.")
    pause()


def results_menu(default_run_dir: Optional[Path] = None) -> None:
    run_dir = default_run_dir or get_default_run_dir()

    while True:
        show_results_menu(run_dir)
        choice = input("Select an option: ").strip()

        if choice == "1":
            show_results_summary(run_dir)
        elif choice == "2":
            show_perturbation_impact_analysis(run_dir)
        elif choice == "3":
            show_sample_level_prediction_table(run_dir)
        elif choice == "4":
            show_confidence_change_ranking(run_dir)
        elif choice == "5":
            show_sample_detail_viewer(run_dir)
        elif choice == "6":
            open_web_dashboard()
        elif choice == "7":
            selected = choose_run_dir("Change Run Folder")
            if selected is not None:
                run_dir = selected
        elif choice == "0":
            break
        else:
            print("Invalid option.")
            pause()


# ============================================================
# Entry point
# ============================================================

def main() -> None:
    while True:
        show_main_menu()
        choice = input("Select an option: ").strip()

        if choice == "1":
            run_test()
        elif choice == "2":
            run_quick_test()
        elif choice == "3":
            show_results_summary()
        elif choice == "4":
            show_perturbation_impact_analysis()
        elif choice == "5":
            show_sample_detail_viewer()
        elif choice == "6":
            open_web_dashboard()
        elif choice == "0":
            print("Goodbye.")
            break
        else:
            print("Invalid option.")
            pause()


if __name__ == "__main__":
    main()
