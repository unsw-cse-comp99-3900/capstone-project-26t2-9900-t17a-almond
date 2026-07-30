#!/usr/bin/env python3
"""Rerun only random graph perturbations for an existing Full Test run."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from robustness_experiments.graph.experiment_design import (  # noqa: E402
    DEFAULT_GRAPH_BUDGETS,
    DEFAULT_GRAPH_SEEDS,
)


RANDOM_GRAPH_RUNNER = (
    PROJECT_ROOT / "robustness_experiments" / "graph" / "run_random_graph_experiment.py"
)
DASHBOARD_RENDERER = PROJECT_ROOT / "robustness_experiments" / "visualize_results.py"
CHECKPOINT_PATH = (
    PROJECT_ROOT
    / "baselines"
    / "deepwukong"
    / "models"
    / "deepwukong"
    / "deepwukong_cwe119_best.ckpt"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rerun random graph results and refresh dashboards without repeating code or Winner-XFG."
    )
    parser.add_argument(
        "--run-dir",
        required=True,
        type=Path,
        help="Existing Full Test directory under outputs.",
    )
    return parser.parse_args()


def resolve_run_dir(path: Path) -> Path:
    run_dir = path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()
    outputs_root = (PROJECT_ROOT / "outputs").resolve()
    if run_dir.parent != outputs_root:
        raise ValueError(f"run directory must be a direct child of {outputs_root}")
    return run_dir


def stream_command(command: list[str], log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    workdir = Path("/workspace") if Path("/workspace/data/sensiAPI.txt").is_file() else PROJECT_ROOT
    with log_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            command,
            cwd=workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            log_file.write(line)
        return process.wait()


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def update_full_test_summary(
    run_dir: Path,
    *,
    backup_dir: Path | None,
    random_summary: dict[str, Any],
) -> None:
    summary_path = run_dir / "summary.json"
    summary = read_json(summary_path)
    metadata = random_summary.get("metadata", {})
    graph_results = summary.setdefault("graph_perturbations", {})
    graph_results["random_graph"] = {
        "status": "completed",
        "return_code": 0,
        "output_dir": "graph_random",
        "scored": metadata.get("perturbations_scored", 0),
        "unscored_no_xfg": metadata.get("perturbations_unscored_no_xfg", 0),
        "rerun_at_utc": datetime.now(timezone.utc).isoformat(),
        "previous_output_dir": backup_dir.name if backup_dir else None,
    }
    targeted_status = graph_results.get("targeted_graph", {}).get("status")
    summary["status"] = "completed" if targeted_status != "failed" else "completed_with_graph_errors"
    history = summary.setdefault("partial_reruns", [])
    history.append(
        {
            "stage": "random_graph",
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "budgets": list(DEFAULT_GRAPH_BUDGETS),
            "seeds": list(DEFAULT_GRAPH_SEEDS),
            "previous_output_dir": backup_dir.name if backup_dir else None,
        }
    )
    write_json(summary_path, summary)


def main() -> int:
    args = parse_args()
    run_dir = resolve_run_dir(args.run_dir)
    graph_inputs = run_dir / "graph_inputs"
    required = (
        graph_inputs / "sources",
        graph_inputs / "csv",
        graph_inputs / "metadata.csv",
        run_dir / "graph_targeted" / "prediction_comparison.csv",
        run_dir / "prediction_comparison.csv",
        CHECKPOINT_PATH,
    )
    missing = [path for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("required rerun inputs are missing: " + ", ".join(str(path) for path in missing))

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = run_dir / f"graph_random_rerun_{stamp}"
    log_path = run_dir / "graph_logs" / f"random_graph_rerun_{stamp}.log"
    command = [
        sys.executable,
        str(RANDOM_GRAPH_RUNNER),
        "--source-root",
        str(graph_inputs / "sources"),
        "--csv-root",
        str(graph_inputs / "csv"),
        "--metadata",
        str(graph_inputs / "metadata.csv"),
        "--checkpoint",
        str(CHECKPOINT_PATH),
        "--output-dir",
        str(candidate),
        "--experiment",
        "full_test_random_graph_rerun",
        "--dataset",
        "all_input_sources",
        "--strategy",
        "random",
        "--budgets",
        *(str(value) for value in DEFAULT_GRAPH_BUDGETS),
        "--seeds",
        *(str(value) for value in DEFAULT_GRAPH_SEEDS),
    ]
    print(f"Rerunning random graph stage for {run_dir.name}", flush=True)
    return_code = stream_command(command, log_path)
    if return_code != 0:
        print(f"Random graph rerun failed; existing results were preserved. Candidate: {candidate}", flush=True)
        return return_code

    current = run_dir / "graph_random"
    backup = run_dir / f"graph_random_before_rerun_{stamp}" if current.exists() else None
    if backup is not None:
        current.rename(backup)
    try:
        candidate.rename(current)
    except Exception:
        if backup is not None and not current.exists():
            backup.rename(current)
        raise

    dashboard = subprocess.run(
        [sys.executable, str(DASHBOARD_RENDERER), "--run-dir", str(run_dir)],
        cwd=PROJECT_ROOT,
    )
    if dashboard.returncode != 0:
        print("Random graph results were replaced, but dashboard regeneration failed.", flush=True)
        return dashboard.returncode

    update_full_test_summary(
        run_dir,
        backup_dir=backup,
        random_summary=read_json(current / "summary.json"),
    )
    print(f"Random graph rerun and dashboard refresh completed: {run_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
