from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASELINE_ROOT = Path("/baseline")
WORKSPACE_ROOT = Path("/workspace")


sys.path.insert(0, str(BASELINE_ROOT / "scripts"))
from infer_single_source import add_symbols, count_tsv_rows, normalized_joern_script  # noqa: E402


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.12g}"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def run_joern_dir(source_dir: Path, output_dir: Path, timeout_seconds: int) -> dict[str, Any]:
    csv_dir = output_dir / "joern_csv"
    csv_dir.mkdir(parents=True, exist_ok=True)
    script = normalized_joern_script(Path("/workspace/joern/joern-parse"), output_dir)
    command = ["bash", str(script), str(csv_dir), str(source_dir)]
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            command,
            cwd=str(WORKSPACE_ROOT),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "parse_status": "failed",
            "error": f"joern timed out after {timeout_seconds}s",
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "csv_dir": str(csv_dir),
            "runtime_ms": (time.perf_counter() - started) * 1000.0,
        }
    nodes_files = sorted(csv_dir.rglob("nodes.csv"))
    edges_files = sorted(csv_dir.rglob("edges.csv"))
    status = "success" if proc.returncode == 0 and nodes_files and edges_files else "failed"
    error = None
    if status != "success":
        error = (
            f"joern failed or did not produce nodes.csv/edges.csv; returncode={proc.returncode}; "
            f"nodes={len(nodes_files)}; edges={len(edges_files)}"
        )
    return {
        "parse_status": status,
        "error": error,
        "command": command,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
        "csv_dir": str(csv_dir),
        "nodes_files": [str(path) for path in nodes_files],
        "edges_files": [str(path) for path in edges_files],
        "runtime_ms": (time.perf_counter() - started) * 1000.0,
    }


def select_csv_dir(nodes_files: list[Path], source_name: str, allow_single: bool) -> Path | None:
    source_lower = source_name.lower()
    for nodes_path in nodes_files:
        if nodes_path.parent.name.lower() == source_lower:
            return nodes_path.parent
    for nodes_path in nodes_files:
        if source_lower in str(nodes_path.parent).lower():
            return nodes_path.parent
    if allow_single and nodes_files:
        return nodes_files[0].parent
    return None


def copy_single_source(source_path: Path, output_dir: Path, index: int) -> Path:
    target_dir = output_dir / "_single_sources" / f"{index:06d}"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / source_path.name
    shutil.copyfile(source_path, target_path)
    return target_dir


