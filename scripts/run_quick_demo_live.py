#!/usr/bin/env python3
"""Run a live DeepWuKong code-perturbation test for every input source file."""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from robustness_experiments.code.code_perturbations import OPERATORS


INPUT_SOURCES_ROOT = PROJECT_ROOT / "input_sources"
SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx"}
# Kept as a stable single-source reference for the separate smoke-test command.
SOURCE_PATH = INPUT_SOURCES_ROOT / "cwe119" / "01_vulnerable_03_vulnerable_30.c"
CHECKPOINT_PATH = PROJECT_ROOT / "baselines" / "deepwukong" / "models" / "deepwukong" / "deepwukong_cwe119_best.ckpt"
INFERENCE_SCRIPT = PROJECT_ROOT / "baselines" / "deepwukong" / "scripts" / "infer_single_source.py"
# A Full Test is deliberately exhaustive: one variant for every implemented
# source-level operator, plus the random and Winner-XFG graph suites below.
ACTION_NAMES = tuple(OPERATORS)
RANDOM_GRAPH_RUNNER = PROJECT_ROOT / "robustness_experiments" / "graph" / "run_random_graph_experiment.py"
TARGETED_GRAPH_RUNNER = PROJECT_ROOT / "robustness_experiments" / "graph" / "run_xfg_targeted_experiment.py"
INPUT_LABEL_MANIFEST = INPUT_SOURCES_ROOT / "sample_manifest.csv"
DASHBOARD_RENDERER = PROJECT_ROOT / "robustness_experiments" / "visualize_results.py"


def discover_source_files(source_root: Path = INPUT_SOURCES_ROOT) -> list[Path]:
    """Return every supported source file below ``input_sources`` in stable order."""
    if not source_root.is_dir():
        raise FileNotFoundError(f"Input source directory does not exist: {source_root}")
    return sorted(
        path for path in source_root.rglob("*")
        if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES
    )


def sample_id_for(source_path: Path) -> str:
    """Create a dataset-qualified identifier that remains unique in one full run."""
    try:
        relative = source_path.relative_to(INPUT_SOURCES_ROOT).with_suffix("")
    except ValueError:
        relative = source_path.with_suffix("")
    return "__".join(relative.parts)


def dataset_for(source_path: Path) -> str:
    try:
        return source_path.relative_to(INPUT_SOURCES_ROOT).parts[0]
    except (ValueError, IndexError):
        return "unknown"


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
    (output_dir / "full_test_stdout.log").write_text(process.stdout, encoding="utf-8")
    (output_dir / "full_test_stderr.log").write_text(process.stderr, encoding="utf-8")
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


def baseline_row(sample_id: str, source_path: Path, prediction: dict[str, Any] | None, error: str | None) -> dict[str, Any]:
    prediction = prediction or {}
    return {
        "sample_id": sample_id,
        "dataset": dataset_for(source_path),
        "source_file": str(source_path.relative_to(PROJECT_ROOT)),
        "function_name": prediction.get("function_name", ""),
        "predicted_label": prediction.get("predicted_label", ""),
        "vulnerability_probability": prediction.get("vulnerability_probability", ""),
        "confidence": prediction.get("confidence", ""),
        "num_nodes": prediction.get("num_nodes", ""),
        "num_edges": prediction.get("num_edges", ""),
        "joern_status": prediction.get("joern_status", ""),
        "input_file": prediction.get("input_file", str(source_path)),
        "status": "success" if prediction else "failed",
        "error": error or "",
    }


