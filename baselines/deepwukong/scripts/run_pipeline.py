from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASELINE_ROOT = Path(__file__).resolve().parents[1]

BATCH_CSV_FIELDS = [
    "index",
    "sample_id",
    "input_file",
    "function_name",
    "result",
    "predicted_label",
    "vulnerability_probability",
    "threshold",
    "confidence",
    "joern_status",
    "num_nodes",
    "num_edges",
    "lexical_score",
    "graph_score",
    "fusion_status",
    "unixcoder_score",
    "codet5_score",
    "graphcodebert_score",
    "final_score",
    "run_dir",
    "error",
]


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def resolve_user_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = BASELINE_ROOT / path
    return path.resolve()


def safe_name(value: str, fallback: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", value or fallback).strip("._")
    return (text[:120] or fallback).lower()


def timestamped_output_dir(base_dir: Path) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = base_dir / stamp
    suffix = 2
    while candidate.exists():
        candidate = base_dir / f"{stamp}_{suffix:02d}"
        suffix += 1
    return candidate


def discover_input_files(input_path: Path, pattern: str, recursive: bool) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if not input_path.is_dir():
        raise FileNotFoundError(f"Input path not found: {input_path}")
    iterator = input_path.rglob(pattern) if recursive else input_path.glob(pattern)
    files = sorted((path.resolve() for path in iterator if path.is_file()), key=lambda path: str(path).lower())
    if not files:
        mode = "recursively" if recursive else "non-recursively"
        raise FileNotFoundError(f"No files matching {pattern!r} found {mode} under: {input_path}")
    return files


def csv_value(value: Any) -> Any:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.12g}"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


def score_text(value: Any) -> str:
    if value is None:
        return "NA"
    try:
        return f"{float(value):.6f}"
    except (TypeError, ValueError):
        return str(value)


def result_text(row: dict[str, Any]) -> str:
    if row.get("error"):
        return "failed"
    if row.get("predicted_label") == 1:
        return "vulnerable"
    if row.get("predicted_label") == 0:
        return "non_vulnerable"
    return "unknown"


def docker_path(path: Path) -> str:
    return str(path)


def run_pipeline(input_file: Path, output_dir: Path, config_path: Path) -> dict[str, Any]:
    if not input_file.is_file():
        raise FileNotFoundError(f"Input C/C++ file not found: {input_file}")
    output_dir.mkdir(parents=True, exist_ok=True)
    config = read_json(config_path)
    model_paths = read_json(resolve_user_path(config["paths"]["model_paths"]))
    deepwukong_paths = model_paths["deepwukong"]
    docker_config = config.get("docker", {})
    image = str(docker_config.get("image") or deepwukong_paths.get("docker_image"))
    checkpoint = resolve_user_path(deepwukong_paths["checkpoint"])
    helper = resolve_user_path(deepwukong_paths["container_helper"])
    threshold = float(config.get("output", {}).get("threshold", 0.5))
    timeout_seconds = int(docker_config.get("timeout_seconds", 900))
    if not checkpoint.exists():
        raise FileNotFoundError(f"DeepWuKong checkpoint not found: {checkpoint}")
    if not helper.exists():
        raise FileNotFoundError(f"Container helper not found: {helper}")

    cmd = ["docker", "run", "--rm"]
    if docker_config.get("use_gpus", True):
        cmd.extend(["--gpus", "all"])
    cmd.extend(
        [
            "--entrypoint",
            "python",
            "-v",
            f"{docker_path(BASELINE_ROOT)}:/baseline:ro",
            "-v",
            f"{docker_path(input_file.parent)}:/scan/input:ro",
            "-v",
            f"{docker_path(output_dir)}:/scan/output",
            image,
            "/baseline/scripts/infer_single_source.py",
            "--source",
            f"/scan/input/{input_file.name}",
            "--host-source-path",
            str(input_file),
            "--checkpoint",
            f"/baseline/{checkpoint.relative_to(BASELINE_ROOT).as_posix()}",
            "--output-dir",
            "/scan/output",
            "--threshold",
            str(threshold),
            "--device",
            str(config.get("inference", {}).get("device", "auto")),
            "--joern-timeout",
            str(int(config.get("joern", {}).get("timeout_seconds", 600))),
        ]
    )
    command_log = output_dir / "docker_command.txt"
    command_log.write_text(" ".join(cmd) + "\n", encoding="utf-8")
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(BASELINE_ROOT),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        (output_dir / "docker_stdout.log").write_text(exc.stdout or "", encoding="utf-8")
        (output_dir / "docker_stderr.log").write_text(exc.stderr or "", encoding="utf-8")
        raise RuntimeError(f"DeepWuKong Docker inference timed out after {timeout_seconds}s") from exc
    except FileNotFoundError as exc:
        raise RuntimeError("Docker executable was not found. Start Docker Desktop and ensure docker is on PATH.") from exc

    (output_dir / "docker_stdout.log").write_text(proc.stdout, encoding="utf-8")
    (output_dir / "docker_stderr.log").write_text(proc.stderr, encoding="utf-8")
    if proc.returncode != 0:
        detail = (proc.stderr.strip() or proc.stdout.strip())[-4000:]
        raise RuntimeError(f"DeepWuKong Docker inference failed: {detail}")

    prediction_json = output_dir / "predictions.json"
    if not prediction_json.exists():
        raise RuntimeError(f"DeepWuKong inference did not write predictions.json under: {output_dir}")
    return read_json(prediction_json)


