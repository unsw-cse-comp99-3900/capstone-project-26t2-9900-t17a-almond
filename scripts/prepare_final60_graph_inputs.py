#!/usr/bin/env python3
"""Stage the 60 code-baseline Joern graphs for graph perturbation experiments."""

from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path


DATASETS = ("cwe119", "devign", "cvefixes")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cwe119-result", required=True, type=Path)
    parser.add_argument("--devign-result", required=True, type=Path)
    parser.add_argument("--cvefixes-result", required=True, type=Path)
    return parser.parse_args()


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing graph input bundle: {output}")

    result_roots = {
        "cwe119": args.cwe119_result.resolve(),
        "devign": args.devign_result.resolve(),
        "cvefixes": args.cvefixes_result.resolve(),
    }
    final60_root = project_root / "input_sources"
    manifest, _ = read_csv(final60_root / "sample_manifest.csv")
    labels_by_leaf = {Path(row["staged_file"]).name: row for row in manifest}
    sources_by_leaf = {path.name: path for path in final60_root.rglob("*") if path.is_file() and path.name != "sample_manifest.csv"}

    source_output = output / "sources"
    csv_output = output / "csv"
    source_output.mkdir(parents=True)
    metadata_rows: list[dict[str, str]] = []
    staging_rows: list[dict[str, str]] = []
    seen_ids: set[str] = set()

    for dataset in DATASETS:
        result_root = result_roots[dataset]
        baseline_rows, _ = read_csv(result_root / "baseline_predictions.csv")
        if len(baseline_rows) != 20:
            raise ValueError(f"Expected 20 code baselines for {dataset}, found {len(baseline_rows)}")

        for baseline_row in baseline_rows:
            sample_id = baseline_row["sample_id"]
            if sample_id in seen_ids:
                raise ValueError(f"Duplicate graph sample ID: {sample_id}")
            seen_ids.add(sample_id)
            source_leaf = Path(baseline_row["source_file"]).name
            source = sources_by_leaf.get(source_leaf)
            label = labels_by_leaf.get(source_leaf)
            baseline = (
                result_root / "runs" / "baseline" / sample_id / "joern_csv" / "scan" / "output" / "_work" / "source" / source_leaf
            )
            nodes, edges = baseline / "nodes.csv", baseline / "edges.csv"
            if source is None or label is None:
                raise FileNotFoundError(f"Final60 source or manifest row unavailable for {sample_id}: {source_leaf}")
            if not nodes.is_file() or not edges.is_file():
                raise FileNotFoundError(f"Baseline Joern CSV unavailable for {sample_id}: {baseline}")

            sample_csv = csv_output / sample_id
            sample_csv.mkdir(parents=True)
            shutil.copy2(nodes, sample_csv / "nodes.csv")
            shutil.copy2(edges, sample_csv / "edges.csv")
            shutil.copy2(source, source_output / f"{sample_id}{source.suffix or '.c'}")
            metadata_rows.append({
                "sample_id": sample_id,
                "label": label["label"],
                "dataset": dataset,
                "source_kind": label["source_kind"],
            })
            staging_rows.append({
                "sample_id": sample_id,
                "dataset": dataset,
                "source_leaf": source_leaf,
                "label": label["label"],
                "status": "staged",
                "baseline_code_result": str(result_root),
                "notes": "baseline Joern CSV staged",
            })

    if len(metadata_rows) != 60:
        raise ValueError(f"Expected 60 staged graph inputs, got {len(metadata_rows)}")
    write_csv(output / "metadata.csv", metadata_rows, ["sample_id", "label", "dataset", "source_kind"])
    write_csv(
        output / "staging_manifest.csv",
        staging_rows,
        ["sample_id", "dataset", "source_leaf", "label", "status", "baseline_code_result", "notes"],
    )
    print(f"Staged {len(metadata_rows)} graph inputs at {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
