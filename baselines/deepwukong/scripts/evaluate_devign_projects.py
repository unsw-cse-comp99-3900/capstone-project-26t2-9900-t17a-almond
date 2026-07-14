from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


BASELINE_ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def resolve_path(value: str | Path, base: Path | None = None) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (base or Path.cwd()) / path
    return path.resolve()


def default_devign_jsonl() -> Path:
    desktop = BASELINE_ROOT.parents[1]
    return (
        desktop
        / "9900_product"
        / "devign-scanner"
        / "data_collections"
        / "devign_public_cpg"
        / "processed"
        / "normalized"
        / "test.jsonl"
    )


def timestamped_output_dir(base_dir: Path) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = base_dir / stamp
    suffix = 2
    while candidate.exists():
        candidate = base_dir / f"{stamp}_{suffix:02d}"
        suffix += 1
    return candidate


def safe_slug(value: Any, fallback: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or fallback)).strip("._")
    return (text[:80] or fallback).lower()


def load_samples(
    jsonl_path: Path,
    projects: list[str],
    split: str,
    limit_per_project: int | None,
) -> list[dict[str, Any]]:
    wanted = {project.lower() for project in projects}
    per_project: Counter[str] = Counter()
    samples: list[dict[str, Any]] = []
    with jsonl_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            row_split = row.get("split") or row.get("official_split") or row.get("metadata", {}).get("official_split")
            if split and row_split and str(row_split) != split:
                continue
            project = str(row.get("project") or "")
            project_key = project.lower()
            if project_key not in wanted:
                continue
            if limit_per_project is not None and per_project[project_key] >= limit_per_project:
                continue
            label = row.get("target", row.get("label"))
            source_code = row.get("source_code") or row.get("func")
            if label not in (0, 1) or not isinstance(source_code, str) or not source_code.strip():
                continue
            per_project[project_key] += 1
            metadata = row.get("metadata") or {}
            samples.append(
                {
                    "sample_id": str(row.get("sample_id") or f"line:{line_number}"),
                    "dataset": str(row.get("dataset") or row.get("dataset_name") or "codexglue_devign"),
                    "project": project,
                    "commit_id": row.get("commit_id"),
                    "source_index": metadata.get("source_index", row.get("source_index", line_number)),
                    "official_split": row_split or split,
                    "target": int(label),
                    "source_code": source_code,
                }
            )
    return samples


def prepare_sources(samples: list[dict[str, Any]], output_dir: Path, chunk_size: int) -> Path:
    source_root = output_dir / "sources"
    source_root.mkdir(parents=True, exist_ok=True)
    metadata_path = output_dir / "metadata.jsonl"
    with metadata_path.open("w", encoding="utf-8", newline="\n") as handle:
        for index, sample in enumerate(samples, 1):
            chunk_name = f"chunk_{(index - 1) // chunk_size:04d}"
            project_slug = safe_slug(sample["project"], "project")
            source_slug = safe_slug(sample["source_index"], str(index))
            filename = f"{index:06d}_{project_slug}_{source_slug}_y{sample['target']}.c"
            relative_source_path = Path(chunk_name) / filename
            source_path = source_root / relative_source_path
            source_path.parent.mkdir(parents=True, exist_ok=True)
            source_path.write_text(sample["source_code"].replace("\r\n", "\n"), encoding="utf-8", newline="\n")
            record = {
                key: value
                for key, value in sample.items()
                if key != "source_code"
            }
            record.update(
                {
                    "index": index,
                    "source_file": filename,
                    "relative_source_path": relative_source_path.as_posix(),
                    "chunk": chunk_name,
                }
            )
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return metadata_path


def write_manifest(
    output_dir: Path,
    samples: list[dict[str, Any]],
    args: argparse.Namespace,
    metadata_path: Path,
    checkpoint: Path,
    image: str,
) -> None:
    projects = Counter(str(sample["project"]) for sample in samples)
    labels: dict[str, Counter[int]] = {}
    for sample in samples:
        labels.setdefault(str(sample["project"]), Counter())[int(sample["target"])] += 1
    write_json(
        output_dir / "manifest.json",
        {
            "created_at": datetime.now().isoformat(),
            "devign_jsonl": str(args.devign_jsonl),
            "metadata_path": str(metadata_path),
            "output_dir": str(output_dir),
            "projects": dict(projects),
            "labels": {project: dict(counter) for project, counter in labels.items()},
            "split": args.split,
            "threshold": args.threshold,
            "chunk_size": args.chunk_size,
            "checkpoint": str(checkpoint),
            "docker_image": image,
            "device": args.device,
        },
    )


def load_deepwukong_paths(config_path: Path) -> dict[str, Any]:
    config = read_json(config_path)
    model_paths = read_json(resolve_path(config["paths"]["model_paths"], BASELINE_ROOT))
    paths = dict(model_paths["deepwukong"])
    paths["threshold"] = float(config.get("output", {}).get("threshold", 0.5))
    paths["use_gpus"] = bool(config.get("docker", {}).get("use_gpus", True))
    paths["timeout_seconds"] = int(config.get("docker", {}).get("timeout_seconds", 900))
    return paths


