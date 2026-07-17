from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from demo_b.code.code_perturbations import (
    OPERATORS,
    PROJECT_ROOT,
    PerturbationResult,
    discover_sources,
    generation_status,
    normalize_counts,
    safe_stem,
)


CSV_FIELDS = [
    "sample_id",
    "source_file",
    "action",
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


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search for minimal perturbation counts that flip DeepWuKong predictions.")
    parser.add_argument("--input", type=Path, default=PROJECT_ROOT / "input_sources" / "devign")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "outputs" / "generated" / "budget_search")
    parser.add_argument("--deepwukong-root", type=Path, default=PROJECT_ROOT / "baselines" / "deepwukong")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "baselines" / "deepwukong" / "configs" / "demo_config.json")
    parser.add_argument("--actions", nargs="+", default=list(OPERATORS), choices=sorted(OPERATORS))
    parser.add_argument("--action", dest="actions", nargs="+", choices=sorted(OPERATORS), help=argparse.SUPPRESS)
    parser.add_argument("--counts", nargs="+", type=int, default=[1, 2, 3, 5])
    parser.add_argument("--count", dest="counts", nargs="+", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--no-run", action="store_true", help="Generate variants and rows without invoking DeepWuKong.")
    args = parser.parse_args()
    args.counts = normalize_counts(args.counts)
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

        original = source.read_text(encoding="utf-8", errors="replace")
        for action_name in args.actions:
            action = OPERATORS[action_name]
            seen_effective_counts: set[int] = set()
            for count in args.counts:
                variant_file = sources_dir / f"{sample_id}__{action.name}__c{count}{source.suffix}"
                variant_run_dir = perturbed_root / f"{sample_id}__{action.name}__c{count}"
                result: PerturbationResult = action.apply(original, count)
                gen_status = generation_status(result.applied_count, count)
                run_status = "not_run" if args.no_run else baseline_status
                error = baseline_error
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
        "counts": args.counts,
        "no_run": args.no_run,
        "rows": len(rows),
        "flips": len(flips),
        "flip_rows": flips,
    }
    write_json(output_root / "budget_search.json", summary)
    print(f"Rows: {len(rows)}")
    print(f"Flips: {len(flips)}")
    print(f"CSV: {output_root / 'budget_search.csv'}")
    print(f"JSON: {output_root / 'budget_search.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
