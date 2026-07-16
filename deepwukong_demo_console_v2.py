#!/usr/bin/env python3
"""
DeepWuKong Robustness Testing Demo Console
T17A Almond - COMP9900

This console is designed for progress-check presentation.
It provides:
1. Run Quick Demo
2. Results Summary
3. Perturbation Impact Analysis
4. Sample Detail Viewer
5. Open Web Dashboard
0. Exit

After running Quick Demo, it enters a detailed Results Menu.
"""

from __future__ import annotations

import csv
import os
import sys
import time
import json
import webbrowser
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


# ============================================================
# Configuration section
# You can edit these values if your folder names are different.
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent

# If you have a known run folder, set it here, e.g. "run_20260710".
# If set to None, the program will try to find the newest folder under outputs/.
RUN_ID: Optional[str] = None

# Optional real quick demo command.
# Keep as None for a stable presentation demo that loads prepared results.
# Example:
# QUICK_DEMO_COMMAND = [sys.executable, "demo_b/run_quick_demo.py"]
QUICK_DEMO_COMMAND: Optional[List[str]] = None

# Dashboard URL or local file.
# Change this to your real frontend address if needed.
WEB_DASHBOARD_URL = "http://localhost:5173"

# Expected output filenames. The program will search for these under outputs/<run_id>/.
PREDICTION_COMPARISON_NAMES = [
    "prediction_comparison.csv",
    "comparison.csv",
    "results.csv",
    "demo_results.csv",
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
# Utility functions
# ============================================================

def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def pause(message: str = "Press Enter to continue...") -> None:
    input(f"\n{message}")


def slow_print(lines: List[str], delay: float = 0.03) -> None:
    for line in lines:
        print(line)
        time.sleep(delay)


def print_header(title: str) -> None:
    clear_screen()
    print("=" * 72)
    print(f" {title}")
    print("=" * 72)


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def find_newest_run_dir() -> Optional[Path]:
    outputs_dir = PROJECT_ROOT / "outputs"
    if not outputs_dir.exists():
        return None

    candidates = [p for p in outputs_dir.iterdir() if p.is_dir()]
    if not candidates:
        return None

    # Prefer folders starting with run_, otherwise newest folder.
    run_candidates = [p for p in candidates if p.name.lower().startswith("run")]
    candidates = run_candidates or candidates
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def get_run_dir() -> Optional[Path]:
    if RUN_ID:
        p = PROJECT_ROOT / "outputs" / RUN_ID
        return p if p.exists() else None
    return find_newest_run_dir()


def find_file(run_dir: Optional[Path], names: List[str]) -> Optional[Path]:
    if run_dir is None:
        return None

    # First search directly in run_dir.
    for name in names:
        p = run_dir / name
        if p.exists():
            return p

    # Then search recursively.
    for name in names:
        matches = list(run_dir.rglob(name))
        if matches:
            return matches[0]

    return None


def find_manifest_file(run_dir: Optional[Path]) -> Optional[Path]:
    # First search in artifacts/perturbed_sources/<run_id>/.
    if run_dir is not None:
        artifacts_manifest_dir = PROJECT_ROOT / "artifacts" / "perturbed_sources" / run_dir.name
        for name in MANIFEST_NAMES:
            p = artifacts_manifest_dir / name
            if p.exists():
                return p

    # Search under artifacts.
    artifacts_dir = PROJECT_ROOT / "artifacts"
    if artifacts_dir.exists():
        for name in MANIFEST_NAMES:
            matches = list(artifacts_dir.rglob(name))
            if matches:
                matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                return matches[0]

    # Search under run_dir.
    return find_file(run_dir, MANIFEST_NAMES)


def to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(str(value).strip())
    except ValueError:
        return default


def to_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(float(str(value).strip()))
    except ValueError:
        return default


def pick_column(row: Dict[str, str], options: List[str]) -> Optional[str]:
    lowered = {k.lower(): k for k in row.keys()}
    for option in options:
        key = lowered.get(option.lower())
        if key is not None:
            return key
    return None


def detect_probability_columns(rows: List[Dict[str, str]]) -> tuple[Optional[str], Optional[str]]:
    if not rows:
        return None, None

    first = rows[0]
    original_options = [
        "original_prob", "orig_prob", "baseline_prob", "original_probability",
        "baseline_probability", "orig_probability", "original_score", "baseline_score"
    ]
    perturbed_options = [
        "perturbed_prob", "pert_prob", "new_prob", "perturbed_probability",
        "prediction_prob", "perturbed_score", "new_score"
    ]

    return pick_column(first, original_options), pick_column(first, perturbed_options)


def get_delta_probability(row: Dict[str, str]) -> float:
    # Prefer explicit delta fields.
    for key in ["delta_prob", "prob_delta", "confidence_change", "delta_confidence", "probability_change"]:
        if key in row:
            return abs(to_float(row.get(key)))

    original_col, perturbed_col = detect_probability_columns([row])
    if original_col and perturbed_col:
        return abs(to_float(row.get(perturbed_col)) - to_float(row.get(original_col)))

    return 0.0


def is_flip(row: Dict[str, str]) -> bool:
    # Prefer explicit flip field.
    for key in ["flip", "prediction_flip", "changed_label", "label_flip"]:
        if key in row:
            value = str(row.get(key, "")).strip().lower()
            return value in ["1", "true", "yes", "y"]

    # Infer from labels if possible.
    original_col = pick_column(row, ["original_label", "orig_label", "baseline_label"])
    perturbed_col = pick_column(row, ["perturbed_label", "new_label", "prediction_label"])
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


def load_demo_data() -> Dict[str, Any]:
    run_dir = get_run_dir()

    prediction_file = find_file(run_dir, PREDICTION_COMPARISON_NAMES)
    action_file = find_file(run_dir, ACTION_SUMMARY_NAMES)
    baseline_file = find_file(run_dir, BASELINE_SUMMARY_NAMES)
    manifest_file = find_manifest_file(run_dir)

    prediction_rows = read_csv(prediction_file) if prediction_file else []
    action_rows = read_csv(action_file) if action_file else []
    baseline_rows = read_csv(baseline_file) if baseline_file else []
    manifest_rows = read_csv(manifest_file) if manifest_file else []

    return {
        "run_dir": run_dir,
        "prediction_file": prediction_file,
        "action_file": action_file,
        "baseline_file": baseline_file,
        "manifest_file": manifest_file,
        "prediction_rows": prediction_rows,
        "action_rows": action_rows,
        "baseline_rows": baseline_rows,
        "manifest_rows": manifest_rows,
    }


def print_data_location(data: Dict[str, Any]) -> None:
    print("\nDetected data files:")
    print(f"- Run directory:          {data['run_dir'] if data['run_dir'] else 'Not found'}")
    print(f"- Prediction comparison:  {data['prediction_file'] if data['prediction_file'] else 'Not found'}")
    print(f"- Action summary:         {data['action_file'] if data['action_file'] else 'Not found'}")
    print(f"- Baseline summary:       {data['baseline_file'] if data['baseline_file'] else 'Not found'}")
    print(f"- Perturbation manifest:  {data['manifest_file'] if data['manifest_file'] else 'Not found'}")


def build_overall_metrics(data: Dict[str, Any]) -> Dict[str, Any]:
    prediction_rows = data["prediction_rows"]
    manifest_rows = data["manifest_rows"]
    baseline_rows = data["baseline_rows"]

    samples = set()
    for row in prediction_rows or baseline_rows or manifest_rows:
        samples.add(get_sample_id(row))

    total_predictions = len(prediction_rows)
    total_variants = len(prediction_rows) if prediction_rows else len(manifest_rows)
    flips = sum(1 for row in prediction_rows if is_flip(row))
    max_delta = max([get_delta_probability(row) for row in prediction_rows], default=0.0)

    flip_rate = (flips / total_predictions * 100.0) if total_predictions else 0.0

    return {
        "samples": len(samples),
        "prediction_rows": total_predictions,
        "perturbed_variants": total_variants,
        "flips": flips,
        "flip_rate": flip_rate,
        "max_delta": max_delta,
        "baseline_rows": len(baseline_rows),
        "manifest_rows": len(manifest_rows),
    }


# ============================================================
# Main menu pages
# ============================================================

def show_main_menu() -> None:
    print_header("DeepWuKong Robustness Testing Demo Console")
    print("1. Run Quick Demo")
    print("2. Results Summary")
    print("3. Perturbation Impact Analysis")
    print("4. Sample Detail Viewer")
    print("5. Open Web Dashboard")
    print("0. Exit")
    print("=" * 72)


def run_quick_demo() -> None:
    print_header("Run Quick Demo")

    slow_print([
        "Quick Demo Mode",
        "",
        "This demo uses a small prepared dataset to keep the presentation fast.",
        "The workflow is:",
        "1. Load original C/C++ samples",
        "2. Apply source-level perturbations",
        "3. Run or load DeepWuKong predictions",
        "4. Compare original and perturbed predictions",
        "5. Generate robustness analysis outputs",
        "",
    ], delay=0.02)

    if QUICK_DEMO_COMMAND:
        print("Running configured quick demo command:")
        print(" ".join(QUICK_DEMO_COMMAND))
        print("-" * 72)
        try:
            subprocess.run(QUICK_DEMO_COMMAND, cwd=PROJECT_ROOT, check=True)
            print("\nQuick demo command completed successfully.")
        except subprocess.CalledProcessError as e:
            print("\nQuick demo command failed.")
            print(f"Return code: {e.returncode}")
            print("You can still inspect prepared outputs if they exist.")
    else:
        print("Presentation mode: using prepared result files.")
        print("No full DeepWuKong inference is executed here.")
        print("This keeps the live demo stable and fast.")
        time.sleep(1.0)

    data = load_demo_data()
    print_data_location(data)

    metrics = build_overall_metrics(data)
    print("\nQuick Demo Completed")
    print("-" * 72)
    print(f"Samples detected:        {metrics['samples']}")
    print(f"Perturbed variants:      {metrics['perturbed_variants']}")
    print(f"Prediction rows:         {metrics['prediction_rows']}")
    print(f"Prediction flips:        {metrics['flips']}")
    print(f"Flip rate:               {metrics['flip_rate']:.2f}%")
    print(f"Max confidence change:   {metrics['max_delta']:.6f}")

    pause("\nPress Enter to open the detailed results menu...")
    results_menu()


def show_results_summary() -> None:
    print_header("Results Summary")

    data = load_demo_data()
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
        print("\nNo prediction comparison file was found.")
        print("Please check your outputs folder or update the path configuration at the top of this script.")
    elif metrics["flips"] == 0:
        print("\nInterpretation:")
        print("No final label flip was detected in this prepared run.")
        print("However, confidence change is still useful for analysing model sensitivity.")
    else:
        print("\nInterpretation:")
        print("At least one perturbation changed the final prediction label.")
        print("These samples should be inspected carefully in the sample detail viewer.")

    pause()


def show_perturbation_impact_analysis() -> None:
    print_header("Perturbation Impact Analysis")

    data = load_demo_data()
    prediction_rows = data["prediction_rows"]
    action_rows = data["action_rows"]

    if action_rows:
        print("Action summary file detected. Showing available summary rows:")
        print("-" * 72)
        # Print a compact table using available columns.
        columns = list(action_rows[0].keys())[:6]
        print(" | ".join(columns))
        print("-" * 72)
        for row in action_rows[:15]:
            print(" | ".join(str(row.get(c, ""))[:20] for c in columns))
        pause()
        return

    if not prediction_rows:
        print("No prediction comparison rows found.")
        print("Cannot compute perturbation impact analysis yet.")
        pause()
        return

    grouped: Dict[str, Dict[str, Any]] = {}
    for row in prediction_rows:
        action = get_action(row)
        if action not in grouped:
            grouped[action] = {
                "count": 0,
                "flips": 0,
                "delta_sum": 0.0,
                "max_delta": 0.0,
            }
        delta = get_delta_probability(row)
        grouped[action]["count"] += 1
        grouped[action]["flips"] += 1 if is_flip(row) else 0
        grouped[action]["delta_sum"] += delta
        grouped[action]["max_delta"] = max(grouped[action]["max_delta"], delta)

    print("Action                         Variants   Flips   Avg ΔProb   Max ΔProb")
    print("-" * 72)
    for action, values in sorted(grouped.items(), key=lambda kv: kv[1]["max_delta"], reverse=True):
        count = values["count"]
        avg_delta = values["delta_sum"] / count if count else 0.0
        print(f"{action[:30]:30} {count:8d} {values['flips']:7d} {avg_delta:10.6f} {values['max_delta']:10.6f}")

    print("\nInterpretation:")
    print("This page compares which perturbation action caused larger prediction changes.")
    print("Even without label flips, a larger confidence change can indicate model sensitivity.")

    pause()


def show_sample_detail_viewer() -> None:
    print_header("Sample Detail Viewer")

    data = load_demo_data()
    prediction_rows = data["prediction_rows"]
    manifest_rows = data["manifest_rows"]

    rows = prediction_rows or manifest_rows
    if not rows:
        print("No sample-level result or manifest rows found.")
        print("Please generate demo outputs first, or update the file path configuration.")
        pause()
        return

    print("Available samples:")
    print("-" * 72)
    for idx, row in enumerate(rows[:20], start=1):
        sample_id = get_sample_id(row)
        action = get_action(row)
        delta = get_delta_probability(row)
        flip = "Yes" if is_flip(row) else "No"
        print(f"{idx:2d}. {sample_id[:35]:35} | {action[:22]:22} | Flip: {flip:3} | ΔProb: {delta:.6f}")

    print("\nChoose a sample number to inspect.")
    print("Enter 0 to go back.")
    choice = input("> ").strip()

    if choice == "0":
        return

    try:
        idx = int(choice)
        if not 1 <= idx <= min(20, len(rows)):
            raise ValueError
    except ValueError:
        print("Invalid choice.")
        pause()
        return

    row = rows[idx - 1]

    print_header("Sample Detail")
    print(f"Sample ID:     {get_sample_id(row)}")
    print(f"Perturbation:  {get_action(row)}")
    print(f"Prediction flip: {'Yes' if is_flip(row) else 'No'}")
    print(f"Confidence change: {get_delta_probability(row):.6f}")

    original_col = pick_column(row, ["original_label", "orig_label", "baseline_label"])
    perturbed_col = pick_column(row, ["perturbed_label", "new_label", "prediction_label"])
    original_prob_col, perturbed_prob_col = detect_probability_columns([row])

    if original_col:
        print(f"Original label:     {row.get(original_col)}")
    if perturbed_col:
        print(f"Perturbed label:    {row.get(perturbed_col)}")
    if original_prob_col:
        print(f"Original score:     {row.get(original_prob_col)}")
    if perturbed_prob_col:
        print(f"Perturbed score:    {row.get(perturbed_prob_col)}")

    print("\nRaw row data:")
    print("-" * 72)
    for key, value in row.items():
        print(f"{key}: {value}")

    print("\nNote:")
    print("If you want to show original vs perturbed code here, add source file paths")
    print("to your manifest or prediction comparison CSV, such as original_path and perturbed_path.")

    pause()


def open_web_dashboard() -> None:
    print_header("Open Web Dashboard")

    print("Opening dashboard...")
    print(f"URL: {WEB_DASHBOARD_URL}")
    print("\nThe dashboard can be used to show:")
    print("- summary cards")
    print("- perturbation comparison charts")
    print("- sample-level prediction table")
    print("- confidence change ranking")
    print("- original vs perturbed code viewer")
    print("- graph / Joern artifact visualisation")

    try:
        webbrowser.open(WEB_DASHBOARD_URL)
        print("\nBrowser open command sent.")
    except Exception as e:
        print("\nFailed to open browser automatically.")
        print(f"Error: {e}")
        print("Please open the URL manually.")

    pause()


# ============================================================
# Results submenu after Quick Demo
# ============================================================

def show_results_menu() -> None:
    print_header("Quick Demo Completed - Results Menu")
    print("1. Overall Robustness Summary")
    print("2. Perturbation Impact Analysis")
    print("3. Sample-Level Prediction Table")
    print("4. Confidence Change Ranking")
    print("5. Sample Detail Viewer")
    print("6. Open Web Dashboard")
    print("0. Back to Main Menu")
    print("=" * 72)


def show_sample_level_prediction_table() -> None:
    print_header("Sample-Level Prediction Table")

    data = load_demo_data()
    rows = data["prediction_rows"]
    if not rows:
        print("No prediction comparison rows found.")
        pause()
        return

    print("Sample ID                           Action                   Flip   ΔProb")
    print("-" * 72)
    for row in rows[:20]:
        sample_id = get_sample_id(row)[:35]
        action = get_action(row)[:22]
        flip = "Yes" if is_flip(row) else "No"
        delta = get_delta_probability(row)
        print(f"{sample_id:35} {action:22} {flip:5} {delta:.6f}")

    print("\nShowing first 20 rows only for terminal readability.")
    pause()


def show_confidence_change_ranking() -> None:
    print_header("Confidence Change Ranking")

    data = load_demo_data()
    rows = data["prediction_rows"]
    if not rows:
        print("No prediction comparison rows found.")
        pause()
        return

    ranked = sorted(rows, key=get_delta_probability, reverse=True)

    print("Rank   Sample ID                          Action                   Flip   ΔProb")
    print("-" * 72)
    for i, row in enumerate(ranked[:10], start=1):
        sample_id = get_sample_id(row)[:33]
        action = get_action(row)[:22]
        flip = "Yes" if is_flip(row) else "No"
        delta = get_delta_probability(row)
        print(f"{i:4d}   {sample_id:33} {action:22} {flip:5} {delta:.6f}")

    print("\nInterpretation:")
    print("These are the samples where perturbations changed the model confidence most.")
    print("They are useful to inspect even when the final prediction label does not flip.")
    pause()


def results_menu() -> None:
    while True:
        show_results_menu()
        choice = input("Select an option: ").strip()

        if choice == "1":
            show_results_summary()
        elif choice == "2":
            show_perturbation_impact_analysis()
        elif choice == "3":
            show_sample_level_prediction_table()
        elif choice == "4":
            show_confidence_change_ranking()
        elif choice == "5":
            show_sample_detail_viewer()
        elif choice == "6":
            open_web_dashboard()
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
            run_quick_demo()
        elif choice == "2":
            show_results_summary()
        elif choice == "3":
            show_perturbation_impact_analysis()
        elif choice == "4":
            show_sample_detail_viewer()
        elif choice == "5":
            open_web_dashboard()
        elif choice == "0":
            print("Goodbye.")
            break
        else:
            print("Invalid option.")
            pause()


if __name__ == "__main__":
    main()