def load_input_labels() -> dict[tuple[str, str], str]:
    """Read optional ground-truth labels used by targeted graph attacks."""
    if not INPUT_LABEL_MANIFEST.is_file():
        return {}
    with INPUT_LABEL_MANIFEST.open(encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        return {
            (str(row.get("dataset", "")).strip(), str(row.get("sample_id", "")).strip()): str(row["label"]).strip()
            for row in rows
            if str(row.get("dataset", "")).strip()
            and str(row.get("sample_id", "")).strip()
            and str(row.get("label", "")).strip() in {"0", "1"}
        }


def find_baseline_csv_directory(run_dir: Path, sample_id: str, source_path: Path) -> Path | None:
    """Find the Joern CSV directory for one baseline across supported layouts."""
    baseline_root = run_dir / "runs" / "baseline" / sample_id
    legacy_candidate = baseline_root / "joern_csv" / "scan" / "output" / "_work" / "source" / source_path.name
    if (legacy_candidate / "nodes.csv").is_file() and (legacy_candidate / "edges.csv").is_file():
        return legacy_candidate

    candidates = [
        node_file.parent
        for node_file in baseline_root.rglob("nodes.csv")
        if (node_file.parent / "edges.csv").is_file()
    ]
    if not candidates:
        return None
    source_candidates = [candidate for candidate in candidates if candidate.name == source_path.name]
    return max(source_candidates or candidates, key=lambda candidate: (candidate / "nodes.csv").stat().st_size)


def prepare_graph_inputs(
    run_dir: Path,
    sources: list[Path],
    baselines: list[dict[str, Any]],
) -> dict[str, Any]:
    """Stage baseline Joern CSVs and sources for the graph-level runners."""
    graph_root = run_dir / "graph_inputs"
    source_root = graph_root / "sources"
    csv_root = graph_root / "csv"
    source_root.mkdir(parents=True, exist_ok=True)
    csv_root.mkdir(parents=True, exist_ok=True)

    labels = load_input_labels()
    baseline_by_id = {str(row["sample_id"]): row for row in baselines}
    metadata_rows: list[dict[str, str]] = []
    staged_rows: list[dict[str, str]] = []
    targeted_rows: list[dict[str, str]] = []

    for source_path in sources:
        sample_id = sample_id_for(source_path)
        dataset = dataset_for(source_path)
        baseline = baseline_by_id[sample_id]
        source_rel = source_path.relative_to(PROJECT_ROOT).as_posix()
        status = "skipped"
        notes = ""
        if baseline["status"] != "success":
            notes = "baseline inference failed"
        else:
            joern_source = find_baseline_csv_directory(run_dir, sample_id, source_path)
            if joern_source is None:
                notes = "baseline Joern nodes.csv or edges.csv is missing"
            else:
                nodes = joern_source / "nodes.csv"
                edges = joern_source / "edges.csv"
                sample_csv = csv_root / sample_id
                sample_csv.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, source_root / f"{sample_id}{source_path.suffix}")
                shutil.copy2(nodes, sample_csv / "nodes.csv")
                shutil.copy2(edges, sample_csv / "edges.csv")
                status = "staged"

        label = labels.get((dataset, source_path.stem), "")
        staged_rows.append(
            {
                "sample_id": sample_id,
                "dataset": dataset,
                "source_file": source_rel,
                "label": label,
                "status": status,
                "notes": notes,
            }
        )
        if status == "staged":
            metadata = {
                "sample_id": sample_id,
                "label": label,
                "dataset": dataset,
                "source_kind": "input_sources",
            }
            metadata_rows.append(metadata)
            if label in {"0", "1"}:
                targeted_rows.append(metadata)

    fields = ["sample_id", "dataset", "source_file", "label", "status", "notes"]
    metadata_fields = ["sample_id", "label", "dataset", "source_kind"]
    write_csv(graph_root / "staging_manifest.csv", fields, staged_rows)
    write_csv(graph_root / "metadata.csv", metadata_fields, metadata_rows)
    write_csv(graph_root / "targeted_metadata.csv", metadata_fields, targeted_rows)
    return {
        "input_dir": str(graph_root.relative_to(run_dir)),
        "sources_discovered": len(sources),
        "sources_staged": len(metadata_rows),
        "targeted_labelled_sources": len(targeted_rows),
        "sources_skipped": len(sources) - len(metadata_rows),
    }