def print_batch_row(row: dict[str, Any], total: int) -> None:
    result = result_text(row)
    if row.get("error"):
        detail = row["error"]
    else:
        detail = (
            f"probability={score_text(row.get('vulnerability_probability'))}, "
            f"confidence={score_text(row.get('confidence'))}, "
            f"joern={row.get('joern_status', 'unknown')}, "
            f"xfg={score_text(row.get('graph_score'))}, "
            f"fusion={row.get('fusion_status', 'unknown')}"
        )
    print(f"[{row['index']}/{total}] {Path(row['input_file']).name}: {result} ({detail})", flush=True)


def build_summary(rows: list[dict[str, Any]], input_path: Path, output_dir: Path, started: float) -> dict[str, Any]:
    succeeded = [row for row in rows if not row.get("error") and row.get("predicted_label") in (0, 1)]
    failed = [row for row in rows if row.get("error")]
    vulnerable = [row for row in succeeded if row.get("predicted_label") == 1]
    non_vulnerable = [row for row in succeeded if row.get("predicted_label") == 0]
    probabilities = [float(row["vulnerability_probability"]) for row in succeeded if row.get("vulnerability_probability") is not None]
    if vulnerable:
        overall_result = "vulnerable_detected"
    elif not succeeded:
        overall_result = "no_successful_predictions"
    elif failed:
        overall_result = "no_vulnerability_detected_in_successful_files_but_some_failed"
    else:
        overall_result = "no_vulnerability_detected"
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline": "deepwukong_xfg_baseline",
        "input_path": str(input_path),
        "output_dir": str(output_dir),
        "scanned_files": len(rows),
        "successful_predictions": len(succeeded),
        "failed_predictions": len(failed),
        "vulnerable_files": len(vulnerable),
        "non_vulnerable_files": len(non_vulnerable),
        "vulnerable_rate_among_successful": (len(vulnerable) / len(succeeded)) if succeeded else None,
        "average_vulnerability_probability": (sum(probabilities) / len(probabilities)) if probabilities else None,
        "overall_result": overall_result,
        "elapsed_seconds": time.perf_counter() - started,
    }