def run_container(
    output_dir: Path,
    metadata_path: Path,
    checkpoint: Path,
    image: str,
    args: argparse.Namespace,
) -> None:
    cmd = ["docker", "run", "--rm"]
    if args.use_gpus:
        cmd.extend(["--gpus", "all"])
    cmd.extend(
        [
            "--entrypoint",
            "python",
            "-v",
            f"{BASELINE_ROOT}:/baseline:ro",
            "-v",
            f"{output_dir}:/eval",
            image,
            "/baseline/scripts/evaluate_devign_projects_container.py",
            "--metadata",
            f"/eval/{metadata_path.name}",
            "--source-root",
            "/eval/sources",
            "--output-dir",
            "/eval",
            "--checkpoint",
            f"/baseline/{checkpoint.relative_to(BASELINE_ROOT).as_posix()}",
            "--threshold",
            str(args.threshold),
            "--device",
            args.device,
            "--joern-timeout",
            str(args.joern_timeout),
            "--progress-every",
            str(args.progress_every),
        ]
    )
    (output_dir / "docker_command.txt").write_text(" ".join(cmd) + "\n", encoding="utf-8")
    started = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=str(BASELINE_ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=args.docker_timeout,
    )
    (output_dir / "docker_stdout.log").write_text(proc.stdout, encoding="utf-8")
    (output_dir / "docker_stderr.log").write_text(proc.stderr, encoding="utf-8")
    if proc.returncode != 0:
        detail = (proc.stderr.strip() or proc.stdout.strip())[-4000:]
        raise RuntimeError(f"Docker evaluation failed after {time.perf_counter() - started:.1f}s: {detail}")


def print_summary(output_dir: Path) -> None:
    per_project = output_dir / "per_project_metrics.csv"
    if not per_project.is_file():
        print(f"Wrote outputs to: {output_dir}")
        return
    print(f"Wrote outputs to: {output_dir}")
    with per_project.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            print(
                "{project}: total={total_samples}, predicted={predicted_samples}, "
                "accuracy_all={accuracy_all}, accuracy_predicted={accuracy_predicted}".format(**row)
            )


def parse_args() -> argparse.Namespace:
    paths = load_deepwukong_paths(resolve_path("configs/demo_config.json", BASELINE_ROOT))
    parser = argparse.ArgumentParser(description="Evaluate the CWE119 DeepWuKong checkpoint on Devign FFmpeg/QEMU.")
    parser.add_argument("--devign-jsonl", type=Path, default=default_devign_jsonl())
    parser.add_argument("--output", type=Path, default=BASELINE_ROOT / "outputs" / "devign_ffmpeg_qemu_eval")
    parser.add_argument("--config", type=Path, default=BASELINE_ROOT / "configs" / "demo_config.json")
    parser.add_argument("--projects", nargs="+", default=["FFmpeg", "qemu"])
    parser.add_argument("--split", default="test")
    parser.add_argument("--limit-per-project", type=int)
    parser.add_argument("--chunk-size", type=int, default=50)
    parser.add_argument("--threshold", type=float, default=float(paths["threshold"]))
    parser.add_argument("--checkpoint", type=Path, default=resolve_path(paths["checkpoint"], BASELINE_ROOT))
    parser.add_argument("--image", default=str(paths.get("docker_image") or "deepwukong-rtx5060-cu128:experimental"))
    parser.add_argument("--device", default="auto")
    parser.add_argument("--joern-timeout", type=int, default=900)
    parser.add_argument("--docker-timeout", type=int, default=24 * 60 * 60)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--no-gpus", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--no-timestamp-output", action="store_true")
    args = parser.parse_args()
    args.devign_jsonl = resolve_path(args.devign_jsonl)
    args.config = resolve_path(args.config, BASELINE_ROOT)
    args.checkpoint = resolve_path(args.checkpoint, BASELINE_ROOT)
    args.output = resolve_path(args.output)
    args.use_gpus = (not args.no_gpus) and bool(paths["use_gpus"])
    return args


def main() -> int:
    args = parse_args()
    if not args.devign_jsonl.is_file():
        raise FileNotFoundError(f"Devign JSONL not found: {args.devign_jsonl}")
    if not args.checkpoint.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {args.checkpoint}")
    samples = load_samples(args.devign_jsonl, args.projects, args.split, args.limit_per_project)
    if not samples:
        raise RuntimeError("No matching Devign samples found.")
    output_dir = args.output if args.no_timestamp_output else timestamped_output_dir(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = prepare_sources(samples, output_dir, args.chunk_size)
    write_manifest(output_dir, samples, args, metadata_path, args.checkpoint, args.image)
    print(f"Prepared {len(samples)} samples under {output_dir}")
    if args.prepare_only:
        return 0
    run_container(output_dir, metadata_path, args.checkpoint, args.image, args)
    print_summary(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
