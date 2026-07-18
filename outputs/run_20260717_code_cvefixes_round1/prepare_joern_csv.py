from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


sys.path.insert(0, "/baseline/scripts")

from infer_single_source import run_joern


SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare flat Joern CSV tables for CWE-119 samples.")
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=600)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    sources = sorted(
        path for path in args.source_root.rglob("*") if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES
    )
    results = []

    for index, source in enumerate(sources, start=1):
        sample_id = source.stem
        isolated_root = Path("/tmp/joern_sources") / sample_id
        isolated_root.mkdir(parents=True, exist_ok=True)
        isolated_source = isolated_root / source.name
        shutil.copyfile(source, isolated_source)

        work_root = Path("/tmp/joern_runs") / sample_id
        stats = run_joern(
            Path("/workspace/joern/joern-parse"),
            isolated_source,
            work_root,
            args.timeout,
        )
        target = args.output_root / sample_id
        target.mkdir(parents=True, exist_ok=True)
        selected = Path(stats["selected_csv_dir"]) if stats.get("selected_csv_dir") else None
        success = bool(
            stats.get("parse_status") == "success"
            and selected is not None
            and (selected / "nodes.csv").is_file()
            and (selected / "edges.csv").is_file()
        )
        if success:
            shutil.copyfile(selected / "nodes.csv", target / "nodes.csv")
            shutil.copyfile(selected / "edges.csv", target / "edges.csv")

        record = {
            "sample_id": sample_id,
            "source_file": str(source),
            "status": "success" if success else "failed",
            "runtime_ms": stats.get("runtime_ms"),
            "error": stats.get("error"),
            "stdout": stats.get("stdout", ""),
            "stderr": stats.get("stderr", ""),
        }
        (target / "joern_graph_stats.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        results.append(record)
        print(
            f"[{index}/{len(sources)}] {sample_id}: {record['status']} "
            f"({float(record['runtime_ms'] or 0.0):.1f} ms)",
            flush=True,
        )

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "samples": len(results),
        "successful": sum(row["status"] == "success" for row in results),
        "failed": sum(row["status"] != "success" for row in results),
        "results": results,
    }
    (args.output_root / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