def run_graph_command(name: str, command: list[str], log_path: Path) -> int:
    """Run a graph experiment while streaming and retaining its runtime log."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Starting {name}...", flush=True)
    with log_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            log_file.write(line)
        return_code = process.wait()
    print(f"{name} finished with exit code {return_code}.", flush=True)
    return return_code


def run_graph_experiments(run_dir: Path, sources: list[Path], baselines: list[dict[str, Any]]) -> dict[str, Any]:
    """Run random and targeted graph perturbations from this full test's baselines."""
    staged = prepare_graph_inputs(run_dir, sources, baselines)
    graph_root = run_dir / staged["input_dir"]
    random_output = run_dir / "graph_random"
    targeted_output = run_dir / "graph_targeted"
    logs_root = run_dir / "graph_logs"
    result: dict[str, Any] = {"staging": staged}

    if staged["sources_staged"]:
        random_command = [
            sys.executable,
            str(RANDOM_GRAPH_RUNNER),
            "--source-root", str(graph_root / "sources"),
            "--csv-root", str(graph_root / "csv"),
            "--checkpoint", str(CHECKPOINT_PATH),
            "--output-dir", str(random_output),
            "--experiment", "full_test_random_graph",
            "--dataset", "all_input_sources",
            "--strategy", "random",
            "--count", "1",
            "--seed", "42",
        ]
        random_code = run_graph_command("random graph perturbation", random_command, logs_root / "random_graph.log")
        result["random_graph"] = {
            "status": "completed" if random_code == 0 else "failed",
            "return_code": random_code,
            "output_dir": str(random_output.relative_to(run_dir)),
        }
    else:
        result["random_graph"] = {"status": "skipped", "reason": "no baseline graph inputs were staged"}

    if staged["targeted_labelled_sources"]:
        targeted_command = [
            sys.executable,
            str(TARGETED_GRAPH_RUNNER),
            "--source-root", str(graph_root / "sources"),
            "--csv-root", str(graph_root / "csv"),
            "--metadata", str(graph_root / "targeted_metadata.csv"),
            "--checkpoint", str(CHECKPOINT_PATH),
            "--output-dir", str(targeted_output),
            "--actions", "winner_xfg_edge_attack", "winner_xfg_feature_mask", "targeted_subgraph_injection",
            "--budgets", "1", "3", "5",
            "--seed", "42",
        ]
        targeted_code = run_graph_command(
            "Winner-XFG targeted graph perturbation",
            targeted_command,
            logs_root / "winner_xfg_targeted.log",
        )
        result["targeted_graph"] = {
            "status": "completed" if targeted_code == 0 else "failed",
            "return_code": targeted_code,
            "output_dir": str(targeted_output.relative_to(run_dir)),
        }
    else:
        result["targeted_graph"] = {
            "status": "skipped",
            "reason": "no staged sources have a 0/1 ground-truth label in sample_manifest.csv",
        }
    return result