def write_batch_outputs(output_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=BATCH_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field)) for field in BATCH_CSV_FIELDS})
    write_json(output_dir / "summary.json", {"summary": summary, "results": rows})
    table_lines = []
    for row in rows:
        table_lines.append(
            "| {index} | `{file}` | {result} | {probability} | {confidence} | {joern} | `{run_dir}` | {error} |".format(
                index=row.get("index"),
                file=Path(row.get("input_file", "")).name,
                result=result_text(row),
                probability=score_text(row.get("vulnerability_probability")),
                confidence=score_text(row.get("confidence")),
                joern=row.get("joern_status", "unknown"),
                run_dir=row.get("run_dir", ""),
                error=row.get("error", ""),
            )
        )
    report = f"""# DeepWuKong Batch Vulnerability Scan Report

Input path: `{summary.get("input_path")}`

Output directory: `{summary.get("output_dir")}`

Generated at UTC: `{summary.get("generated_at_utc")}`

Overall result: `{summary.get("overall_result")}`

Scanned files: `{summary.get("scanned_files")}`

Successful predictions: `{summary.get("successful_predictions")}`

Failed predictions: `{summary.get("failed_predictions")}`

Vulnerable files: `{summary.get("vulnerable_files")}`

Non-vulnerable files: `{summary.get("non_vulnerable_files")}`

Average vulnerability probability: `{score_text(summary.get("average_vulnerability_probability"))}`

## Per-File Results

| # | File | Result | Probability | Confidence | Joern | Run directory | Error |
|---:|---|---|---:|---:|---|---|---|
{chr(10).join(table_lines)}
"""
    (output_dir / "summary_report.txt").write_text(report, encoding="utf-8")


def run_batch(input_path: Path, output_dir: Path, config_path: Path, pattern: str, recursive: bool) -> dict[str, Any]:
    input_files = discover_input_files(input_path=input_path, pattern=pattern, recursive=recursive)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    print(f"Scanning {len(input_files)} file(s) from {input_path}", flush=True)
    for index, input_file in enumerate(input_files, 1):
        run_dir = output_dir / "runs" / f"{index:03d}_{safe_name(input_file.stem, f'sample_{index}')}"
        row: dict[str, Any] = {
            "index": index,
            "sample_id": input_file.stem,
            "input_file": str(input_file),
            "run_dir": str(run_dir),
            "error": "",
        }
        try:
            payload = run_pipeline(input_file=input_file, output_dir=run_dir, config_path=config_path)
            row.update(payload["prediction"])
            row["index"] = index
            row["run_dir"] = str(run_dir)
            row["result"] = result_text(row)
        except Exception as exc:
            row["result"] = "failed"
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
        print_batch_row(row, len(input_files))
    summary = build_summary(rows=rows, input_path=input_path, output_dir=output_dir, started=started)
    write_batch_outputs(output_dir=output_dir, rows=rows, summary=summary)
    return {"summary": summary, "results": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the DeepWuKong source-scanning pipeline.")
    parser.add_argument("--input", default="inputs", help="Input C/C++ source file or directory. Defaults to inputs.")
    parser.add_argument("--output", default="outputs", help="Output base directory.")
    parser.add_argument("--config", default="configs/runtime_config.json", help="Runtime config JSON.")
    parser.add_argument("--pattern", default="*.c", help="Glob used when --input is a directory.")
    parser.add_argument("--no-recursive", action="store_true", help="Do not scan input directories recursively.")
    parser.add_argument("--no-timestamp-output", action="store_true", help="Write directly to --output.")
    args = parser.parse_args()

    input_path = resolve_user_path(args.input)
    output_base = resolve_user_path(args.output)
    output_dir = output_base if args.no_timestamp_output else timestamped_output_dir(output_base)
    config_path = resolve_user_path(args.config)
    if input_path.is_dir():
        result = run_batch(
            input_path=input_path,
            output_dir=output_dir,
            config_path=config_path,
            pattern=args.pattern,
            recursive=not args.no_recursive,
        )
        print(json.dumps(result["summary"], indent=2, ensure_ascii=True))
        print(f"Wrote batch outputs to: {output_dir}")
    else:
        payload = run_pipeline(input_file=input_path, output_dir=output_dir, config_path=config_path)
        print(json.dumps(payload["prediction"], indent=2, ensure_ascii=True))
        print(f"Wrote inference outputs to: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
