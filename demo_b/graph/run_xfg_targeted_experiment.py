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

if Path("/workspace").is_dir():
    sys.path.insert(0, "/workspace")
if Path("/baseline/scripts").is_dir():
    sys.path.insert(0, "/baseline/scripts")
sys.path.insert(0, str(PROJECT_ROOT))

from demo_b.graph.graph_perturbations import (  # noqa: E402
    XFG_TARGETED_ACTION_NAMES,
    apply_xfg_targeted_action,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run winner-XFG-targeted DeepWuKong graph attacks.")
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--csv-root", required=True, type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--actions", nargs="+", choices=XFG_TARGETED_ACTION_NAMES, default=list(XFG_TARGETED_ACTION_NAMES))
    parser.add_argument("--budgets", nargs="+", type=int, default=[1, 3, 5])
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--include-baseline-errors", action="store_true")
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


def read_metadata(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sorted(csv.DictReader(handle), key=lambda row: row["sample_id"])


def find_source(source_root: Path, sample_id: str) -> Path | None:
    matches = sorted(path for path in source_root.rglob(f"{sample_id}.*") if path.is_file())
    return matches[0] if matches else None


def effective_winner_nodes(pdg: Any, winner: dict[str, Any], limit: int = 5) -> tuple[list[int], str]:
    if limit < 1:
        raise ValueError("limit must be at least 1")

    graph_nodes = {int(node) for node in pdg.nodes}
    active_nodes = sorted(graph_nodes.intersection(int(node) for node in winner.get("nodes", [])))
    if active_nodes:
        return active_nodes, "winner_xfg"
    if not graph_nodes:
        raise ValueError("cannot select a winner neighborhood from an empty PDG")

    key_line = int(winner["key_line"])
    nearest_nodes = sorted(
        graph_nodes,
        key=lambda node: (abs(node - key_line), -pdg.degree(node), node),
    )
    return nearest_nodes[: min(limit, len(nearest_nodes))], "nearest_pdg_nodes"


class Predictor:
    def __init__(self, checkpoint: Path, threshold: float) -> None:
        import torch
        from torch_geometric.data import Batch

        from infer_single_source import add_symbols
        from src.data_generator import build_XFG
        from src.datas.graphs import XFG
        from src.models.vd import DeepWuKong

        self.torch = torch
        self.Batch = Batch
        self.XFG = XFG
        self.add_symbols = add_symbols
        self.build_XFG = build_XFG
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
        xfg_dict = self.build_XFG(pdg, key_line_map) or {}
        data_list = []
        metadata = []

        for category, graphs in xfg_dict.items():
            for graph in graphs:
                graph = self.add_symbols(graph, self.config.split_token)
                data = self.XFG(xfg=graph).to_torch(self.vocab, self.config.dataset.token.max_parts)
                data_list.append(data)
                metadata.append(
                    {
                        "category": category,
                        "key_line": int(graph.graph.get("key_line")),
                        "nodes": [int(node) for node in graph.nodes],
                    }
                )

        if not data_list:
            return {
                "status": "no_xfg",
                "probability": 0.0,
                "predicted_label": 0,
                "xfg_count": 0,
                "xfg_predictions": [],
                "winner": None,
                "runtime_ms": (time.perf_counter() - started) * 1000.0,
            }

        batch = self.Batch.from_data_list(data_list).to(self.device)
        with self.torch.no_grad():
            probabilities = self.torch.softmax(self.model(batch), dim=1).detach().cpu().tolist()

        predictions = []
        for meta, values in zip(metadata, probabilities):
            probability = float(values[1]) if len(values) > 1 else 0.0
            predictions.append(
                {
                    **meta,
                    "vulnerability_probability": probability,
                    "predicted_label": int(probability >= self.threshold),
                }
            )
        winner = max(predictions, key=lambda row: row["vulnerability_probability"])
        probability = float(winner["vulnerability_probability"])
        return {
            "status": "ok",
            "probability": probability,
            "predicted_label": int(probability >= self.threshold),
            "xfg_count": len(predictions),
            "xfg_predictions": predictions,
            "winner": {
                "category": winner["category"],
                "key_line": winner["key_line"],
                "nodes": winner["nodes"],
                "probability": winner["vulnerability_probability"],
            },
            "runtime_ms": (time.perf_counter() - started) * 1000.0,
        }


def summarize(rows: list[dict[str, Any]], actions: list[str], budgets: list[int]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["action"]), int(row["budget"]))].append(row)
    output = []
    for action in actions:
        for budget in budgets:
            group = grouped[(action, budget)]
            successful = [row for row in group if row["status"] == "success"]
            deltas = [float(row["delta_probability"]) for row in successful]
            output.append(
                {
                    "action": action,
                    "budget": budget,
                    "attempted": len(group),
                    "successful": len(successful),
                    "failed": len(group) - len(successful),
                    "flips": sum(int(row["flipped"]) for row in successful),
                    "attack_successes": sum(int(row["attack_success"]) for row in successful),
                    "attack_success_rate": (
                        sum(int(row["attack_success"]) for row in successful) / len(successful)
                        if successful
                        else None
                    ),
                    "mean_delta_probability": sum(deltas) / len(deltas) if deltas else None,
                    "mean_absolute_delta_probability": (
                        sum(abs(value) for value in deltas) / len(deltas) if deltas else None
                    ),
                    "max_absolute_delta_probability": max((abs(value) for value in deltas), default=None),
                    "mean_applied_count": (
                        sum(int(row["applied_count"]) for row in successful) / len(successful)
                        if successful
                        else None
                    ),
                }
            )
    return output