def generate_html_reports(run_dir: Path, graph_results: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Render code and graph dashboards and refresh the shared output index."""
    reports: dict[str, dict[str, Any]] = {}
    targets = [
        ("random_graph", run_dir / "graph_random"),
        ("targeted_graph", run_dir / "graph_targeted"),
        ("full_test", run_dir),
    ]
    logs_root = run_dir / "dashboard_logs"
    for name, target in targets:
        comparison = target / "prediction_comparison.csv"
        if not comparison.is_file():
            reports[name] = {"status": "skipped", "reason": "comparison CSV is unavailable"}
            continue
        process = subprocess.run(
            [sys.executable, str(DASHBOARD_RENDERER), "--run-dir", str(target)],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
        )
        log_path = logs_root / f"{name}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(process.stdout + process.stderr, encoding="utf-8")
        reports[name] = {
            "status": "completed" if process.returncode == 0 else "failed",
            "return_code": process.returncode,
            "dashboard": str((target / "dashboard.html").relative_to(run_dir)),
        }

    dashboard = run_dir / "dashboard.html"
    if dashboard.is_file():
        links = [
            ("Random graph perturbation report", "graph_random/dashboard.html"),
            ("Winner-XFG targeted graph perturbation report", "graph_targeted/dashboard.html"),
        ]
        available = [f'<li><a href="{href}">{label}</a></li>' for label, href in links if (run_dir / href).is_file()]
        if available:
            section = (
                '<section><h2>Graph-level reports</h2><p class="sub">The same full-test run generated these graph reports.</p>'
                f'<ul>{"".join(available)}</ul></section>'
            )
            content = dashboard.read_text(encoding="utf-8")
            if "Graph-level reports" not in content:
                dashboard.write_text(content.replace("</main>", section + "</main>", 1), encoding="utf-8")
    return reports


def main() -> int:
    sources = discover_source_files()
    if not sources:
        raise FileNotFoundError(f"No C/C++ source files found under {INPUT_SOURCES_ROOT}.")
    for required in (CHECKPOINT_PATH, INFERENCE_SCRIPT):
        if not required.is_file():
            raise FileNotFoundError(f"Required full-test file is missing: {required}")

    started = datetime.now()
    run_id = f"run_{started:%Y%m%d_%H%M%S}_code_all_input_sources"
    run_dir = PROJECT_ROOT / "outputs" / run_id
    variants_dir = run_dir / "variants"
    comparisons: list[dict[str, Any]] = []
    baselines: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, str]] = []

    print(f"Live Full Test: {len(sources)} source files discovered under {INPUT_SOURCES_ROOT}", flush=True)
    for index, source_path in enumerate(sources, start=1):
        sample_id = sample_id_for(source_path)
        source_rel = source_path.relative_to(PROJECT_ROOT).as_posix()
        manifest_rows.append({"sample_id": sample_id, "dataset": dataset_for(source_path), "source_file": source_rel})
        print(f"[{index}/{len(sources)}] {sample_id}: baseline inference...", flush=True)
        baseline, baseline_error = run_inference(source_path, run_dir / "runs" / "baseline" / sample_id, sample_id)
        baselines.append(baseline_row(sample_id, source_path, baseline, baseline_error))
        if baseline is None:
            print(f"  baseline failed: {baseline_error}", file=sys.stderr, flush=True)
            continue

        original = source_path.read_text(encoding="utf-8", errors="replace")
        for action_name in ACTION_NAMES:
            action = OPERATORS[action_name]
            result = action.apply(original, count=1)
            if result.applied_count <= 0:
                comparisons.append(comparison_row(sample_id, action_name, baseline, None, result.notes))
                print(f"  [{action_name}] skipped: {result.notes}", flush=True)
                continue
            variant_path = variants_dir / dataset_for(source_path) / f"{sample_id}__{action_name}__c1{source_path.suffix}"
            variant_path.parent.mkdir(parents=True, exist_ok=True)
            variant_path.write_text(result.source_text, encoding="utf-8", newline="")
            print(f"  [{action_name}] perturbed inference...", flush=True)
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
        "sample_id", "dataset", "source_file", "function_name", "predicted_label", "vulnerability_probability",
        "confidence", "num_nodes", "num_edges", "joern_status", "input_file", "status", "error",
    ]
    action_summary = build_action_summary(comparisons)
    write_csv(run_dir / "input_manifest.csv", ["sample_id", "dataset", "source_file"], manifest_rows)
    write_csv(run_dir / "prediction_comparison.csv", comparison_fields, comparisons)
    write_csv(run_dir / "action_summary.csv", action_fields, action_summary)
    write_csv(run_dir / "baseline_summary.csv", baseline_fields, baselines)
    completed_baselines = sum(row["status"] == "success" for row in baselines)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "code_completed",
        "run_id": run_id,
        "input_root": "input_sources",
        "sources_discovered": len(sources),
        "baseline_completed": completed_baselines,
        "baseline_failed": len(baselines) - completed_baselines,
        "actions_per_sample": list(ACTION_NAMES),
        "attempted_variants": len(comparisons),
        "successful_variants": sum(row["status"] == "success" for row in comparisons),
        "prediction_flips": sum(str(row["flipped"]).lower() == "true" for row in comparisons),
        "results_file": "prediction_comparison.csv",
    }
    graph_results = run_graph_experiments(run_dir, sources, baselines)
    summary["graph_perturbations"] = graph_results
    graph_failed = any(
        graph_results[name].get("status") == "failed"
        for name in ("random_graph", "targeted_graph")
    )
    summary["status"] = "completed_with_graph_errors" if graph_failed else "completed"
    summary["html_reports"] = generate_html_reports(run_dir, graph_results)
    write_json(run_dir / "summary.json", summary)
    (run_dir / "README.md").write_text(
        "# Live DeepWuKong Full Test\n\n"
        "This run scores every C/C++ source file under `input_sources` using a baseline prediction and "
        "the configured source-level perturbations, then runs random and Winner-XFG-targeted graph perturbations "
        "from the resulting baseline PDG/XFG inputs. `input_manifest.csv` records the exact input set.\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)
    print(f"Live results written to: {run_dir}", flush=True)
    return 1 if graph_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
