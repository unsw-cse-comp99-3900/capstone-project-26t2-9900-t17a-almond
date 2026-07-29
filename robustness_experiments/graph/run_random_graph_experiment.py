from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
for import_root in (
    PROJECT_ROOT / "baselines" / "deepwukong" / "scripts",
    Path("/baseline/scripts"),
    Path("/workspace"),
    PROJECT_ROOT,
):
    if import_root.is_dir():
        sys.path.insert(0, str(import_root))

import torch
from torch_geometric.data import Batch

from robustness_experiments.graph.graph_perturbations import ACTION_NAMES, apply_graph_action
from infer_single_source import add_symbols, function_name
from src.data_generator import build_PDG, build_XFG
from src.datas.graphs import XFG
from src.models.vd import DeepWuKong


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the first graph perturbation experiment.")
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--csv-root", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--experiment", default="graph_perturbation_round_1")
    parser.add_argument("--dataset", default="archived_devign_baseline_csv")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--strategy", choices=("random", "guided"), default="random")
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list, tuple)) else value
                    for key, value in row.items()
                }
            )


def find_source(source_root: Path, sample_id: str) -> Path | None:
    matches = sorted(path for path in source_root.rglob(f"{sample_id}.*") if path.is_file())
    return matches[0] if matches else None


class Predictor:
    def __init__(self, checkpoint: Path, threshold: float) -> None:
        self.threshold = threshold
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        self.model = DeepWuKong.load_from_checkpoint(
            checkpoint_path=str(checkpoint),
            weights_only=False,
        ).to(self.device)
        self.model.eval()
        self.config = self.model.hparams["config"]
        self.vocab = self.model.hparams["vocab"]

    def predict_graph(self, pdg: Any, key_line_map: dict[str, set[int]]) -> dict[str, Any]:
        started = time.perf_counter()
        xfg_dict = build_XFG(pdg, key_line_map) or {}
        data_list = []
        metadata = []
        skipped_empty = 0

        for category, graphs in xfg_dict.items():
            for graph in graphs:
                graph = add_symbols(graph, self.config.split_token)
                data = XFG(xfg=graph).to_torch(self.vocab, self.config.dataset.token.max_parts)
                data_list.append(data)
                metadata.append({"category": category, "key_line": graph.graph.get("key_line")})

        if not data_list:
            return {
                "status": "no_xfg",
                "probability": 0.0,
                "predicted_label": 0,
                "xfg_count": 0,
                "skipped_empty_xfg": skipped_empty,
                "runtime_ms": (time.perf_counter() - started) * 1000.0,
            }

        batch = Batch.from_data_list(data_list).to(self.device)
        with torch.no_grad():
            probabilities = torch.softmax(self.model(batch), dim=1).detach().cpu().tolist()

        xfg_predictions = []
        max_probability = 0.0
        for meta, values in zip(metadata, probabilities):
            probability = float(values[1]) if len(values) > 1 else 0.0
            max_probability = max(max_probability, probability)
            xfg_predictions.append(
                {
                    **meta,
                    "vulnerability_probability": probability,
                    "predicted_label": int(probability >= self.threshold),
                }
            )

        return {
            "status": "ok",
            "probability": max_probability,
            "predicted_label": int(max_probability >= self.threshold),
            "xfg_count": len(xfg_predictions),
            "skipped_empty_xfg": skipped_empty,
            "runtime_ms": (time.perf_counter() - started) * 1000.0,
            "xfg_predictions": xfg_predictions,
        }


def action_summaries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["action"])].append(row)

    summaries = []
    for action in ACTION_NAMES:
        group = grouped[action]
        successful = [row for row in group if not row["error"] and row["valid"]]
        absolute_deltas = [abs(float(row["delta_probability"])) for row in successful]
        summaries.append(
            {
                "action": action,
                "attempted": len(group),
                "successful": len(successful),
                "failed": len(group) - len(successful),
                "flips": sum(int(row["flipped"]) for row in successful),
                "mean_delta_probability": (
                    sum(float(row["delta_probability"]) for row in successful) / len(successful)
                    if successful
                    else None
                ),
                "mean_absolute_delta_probability": (
                    sum(absolute_deltas) / len(absolute_deltas) if absolute_deltas else None
                ),
                "max_absolute_delta_probability": max(absolute_deltas) if absolute_deltas else None,
                "mean_runtime_ms": (
                    sum(float(row["runtime_ms"]) for row in successful) / len(successful)
                    if successful
                    else None
                ),
            }
        )
    return summaries