class DeepWuKongPredictor:
    def __init__(self, checkpoint_path: Path, threshold: float, device_name: str) -> None:
        sys.path.insert(0, str(WORKSPACE_ROOT))
        import torch
        from src.data_generator import build_PDG, build_XFG
        from src.datas.graphs import XFG
        from src.models.vd import DeepWuKong
        from torch_geometric.data import Batch

        self.torch = torch
        self.build_PDG = build_PDG
        self.build_XFG = build_XFG
        self.XFG = XFG
        self.Batch = Batch
        self.threshold = threshold
        self.sensi_api_path = WORKSPACE_ROOT / "data" / "sensiAPI.txt"
        self.device = torch.device(device_name if device_name != "auto" else ("cuda:0" if torch.cuda.is_available() else "cpu"))
        self.model = DeepWuKong.load_from_checkpoint(checkpoint_path=str(checkpoint_path), weights_only=False).to(self.device)
        self.model.eval()
        self.config = self.model.hparams["config"]
        self.vocab = self.model.hparams["vocab"]

    def predict(self, source_path: Path, csv_root: Path) -> dict[str, Any]:
        pdg, key_line_map = self.build_PDG(str(csv_root), str(self.sensi_api_path), str(source_path))
        if pdg is None or key_line_map is None:
            return self.empty_prediction("no_pdg", {})
        xfg_dict = self.build_XFG(pdg, key_line_map)
        xfg_items = []
        for category, graphs in (xfg_dict or {}).items():
            for graph in graphs:
                xfg_items.append((category, graph))
        key_line_counts = {name: len(lines) for name, lines in key_line_map.items()}
        if not xfg_items:
            return self.empty_prediction("no_xfg", key_line_counts)

        data_list = []
        meta = []
        skipped_empty_xfg = 0
        for category, graph in xfg_items:
            graph = add_symbols(graph, self.config.split_token)
            data = self.XFG(xfg=graph).to_torch(self.vocab, self.config.dataset.token.max_parts)
            if data.x.numel() == 0 or data.edge_index.numel() == 0:
                skipped_empty_xfg += 1
                continue
            data_list.append(data)
            meta.append({"category": category, "key_line": graph.graph.get("key_line")})
        if not data_list:
            prediction = self.empty_prediction("no_xfg", key_line_counts)
            prediction["skipped_empty_xfg"] = skipped_empty_xfg
            return prediction

        batch = self.Batch.from_data_list(data_list).to(self.device)
        with self.torch.no_grad():
            logits = self.model(batch)
            probabilities = self.torch.softmax(logits, dim=1).detach().cpu().tolist()

        xfg_predictions = []
        max_vulnerable_probability = 0.0
        for item, probs in zip(meta, probabilities):
            vulnerable_probability = float(probs[1]) if len(probs) > 1 else 0.0
            max_vulnerable_probability = max(max_vulnerable_probability, vulnerable_probability)
            item.update(
                {
                    "vulnerability_probability": vulnerable_probability,
                    "predicted_label": int(vulnerable_probability >= self.threshold),
                    "confidence": max(float(value) for value in probs),
                }
            )
            xfg_predictions.append(item)
        predicted_label = int(max_vulnerable_probability >= self.threshold)
        confidence = max_vulnerable_probability if predicted_label == 1 else 1.0 - max_vulnerable_probability
        return {
            "prediction_status": "ok",
            "probability": max_vulnerable_probability,
            "predicted_label": predicted_label,
            "confidence": confidence,
            "xfg_count": len(xfg_predictions),
            "xfg_predictions": xfg_predictions,
            "key_line_counts": key_line_counts,
            "skipped_empty_xfg": skipped_empty_xfg,
            "device": str(self.device),
        }

    def empty_prediction(self, status: str, key_line_counts: dict[str, int]) -> dict[str, Any]:
        return {
            "prediction_status": status,
            "probability": 0.0,
            "predicted_label": 0,
            "confidence": 1.0,
            "xfg_count": 0,
            "xfg_predictions": [],
            "key_line_counts": key_line_counts,
            "device": str(self.device),
        }