def main() -> int:
    args = parse_args()
    if any(budget < 1 for budget in args.budgets):
        raise ValueError("all budgets must be at least 1")
    actions = list(dict.fromkeys(args.actions))
    budgets = sorted(set(args.budgets))
    args.output_dir.mkdir(parents=True, exist_ok=True)

    from infer_single_source import function_name
    from src.data_generator import build_PDG

    started = time.perf_counter()
    predictor = Predictor(args.checkpoint, args.threshold)
    sensi_api = Path("/workspace/data/sensiAPI.txt")
    baseline_rows: list[dict[str, Any]] = []
    attack_rows: list[dict[str, Any]] = []

    records = read_metadata(args.metadata)
    for index, record in enumerate(records, start=1):
        sample_id = record["sample_id"]
        true_label = int(record["label"])
        source = find_source(args.source_root, sample_id)
        csv_dir = args.csv_root / sample_id
        if source is None or not (csv_dir / "nodes.csv").is_file():
            print(f"[{index}/{len(records)}] {sample_id}: source or CSV missing", flush=True)
            continue

        source_function = function_name(source.read_text(encoding="utf-8", errors="replace"))
        pdg, key_line_map = build_PDG(str(csv_dir), str(sensi_api), str(source))
        if pdg is None or key_line_map is None:
            print(f"[{index}/{len(records)}] {sample_id}: no PDG", flush=True)
            continue
        baseline = predictor.predict_graph(pdg, key_line_map)
        baseline_correct = int(baseline["predicted_label"] == true_label)
        winner = baseline.get("winner")
        winner_nodes: list[int] = []
        winner_fallback: str | None = None
        if winner is not None:
            winner_nodes, winner_fallback = effective_winner_nodes(pdg, winner)
        baseline_row = {
            "sample": sample_id,
            "function": source_function,
            "true_label": true_label,
            "status": baseline["status"],
            "label": baseline["predicted_label"],
            "correct": baseline_correct,
            "prob": baseline["probability"],
            "nodes": pdg.number_of_nodes(),
            "edges": pdg.number_of_edges(),
            "xfg_count": baseline["xfg_count"],
            "winner_category": winner["category"] if winner else None,
            "winner_key_line": winner["key_line"] if winner else None,
            "winner_raw_nodes": len(winner["nodes"]) if winner else 0,
            "winner_nodes": len(winner_nodes),
            "winner_fallback": winner_fallback,
        }
        baseline_rows.append(baseline_row)
        write_json(
            args.output_dir / "runs" / "baseline" / f"{sample_id}.json",
            {"prediction": baseline_row, "details": baseline},
        )
        print(
            f"[{index}/{len(records)}] {sample_id}: true={true_label}, "
            f"baseline={baseline['predicted_label']} p={baseline['probability']:.6f}, "
            f"correct={bool(baseline_correct)}, winner={winner['key_line'] if winner else 'none'}",
            flush=True,
        )

        if (not baseline_correct and not args.include_baseline_errors) or winner is None:
            continue
        target_label = 1 - true_label
        for action in actions:
            for budget in budgets:
                attack_started = time.perf_counter()
                row = {
                    "sample": sample_id,
                    "action": action,
                    "budget": budget,
                    "function": source_function,
                    "true_label": true_label,
                    "target_label": target_label,
                    "status": "failed",
                    "base_label": baseline["predicted_label"],
                    "variant_label": None,
                    "flipped": False,
                    "attack_success": False,
                    "base_prob": baseline["probability"],
                    "variant_prob": None,
                    "delta_probability": None,
                    "base_nodes": pdg.number_of_nodes(),
                    "variant_nodes": None,
                    "delta_nodes": None,
                    "base_edges": pdg.number_of_edges(),
                    "variant_edges": None,
                    "delta_edges": None,
                    "base_xfg_count": baseline["xfg_count"],
                    "variant_xfg_count": None,
                    "winner_category": winner["category"],
                    "winner_key_line": winner["key_line"],
                    "winner_raw_nodes": len(winner["nodes"]),
                    "winner_nodes": len(winner_nodes),
                    "winner_fallback": winner_fallback,
                    "applied_count": 0,
                    "runtime_ms": None,
                    "operations": [],
                    "error": "",
                }
                prediction = None
                try:
                    result = apply_xfg_targeted_action(
                        pdg,
                        action=action,
                        winner_nodes=winner_nodes,
                        winner_key_line=int(winner["key_line"]),
                        target_label=target_label,
                        budget=budget,
                        key_lines=key_line_map,
                        seed=args.seed,
                    )
                    row.update(
                        {
                            "applied_count": result.applied_count,
                            "variant_nodes": result.graph.number_of_nodes(),
                            "variant_edges": result.graph.number_of_edges(),
                            "delta_nodes": result.graph.number_of_nodes() - pdg.number_of_nodes(),
                            "delta_edges": result.graph.number_of_edges() - pdg.number_of_edges(),
                            "operations": [asdict(operation) for operation in result.operations],
                        }
                    )
                    if not result.valid or result.applied_count == 0:
                        raise RuntimeError(result.notes or "targeted action was not fully applied")
                    prediction = predictor.predict_graph(result.graph, key_line_map)
                    variant_label = int(prediction["predicted_label"])
                    row.update(
                        {
                            "status": "success",
                            "variant_label": variant_label,
                            "flipped": variant_label != baseline["predicted_label"],
                            "attack_success": variant_label != true_label,
                            "variant_prob": prediction["probability"],
                            "delta_probability": prediction["probability"] - baseline["probability"],
                            "variant_xfg_count": prediction["xfg_count"],
                        }
                    )
                except Exception as exc:
                    row["error"] = f"{type(exc).__name__}: {exc}"
                row["runtime_ms"] = (time.perf_counter() - attack_started) * 1000.0
                attack_rows.append(row)
                write_json(
                    args.output_dir / "runs" / "perturbed" / f"{sample_id}__{action}__b{budget}.json",
                    {"comparison": row, "prediction": prediction},
                )
                probability_text = f"{row['variant_prob']:.6f}" if row["variant_prob"] is not None else "NA"
                print(
                    f"  {action} b={budget}: p={probability_text}, flip={row['flipped']}, "
                    f"attack_success={row['attack_success']}, error={row['error'] or 'none'}",
                    flush=True,
                )

    action_summary = summarize(attack_rows, actions, budgets)
    successful = [row for row in attack_rows if row["status"] == "success"]
    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "winner_xfg_targeted_cwe119_round_2",
        "strategy": "winner_xfg_targeted",
        "seed": args.seed,
        "threshold": args.threshold,
        "device": str(predictor.device),
        "actions": actions,
        "budgets": budgets,
        "baseline_samples": len(baseline_rows),
        "baseline_correct_samples": sum(int(row["correct"]) for row in baseline_rows),
        "attacks_attempted": len(attack_rows),
        "attacks_successfully_scored": len(successful),
        "failed_attacks": len(attack_rows) - len(successful),
        "prediction_flips": sum(int(row["flipped"]) for row in successful),
        "attack_successes": sum(int(row["attack_success"]) for row in successful),
        "attack_success_rate": (
            sum(int(row["attack_success"]) for row in successful) / len(successful) if successful else None
        ),
        "elapsed_seconds": time.perf_counter() - started,
    }
    write_csv(args.output_dir / "baseline_summary.csv", baseline_rows)
    write_csv(args.output_dir / "prediction_comparison.csv", attack_rows)
    write_csv(args.output_dir / "action_summary.csv", action_summary)
    write_json(args.output_dir / "summary.json", {"metadata": metadata, "action_summary": action_summary})
    print(json.dumps(metadata, indent=2), flush=True)
    return 0 if metadata["failed_attacks"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
