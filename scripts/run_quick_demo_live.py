#!/usr/bin/env python3
"""Run a small, real DeepWuKong perturbation experiment inside the runtime image."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from demo_b.code.code_perturbations import OPERATORS


SOURCE_PATH = PROJECT_ROOT / "input_sources" / "cwe119" / "vulnerable" / "05_vulnerable_32.cpp"
CHECKPOINT_PATH = PROJECT_ROOT / "baselines" / "deepwukong" / "models" / "deepwukong" / "deepwukong_cwe119_best.ckpt"
INFERENCE_SCRIPT = PROJECT_ROOT / "baselines" / "deepwukong" / "scripts" / "infer_single_source.py"
ACTION_NAMES = ("dead_statement", "xfg_targeted_dead_code")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def numeric(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def run_inference(source_path: Path, output_dir: Path, sample_id: str) -> tuple[dict[str, Any] | None, str | None]:
    command = [
        sys.executable,
        str(INFERENCE_SCRIPT),
        "--source",
        str(source_path),
        "--host-source-path",
        str(source_path),
        "--checkpoint",
        str(CHECKPOINT_PATH),
        "--output-dir",
        str(output_dir),
        "--device",
        "auto",
    ]
    # DeepWuKong's original symbolizer resolves data/sensiAPI.txt relative to
    # the runtime image's /workspace directory.
    runtime_cwd = Path("/workspace") if Path("/workspace").is_dir() else PROJECT_ROOT
    process = subprocess.run(command, cwd=runtime_cwd, text=True, capture_output=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "quick_demo_stdout.log").write_text(process.stdout, encoding="utf-8")
    (output_dir / "quick_demo_stderr.log").write_text(process.stderr, encoding="utf-8")
    if process.returncode != 0:
        detail = (process.stderr.strip() or process.stdout.strip())[-2000:]
        return None, detail or f"Inference process exited with code {process.returncode}."
    prediction_path = output_dir / "predictions.json"
    if not prediction_path.is_file():
        return None, "Inference completed without producing predictions.json."
    payload = json.loads(prediction_path.read_text(encoding="utf-8"))
    prediction = dict(payload.get("prediction") or {})
    if not prediction:
        return None, "predictions.json does not contain a prediction record."
    prediction["sample_id"] = sample_id
    return prediction, None


def comparison_row(
    sample_id: str,
    action: str,
    baseline: dict[str, Any],
    variant: dict[str, Any] | None,
    error: str | None,
) -> dict[str, Any]:
    base_probability = numeric(baseline.get("vulnerability_probability"))
    base_nodes = int(numeric(baseline.get("num_nodes")))
    base_edges = int(numeric(baseline.get("num_edges")))
    if variant is None:
        return {
            "sample": sample_id,
            "action": action,
            "function": baseline.get("function_name", "unknown"),
            "status": "failed",
            "base_label": baseline.get("predicted_label"),
            "variant_label": "",
            "flipped": "False",
            "base_prob": base_probability,
            "variant_prob": "",
            "delta_prob": "",
            "base_nodes": base_nodes,
            "variant_nodes": "",
            "delta_nodes": "",
            "base_edges": base_edges,
            "variant_edges": "",
            "delta_edges": "",
            "error": error or "unknown inference failure",
        }
    variant_probability = numeric(variant.get("vulnerability_probability"))
    variant_nodes = int(numeric(variant.get("num_nodes")))
    variant_edges = int(numeric(variant.get("num_edges")))
    return {
        "sample": sample_id,
        "action": action,
        "function": baseline.get("function_name", "unknown"),
        "status": "success",
        "base_label": baseline.get("predicted_label"),
        "variant_label": variant.get("predicted_label"),
        "flipped": str(baseline.get("predicted_label")) != str(variant.get("predicted_label")),
        "base_prob": base_probability,
        "variant_prob": variant_probability,
        "delta_prob": variant_probability - base_probability,
        "base_nodes": base_nodes,
        "variant_nodes": variant_nodes,
        "delta_nodes": variant_nodes - base_nodes,
        "base_edges": base_edges,
        "variant_edges": variant_edges,
        "delta_edges": variant_edges - base_edges,
        "error": "",
    }


def build_action_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["action"])].append(row)
    summaries: list[dict[str, Any]] = []
    for action, group in sorted(grouped.items()):
        completed = [row for row in group if row["status"] == "success"]
        summaries.append(
            {
                "action": action,
                "count": len(group),
                "flips": sum(str(row["flipped"]).lower() == "true" for row in completed),
                "avg_delta_prob": sum(numeric(row["delta_prob"]) for row in completed) / len(completed) if completed else "",
                "min_delta_prob": min((numeric(row["delta_prob"]) for row in completed), default=""),
                "max_delta_prob": max((numeric(row["delta_prob"]) for row in completed), default=""),
                "avg_delta_nodes": sum(numeric(row["delta_nodes"]) for row in completed) / len(completed) if completed else "",
                "avg_delta_edges": sum(numeric(row["delta_edges"]) for row in completed) / len(completed) if completed else "",
                "attempted": len(group),
                "failed": len(group) - len(completed),
            }
        )
    return summaries


def main() -> int:
    if not SOURCE_PATH.is_file() or not CHECKPOINT_PATH.is_file() or not INFERENCE_SCRIPT.is_file():
        raise FileNotFoundError("Quick Demo input, model checkpoint, or inference script is missing from the image.")

    started = datetime.now()
    run_id = f"run_{started:%Y%m%d_%H%M%S}_code_cwe119_quick"
    run_dir = PROJECT_ROOT / "outputs" / run_id
    variants_dir = run_dir / "variants"
    sample_id = SOURCE_PATH.stem
    print(f"Live Quick Demo: {sample_id}", flush=True)
    print("Running baseline inference (Joern -> PDG/XFG -> DeepWuKong)...", flush=True)
    baseline, baseline_error = run_inference(SOURCE_PATH, run_dir / "runs" / "baseline" / sample_id, sample_id)
    if baseline is None:
        write_json(run_dir / "summary.json", {"status": "baseline_failed", "error": baseline_error})
        print(f"Baseline inference failed: {baseline_error}", file=sys.stderr, flush=True)
        return 1

    original = SOURCE_PATH.read_text(encoding="utf-8", errors="replace")
    comparisons: list[dict[str, Any]] = []
    for action_name in ACTION_NAMES:
        action = OPERATORS[action_name]
        result = action.apply(original, count=1)
        if result.applied_count <= 0:
            comparisons.append(comparison_row(sample_id, action_name, baseline, None, result.notes))
            print(f"[{action_name}] skipped: {result.notes}", flush=True)
            continue
        variant_path = variants_dir / f"{sample_id}__{action_name}__c1{SOURCE_PATH.suffix}"
        variant_path.parent.mkdir(parents=True, exist_ok=True)
        variant_path.write_text(result.source_text, encoding="utf-8", newline="")
        print(f"[{action_name}] running perturbed inference...", flush=True)
        variant, error = run_inference(
            variant_path,
            run_dir / "runs" / "perturbed" / variant_path.stem,
            variant_path.stem,
        )
        comparisons.append(comparison_row(sample_id, action_name, baseline, variant, error))

    comparison_fields = [
        "sample", "action", "function", "status", "base_label", "variant_label", "flipped",
        "base_prob", "variant_prob", "delta_prob", "base_nodes", "variant_nodes", "delta_nodes",
        "base_edges", "variant_edges", "delta_edges", "error",
    ]
    action_fields = [
        "action", "count", "flips", "avg_delta_prob", "min_delta_prob", "max_delta_prob",
        "avg_delta_nodes", "avg_delta_edges", "attempted", "failed",
    ]
    baseline_fields = [
        "sample_id", "function_name", "predicted_label", "vulnerability_probability", "confidence",
        "num_nodes", "num_edges", "joern_status", "input_file",
    ]
    action_summary = build_action_summary(comparisons)
    write_csv(run_dir / "prediction_comparison.csv", comparison_fields, comparisons)
    write_csv(run_dir / "action_summary.csv", action_fields, action_summary)
    write_csv(run_dir / "baseline_summary.csv", baseline_fields, [baseline])
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        "run_id": run_id,
        "sample": sample_id,
        "source": str(SOURCE_PATH.relative_to(PROJECT_ROOT)),
        "actions": list(ACTION_NAMES),
        "baseline": baseline,
        "attempted_variants": len(comparisons),
        "successful_variants": sum(row["status"] == "success" for row in comparisons),
        "prediction_flips": sum(str(row["flipped"]).lower() == "true" for row in comparisons),
        "results_file": "prediction_comparison.csv",
    }
    write_json(run_dir / "summary.json", summary)
    (run_dir / "README.md").write_text(
        "# Live DeepWuKong Quick Demo\n\n"
        "This run was generated live inside the Almond Docker image. It scores the original CWE-119 "
        "sample and two newly generated source perturbations through Joern and DeepWuKong.\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)
    print(f"Live results written to: {run_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