def binary_metrics(labels: list[int], predictions: list[int], scores: list[float]) -> dict[str, Any]:
    total = len(labels)
    tp = sum(1 for label, pred in zip(labels, predictions) if label == 1 and pred == 1)
    tn = sum(1 for label, pred in zip(labels, predictions) if label == 0 and pred == 0)
    fp = sum(1 for label, pred in zip(labels, predictions) if label == 0 and pred == 1)
    fn = sum(1 for label, pred in zip(labels, predictions) if label == 1 and pred == 0)
    accuracy = (tp + tn) / total if total else None
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    specificity = tn / (tn + fp) if (tn + fp) else 0.0
    f1 = (2.0 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    balanced_accuracy = (recall + specificity) / 2.0
    mcc_den = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    mcc = ((tp * tn) - (fp * fn)) / mcc_den if mcc_den else 0.0
    return {
        "samples": total,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "specificity": specificity,
        "balanced_accuracy": balanced_accuracy,
        "mcc": mcc,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "class_0": sum(1 for label in labels if label == 0),
        "class_1": sum(1 for label in labels if label == 1),
        "prediction_0": sum(1 for pred in predictions if pred == 0),
        "prediction_1": sum(1 for pred in predictions if pred == 1),
        "average_score": (sum(scores) / len(scores)) if scores else None,
    }


def group_metrics(rows: list[dict[str, Any]], group_field: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(group_field) or "unknown")].append(row)
    output_rows: list[dict[str, Any]] = []
    for group in sorted(grouped):
        values = grouped[group]
        predicted = [row for row in values if row.get("predicted_label") in (0, 1)]
        labels = [int(row["target"]) for row in predicted]
        preds = [int(row["predicted_label"]) for row in predicted]
        scores = [float(row["probability"]) for row in predicted]
        metrics = binary_metrics(labels, preds, scores)
        total = len(values)
        correct_predicted = sum(1 for row in predicted if int(row["target"]) == int(row["predicted_label"]))
        status_counts = Counter(str(row.get("prediction_status") or "unknown") for row in values)
        output_rows.append(
            {
                group_field: group,
                "total_samples": total,
                "predicted_samples": len(predicted),
                "no_prediction_samples": total - len(predicted),
                "accuracy_all": correct_predicted / total if total else None,
                "accuracy_predicted": metrics["accuracy"],
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1": metrics["f1"],
                "specificity": metrics["specificity"],
                "balanced_accuracy": metrics["balanced_accuracy"],
                "mcc": metrics["mcc"],
                "tp": metrics["tp"],
                "tn": metrics["tn"],
                "fp": metrics["fp"],
                "fn": metrics["fn"],
                "class_0": sum(1 for row in values if int(row["target"]) == 0),
                "class_1": sum(1 for row in values if int(row["target"]) == 1),
                "prediction_0": metrics["prediction_0"],
                "prediction_1": metrics["prediction_1"],
                "ok": status_counts["ok"],
                "no_xfg": status_counts["no_xfg"],
                "no_pdg": status_counts["no_pdg"],
                "joern_failed": status_counts["joern_failed"],
                "inference_failed": status_counts["inference_failed"],
                "csv_missing": status_counts["csv_missing"],
                "average_score": metrics["average_score"],
            }
        )
    return output_rows


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field)) for field in fields})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Container-side DeepWuKong Devign evaluator.")
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--joern-timeout", type=int, default=900)
    parser.add_argument("--progress-every", type=int, default=25)
    return parser.parse_args()