def archive_action_summaries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries = []
    for action in ACTION_NAMES:
        attempted = [row for row in rows if row["action"] == action]
        successful = [
            row
            for row in attempted
            if not row["error"] and row["valid"] and row["delta_probability"] is not None
        ]
        deltas = [float(row["delta_probability"]) for row in successful]
        summaries.append(
            {
                "action": action,
                "count": len(successful),
                "flips": sum(int(row["flipped"]) for row in successful),
                "avg_delta_prob": sum(deltas) / len(deltas) if deltas else None,
                "min_delta_prob": min(deltas) if deltas else None,
                "max_delta_prob": max(deltas) if deltas else None,
                "avg_delta_nodes": (
                    sum(int(row["delta_nodes"]) for row in successful) / len(successful)
                    if successful
                    else None
                ),
                "avg_delta_edges": (
                    sum(int(row["delta_edges"]) for row in successful) / len(successful)
                    if successful
                    else None
                ),
                "attempted": len(attempted),
                "failed": len(attempted) - len(successful),
            }
        )
    return summaries


def write_archive_layout(
    output_dir: Path,
    baseline_rows: list[dict[str, Any]],
    perturbation_rows: list[dict[str, Any]],
    details: dict[str, Any],
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    generated_at = metadata["generated_at_utc"]
    threshold = float(metadata["threshold"])
    baseline_by_sample = {row["sample_id"]: row for row in baseline_rows}

    baseline_summary = []
    for row in baseline_rows:
        baseline_summary.append(
            {
                "sample": row["sample_id"],
                "function": row["function"],
                "status": "success" if not row["error"] else "failed",
                "label": row["predicted_label"],
                "prob": row["probability"],
                "nodes": row["pdg_nodes"],
                "edges": row["pdg_edges"],
                "xfg_count": row["xfg_count"],
            }
        )
        probability = row["probability"]
        label = row["predicted_label"]
        payload = {
            "generated_at_utc": generated_at,
            "prediction": {
                "sample_id": row["sample_id"],
                "input_file": row["source_file"],
                "function_name": row["function"],
                "joern_status": "reused_archived_csv",
                "graph_level": "line_pdg",
                "num_nodes": row["pdg_nodes"],
                "num_edges": row["pdg_edges"],
                "predicted_label": label,
                "vulnerability_probability": probability,
                "threshold": threshold,
                "confidence": (
                    max(float(probability), 1.0 - float(probability)) if probability is not None else None
                ),
                "graph_score": probability,
                "final_score": probability,
                "status": "success" if not row["error"] else "failed",
                "error": row["error"],
            },
            "details": {
                "experiment": metadata,
                "graph_counts": {"pdg_nodes": row["pdg_nodes"], "pdg_edges": row["pdg_edges"]},
                "xfg": details.get(row["sample_id"], {}).get("baseline", {}),
                "key_line_counts": row["key_line_counts"],
                "runtime_ms": row["runtime_ms"],
            },
        }
        write_json(output_dir / "runs" / "baseline" / f"{row['sample_id']}.json", payload)

    comparison_rows = []
    for row in perturbation_rows:
        baseline = baseline_by_sample[row["sample_id"]]
        success = not row["error"] and row["valid"] and row["perturbed_probability"] is not None
        comparison_rows.append(
            {
                "sample": row["sample_id"],
                "action": row["action"],
                "function": baseline["function"],
                "status": "success" if success else "failed",
                "base_label": row["baseline_label"],
                "variant_label": row["perturbed_label"],
                "flipped": row["flipped"],
                "base_prob": row["baseline_probability"],
                "variant_prob": row["perturbed_probability"],
                "delta_prob": row["delta_probability"],
                "base_nodes": row["baseline_nodes"],
                "variant_nodes": row["perturbed_nodes"],
                "delta_nodes": row["delta_nodes"],
                "base_edges": row["baseline_edges"],
                "variant_edges": row["perturbed_edges"],
                "delta_edges": row["delta_edges"],
                "base_xfg_count": row["baseline_xfg_count"],
                "variant_xfg_count": row["perturbed_xfg_count"],
                "error": row["error"],
            }
        )
        action_detail = details.get(row["sample_id"], {}).get("actions", {}).get(row["action"], {})
        probability = row["perturbed_probability"]
        label = row["perturbed_label"]
        payload = {
            "generated_at_utc": generated_at,
            "prediction": {
                "sample_id": f"{row['sample_id']}__{row['action']}",
                "input_file": baseline["source_file"],
                "function_name": baseline["function"],
                "joern_status": "reused_archived_csv",
                "graph_level": "perturbed_line_pdg",
                "num_nodes": row["perturbed_nodes"],
                "num_edges": row["perturbed_edges"],
                "predicted_label": label,
                "vulnerability_probability": probability,
                "threshold": threshold,
                "confidence": (
                    max(float(probability), 1.0 - float(probability)) if probability is not None else None
                ),
                "graph_score": probability,
                "final_score": probability,
                "status": "success" if success else "failed",
                "error": row["error"],
            },
            "details": {
                "experiment": metadata,
                "baseline_sample_id": row["sample_id"],
                "graph_action": {
                    "action": row["action"],
                    "strategy": row["strategy"],
                    "seed": row["seed"],
                    "requested_count": row["requested_count"],
                    "applied_count": row["applied_count"],
                    "valid": row["valid"],
                    "operations": row["operations"],
                    "validation_errors": row["validation_errors"],
                },
                "graph_counts": {
                    "baseline_pdg_nodes": row["baseline_nodes"],
                    "baseline_pdg_edges": row["baseline_edges"],
                    "perturbed_pdg_nodes": row["perturbed_nodes"],
                    "perturbed_pdg_edges": row["perturbed_edges"],
                },
                "xfg": action_detail.get("prediction", {}),
                "runtime_ms": row["runtime_ms"],
            },
        }
        write_json(
            output_dir / "runs" / "perturbed" / f"{row['sample_id']}__{row['action']}.json",
            payload,
        )

    archive_summaries = archive_action_summaries(perturbation_rows)
    write_csv(output_dir / "baseline_summary.csv", baseline_summary)
    write_csv(output_dir / "prediction_comparison.csv", comparison_rows)
    write_csv(output_dir / "action_summary.csv", archive_summaries)
    return archive_summaries


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    predictor = Predictor(args.checkpoint, args.threshold)
    sensi_api = Path("/workspace/data/sensiAPI.txt")
    csv_dirs = sorted(path for path in args.csv_root.iterdir() if (path / "nodes.csv").is_file())

    baseline_rows: list[dict[str, Any]] = []
    perturbation_rows: list[dict[str, Any]] = []
    details: dict[str, Any] = {}

    for sample_index, csv_dir in enumerate(csv_dirs, start=1):
        sample_id = csv_dir.name
        source = find_source(args.source_root, sample_id)
        if source is None:
            print(f"[{sample_index}/{len(csv_dirs)}] {sample_id}: source missing", flush=True)
            continue

        detected_function = function_name(source.read_text(encoding="utf-8", errors="replace"))
        try:
            pdg, key_line_map = build_PDG(str(csv_dir), str(sensi_api), str(source))
            if pdg is None or key_line_map is None:
                raise RuntimeError("build_PDG returned no graph")
            baseline = predictor.predict_graph(pdg, key_line_map)
        except Exception as exc:
            baseline_rows.append(
                {
                    "sample_id": sample_id,
                    "source_file": str(source),
                    "function": detected_function,
                    "status": "failed",
                    "probability": None,
                    "predicted_label": None,
                    "pdg_nodes": None,
                    "pdg_edges": None,
                    "xfg_count": None,
                    "runtime_ms": None,
                    "key_line_counts": {},
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            print(f"[{sample_index}/{len(csv_dirs)}] {sample_id}: baseline failed: {exc}", flush=True)
            continue

        key_line_counts = {name: len(lines) for name, lines in key_line_map.items()}
        baseline_row = {
            "sample_id": sample_id,
            "source_file": str(source),
            "function": detected_function,
            "status": baseline["status"],
            "probability": baseline["probability"],
            "predicted_label": baseline["predicted_label"],
            "pdg_nodes": pdg.number_of_nodes(),
            "pdg_edges": pdg.number_of_edges(),
            "xfg_count": baseline["xfg_count"],
            "runtime_ms": baseline["runtime_ms"],
            "key_line_counts": key_line_counts,
            "error": "",
        }
        baseline_rows.append(baseline_row)
        details[sample_id] = {"baseline": baseline, "actions": {}}

        print(
            f"[{sample_index}/{len(csv_dirs)}] {sample_id}: baseline "
            f"p={baseline['probability']:.6f}, label={baseline['predicted_label']}, "
            f"PDG={pdg.number_of_nodes()}/{pdg.number_of_edges()}, XFG={baseline['xfg_count']}",
            flush=True,
        )

        for action in ACTION_NAMES:
            action_started = time.perf_counter()
            row = {
                "sample_id": sample_id,
                "action": action,
                "strategy": args.strategy,
                "seed": args.seed,
                "requested_count": args.count,
                "applied_count": 0,
                "valid": False,
                "baseline_nodes": pdg.number_of_nodes(),
                "baseline_edges": pdg.number_of_edges(),
                "perturbed_nodes": None,
                "perturbed_edges": None,
                "delta_nodes": None,
                "delta_edges": None,
                "baseline_xfg_count": baseline["xfg_count"],
                "perturbed_xfg_count": None,
                "baseline_probability": baseline["probability"],
                "perturbed_probability": None,
                "delta_probability": None,
                "baseline_label": baseline["predicted_label"],
                "perturbed_label": None,
                "flipped": False,
                "runtime_ms": None,
                "operations": [],
                "validation_errors": [],
                "error": "",
            }
            try:
                result = apply_graph_action(
                    pdg,
                    action=action,
                    strategy=args.strategy,
                    key_lines=key_line_map,
                    count=args.count,
                    seed=args.seed,
                )
                row.update(
                    {
                        "applied_count": result.applied_count,
                        "valid": result.valid,
                        "perturbed_nodes": result.graph.number_of_nodes(),
                        "perturbed_edges": result.graph.number_of_edges(),
                        "delta_nodes": result.graph.number_of_nodes() - pdg.number_of_nodes(),
                        "delta_edges": result.graph.number_of_edges() - pdg.number_of_edges(),
                        "operations": [asdict(operation) for operation in result.operations],
                        "validation_errors": list(result.validation_errors),
                    }
                )
                if not result.valid or result.applied_count != args.count:
                    raise RuntimeError(result.notes or "graph action was not fully applied")
                prediction = predictor.predict_graph(result.graph, key_line_map)
                row.update(
                    {
                        "perturbed_xfg_count": prediction["xfg_count"],
                        "perturbed_probability": prediction["probability"],
                        "delta_probability": prediction["probability"] - baseline["probability"],
                        "perturbed_label": prediction["predicted_label"],
                        "flipped": prediction["predicted_label"] != baseline["predicted_label"],
                    }
                )
                details[sample_id]["actions"][action] = {"result": row, "prediction": prediction}
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
                details[sample_id]["actions"][action] = {"result": row}
            row["runtime_ms"] = (time.perf_counter() - action_started) * 1000.0
            perturbation_rows.append(row)
            probability_text = (
                f"{float(row['perturbed_probability']):.6f}" if row["perturbed_probability"] is not None else "NA"
            )
            print(
                f"  {action}: applied={row['applied_count']}, valid={row['valid']}, "
                f"p={probability_text}, flip={row['flipped']}, error={row['error'] or 'none'}",
                flush=True,
            )

    metrics = action_summaries(perturbation_rows)
    elapsed = time.perf_counter() - started
    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": args.experiment,
        "dataset": args.dataset,
        "strategy": args.strategy,
        "seed": args.seed,
        "count": args.count,
        "threshold": args.threshold,
        "device": str(predictor.device),
        "samples_discovered": len(csv_dirs),
        "baselines_completed": sum(not row["error"] for row in baseline_rows),
        "perturbations_attempted": len(perturbation_rows),
        "perturbations_successful": sum(not row["error"] and row["valid"] for row in perturbation_rows),
        "label_flips": sum(int(row["flipped"]) for row in perturbation_rows),
        "elapsed_seconds": elapsed,
        "actions": list(ACTION_NAMES),
    }

    write_csv(args.output_dir / "baseline_predictions.csv", baseline_rows)
    write_csv(args.output_dir / "perturbation_results.csv", perturbation_rows)
    write_json(args.output_dir / "details.json", details)
    archive_summaries = write_archive_layout(args.output_dir, baseline_rows, perturbation_rows, details, metadata)
    write_csv(args.output_dir / "action_metrics.csv", metrics)
    write_json(
        args.output_dir / "summary.json",
        {"metadata": metadata, "action_summary": archive_summaries, "action_metrics": metrics},
    )
    print(json.dumps(metadata, indent=2), flush=True)
    return 0 if metadata["perturbations_successful"] == metadata["perturbations_attempted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