def evaluate(args: argparse.Namespace) -> list[dict[str, Any]]:
    records = read_jsonl(args.metadata)
    chunks: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        chunks[str(record["chunk"])].append(record)
    predictor = DeepWuKongPredictor(args.checkpoint, args.threshold, args.device)
    results: list[dict[str, Any]] = []
    started = time.perf_counter()
    processed = 0
    chunk_logs = []

    for chunk_name in sorted(chunks):
        chunk_records = chunks[chunk_name]
        source_dir = args.source_root / chunk_name
        chunk_output = args.output_dir / "joern_chunks" / chunk_name
        joern_stats = run_joern_dir(source_dir, chunk_output, args.joern_timeout)
        chunk_logs.append({"chunk": chunk_name, **joern_stats})
        nodes_files = [Path(path) for path in joern_stats.get("nodes_files", [])]
        chunk_failed = joern_stats["parse_status"] != "success"
        for record in chunk_records:
            processed += 1
            row_started = time.perf_counter()
            source_path = args.source_root / record["relative_source_path"]
            row: dict[str, Any] = {
                **record,
                "threshold": args.threshold,
                "joern_status": joern_stats["parse_status"],
                "prediction_status": None,
                "predicted_label": None,
                "probability": None,
                "confidence": None,
                "correct": 0,
                "num_nodes": None,
                "num_edges": None,
                "xfg_count": None,
                "error": "",
                "runtime_ms": None,
            }
            try:
                selected_csv_dir = None
                if not chunk_failed:
                    selected_csv_dir = select_csv_dir(nodes_files, source_path.name, allow_single=len(chunk_records) == 1)
                if selected_csv_dir is None:
                    single_source_dir = copy_single_source(source_path, args.output_dir, int(record["index"]))
                    single_output = args.output_dir / "joern_single" / f"{int(record['index']):06d}"
                    single_stats = run_joern_dir(single_source_dir, single_output, args.joern_timeout)
                    row["joern_status"] = single_stats["parse_status"]
                    if single_stats["parse_status"] == "success":
                        single_nodes = [Path(path) for path in single_stats.get("nodes_files", [])]
                        selected_csv_dir = select_csv_dir(single_nodes, source_path.name, allow_single=True)
                    else:
                        row["prediction_status"] = "joern_failed"
                        row["error"] = single_stats.get("error") or joern_stats.get("error") or "joern failed"
                if selected_csv_dir is None and not row["prediction_status"]:
                    row["prediction_status"] = "csv_missing"
                    row["error"] = "No per-file Joern CSV directory was found."
                if selected_csv_dir is not None:
                    row["selected_csv_dir"] = str(selected_csv_dir)
                    row["num_nodes"] = count_tsv_rows(selected_csv_dir / "nodes.csv")
                    row["num_edges"] = count_tsv_rows(selected_csv_dir / "edges.csv")
                    prediction = predictor.predict(source_path, selected_csv_dir)
                    row["prediction_status"] = prediction["prediction_status"]
                    row["predicted_label"] = int(prediction["predicted_label"])
                    row["probability"] = float(prediction["probability"])
                    row["confidence"] = float(prediction["confidence"])
                    row["xfg_count"] = int(prediction["xfg_count"])
                    row["correct"] = int(int(row["target"]) == int(row["predicted_label"]))
            except Exception as exc:
                row["prediction_status"] = "inference_failed"
                row["error"] = f"{type(exc).__name__}: {exc}"
            row["runtime_ms"] = (time.perf_counter() - row_started) * 1000.0
            results.append(row)
            if args.progress_every and processed % args.progress_every == 0:
                elapsed = time.perf_counter() - started
                print(f"Processed {processed}/{len(records)} samples in {elapsed:.1f}s", flush=True)
    write_json(args.output_dir / "joern_chunk_logs.json", chunk_logs)
    return results


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = evaluate(args)
    prediction_fields = [
        "index",
        "sample_id",
        "dataset",
        "project",
        "commit_id",
        "source_index",
        "official_split",
        "target",
        "predicted_label",
        "probability",
        "confidence",
        "threshold",
        "correct",
        "joern_status",
        "prediction_status",
        "num_nodes",
        "num_edges",
        "xfg_count",
        "relative_source_path",
        "selected_csv_dir",
        "error",
        "runtime_ms",
    ]
    write_csv(args.output_dir / "predictions.csv", results, prediction_fields)
    project_rows = group_metrics(results, "project")
    metric_fields = [
        "project",
        "total_samples",
        "predicted_samples",
        "no_prediction_samples",
        "accuracy_all",
        "accuracy_predicted",
        "precision",
        "recall",
        "f1",
        "specificity",
        "balanced_accuracy",
        "mcc",
        "tp",
        "tn",
        "fp",
        "fn",
        "class_0",
        "class_1",
        "prediction_0",
        "prediction_1",
        "ok",
        "no_xfg",
        "no_pdg",
        "joern_failed",
        "inference_failed",
        "csv_missing",
        "average_score",
    ]
    write_csv(args.output_dir / "per_project_metrics.csv", project_rows, metric_fields)
    overall_rows = group_metrics(results, "dataset")
    overall_fields = ["dataset" if field == "project" else field for field in metric_fields]
    normalized_overall = []
    for row in overall_rows:
        normalized = {"dataset": row.pop("dataset", row.pop("project", "unknown")), **row}
        normalized_overall.append(normalized)
    write_csv(args.output_dir / "per_dataset_metrics.csv", normalized_overall, overall_fields)
    write_json(
        args.output_dir / "summary.json",
        {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "threshold": args.threshold,
            "checkpoint": str(args.checkpoint),
            "projects": project_rows,
            "datasets": normalized_overall,
            "status_counts": dict(Counter(str(row.get("prediction_status") or "unknown") for row in results)),
        },
    )
    print(json.dumps({"projects": project_rows, "status_counts": dict(Counter(str(row.get("prediction_status") or "unknown") for row in results))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
