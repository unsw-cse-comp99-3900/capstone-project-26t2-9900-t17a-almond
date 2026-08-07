from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def function_name(source_code: str) -> str:
    pattern = re.compile(
        r"\b(?:static\s+|inline\s+|extern\s+)*[A-Za-z_][\w\s\*]*\s+([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{",
        re.MULTILINE,
    )
    match = pattern.search(source_code)
    return match.group(1) if match else "unknown"


def host_sample_id(host_source_path: str) -> str:
    if "\\" in host_source_path or ":" in host_source_path:
        return PureWindowsPath(host_source_path).stem
    return Path(host_source_path).stem


def normalized_joern_script(joern_bin: Path, output_dir: Path) -> Path:
    script = output_dir / "_work" / "joern-parse-lf.sh"
    text = joern_bin.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace('BASEDIR=$(dirname "$0")', 'BASEDIR="/workspace/joern"')
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(text, encoding="utf-8", newline="\n")
    script.chmod(0o755)
    return script


def run_joern(joern_bin: Path, source_path: Path, output_dir: Path, timeout_seconds: int) -> dict[str, Any]:
    csv_dir = output_dir / "joern_csv"
    csv_dir.mkdir(parents=True, exist_ok=True)
    script = normalized_joern_script(joern_bin, output_dir)
    command = ["bash", str(script), str(csv_dir), str(source_path.parent)]
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            command,
            cwd="/workspace",
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
    selected_nodes = None
    source_name = source_path.name.lower()
    for candidate in nodes_files:
        parent_text = str(candidate.parent).lower()
        if source_name in parent_text:
            selected_nodes = candidate
            break
    if selected_nodes is None and nodes_files:
        selected_nodes = nodes_files[0]
    selected_dir = selected_nodes.parent if selected_nodes else None
    selected_edges = selected_dir / "edges.csv" if selected_dir else None

    status = "success" if proc.returncode == 0 and selected_nodes and selected_edges and selected_edges.exists() else "failed"
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
        "selected_csv_dir": str(selected_dir) if selected_dir else None,
        "runtime_ms": (time.perf_counter() - started) * 1000.0,
    }


def count_tsv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def add_symbols(xfg: Any, split_token: bool) -> Any:
    from src.preprocess.symbolizer import clean_gadget, tokenize_code_line

    file_path = Path(xfg.graph["file_paths"][0])
    file_contents = file_path.read_text(encoding="utf-8", errors="ignore").splitlines(True)
    code_lines = []
    for node in xfg:
        source_line = xfg.nodes[node].get("source_line", node)
        line_index = int(source_line) - 1
        code_lines.append(file_contents[line_index] if 0 <= line_index < len(file_contents) else "")
    sym_code_lines = clean_gadget(code_lines)
    for idx, node in enumerate(xfg):
        xfg.nodes[node]["code_sym_token"] = tokenize_code_line(sym_code_lines[idx], split_token)
    return xfg


def predict_deepwukong(
    source_path: Path,
    checkpoint_path: Path,
    csv_root: Path,
    threshold: float,
    device_name: str,
) -> dict[str, Any]:
    sys.path.insert(0, "/workspace")
    import torch
    from src.data_generator import build_PDG, build_XFG
    from src.datas.graphs import XFG
    from src.models.vd import DeepWuKong
    from torch_geometric.data import Batch

    sensi_api_path = Path("/workspace/data/sensiAPI.txt")
    pdg, key_line_map = build_PDG(str(csv_root), str(sensi_api_path), str(source_path))
    if pdg is None or key_line_map is None:
        return {
            "probability": 0.0,
            "predicted_label": 0,
            "confidence": 1.0,
            "xfg_count": 0,
            "xfg_predictions": [],
            "key_line_counts": {},
            "warning": "Joern CSV was parsed, but DeepWuKong did not find sensitive XFG seed lines.",
        }

    xfg_dict = build_XFG(pdg, key_line_map)
    xfg_items = []
    for category, graphs in (xfg_dict or {}).items():
        for graph in graphs:
            xfg_items.append((category, graph))
    if not xfg_items:
        return {
            "probability": 0.0,
            "predicted_label": 0,
            "confidence": 1.0,
            "xfg_count": 0,
            "xfg_predictions": [],
            "key_line_counts": {name: len(lines) for name, lines in key_line_map.items()},
            "warning": "No XFG slices were generated from the sensitive seed lines.",
        }

    device = torch.device(device_name if device_name != "auto" else ("cuda:0" if torch.cuda.is_available() else "cpu"))
    model = DeepWuKong.load_from_checkpoint(checkpoint_path=str(checkpoint_path), weights_only=False).to(device)
    model.eval()
    config = model.hparams["config"]
    vocab = model.hparams["vocab"]

    data_list = []
    meta = []
    for category, graph in xfg_items:
        graph = add_symbols(graph, config.split_token)
        data_list.append(XFG(xfg=graph).to_torch(vocab, config.dataset.token.max_parts))
        meta.append({"category": category, "key_line": graph.graph.get("key_line")})

    batch = Batch.from_data_list(data_list).to(device)
    with torch.no_grad():
        logits = model(batch)
        probabilities = torch.softmax(logits, dim=1).detach().cpu().tolist()

    xfg_predictions = []
    max_vulnerable_probability = 0.0
    for item, probs in zip(meta, probabilities):
        vulnerable_probability = float(probs[1]) if len(probs) > 1 else 0.0
        max_vulnerable_probability = max(max_vulnerable_probability, vulnerable_probability)
        item.update(
            {
                "vulnerability_probability": vulnerable_probability,
                "predicted_label": int(vulnerable_probability >= threshold),
                "confidence": max(float(value) for value in probs),
            }
        )
        xfg_predictions.append(item)

    predicted_label = int(max_vulnerable_probability >= threshold)
    confidence = max_vulnerable_probability if predicted_label == 1 else 1.0 - max_vulnerable_probability
    return {
        "probability": max_vulnerable_probability,
        "predicted_label": predicted_label,
        "confidence": confidence,
        "xfg_count": len(xfg_predictions),
        "xfg_predictions": xfg_predictions,
        "key_line_counts": {name: len(lines) for name, lines in key_line_map.items()},
        "warning": None,
        "device": str(device),
    }


def write_prediction_outputs(output_dir: Path, row: dict[str, Any], details: dict[str, Any]) -> None:
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "prediction": row,
        "details": details,
    }
    write_json(output_dir / "predictions.json", payload)
    write_json(output_dir / "run_metadata.json", details)
    write_json(output_dir / "joern_graph_stats.json", details.get("joern_stats", {}))
    with (output_dir / "predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)
    label_name = "vulnerable" if row["predicted_label"] == 1 else "non_vulnerable"
    report = f"""# DeepWuKong Prediction Report

Input file: `{row["input_file"]}`

Prediction: `{label_name}`

Vulnerability probability: `{row["vulnerability_probability"]:.6f}`

Confidence: `{row["confidence"]:.6f}`

XFG slices scored: `{details.get("features", {}).get("xfg", {}).get("xfg_count", 0)}`

Joern status: `{row["joern_status"]}`
"""
    (output_dir / "inference_report.txt").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DeepWuKong inference for one source file inside the Docker image.")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--host-source-path", required=True)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--joern-timeout", type=int, default=600)
    args = parser.parse_args()

    started = time.perf_counter()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_code = args.source.read_text(encoding="utf-8", errors="replace")

    work_source_dir = output_dir / "_work" / "source"
    work_source_dir.mkdir(parents=True, exist_ok=True)
    work_source = work_source_dir / args.source.name
    shutil.copyfile(args.source, work_source)

    joern_stats = run_joern(
        joern_bin=Path("/workspace/joern/joern-parse"),
        source_path=work_source,
        output_dir=output_dir,
        timeout_seconds=args.joern_timeout,
    )
    if joern_stats["parse_status"] != "success":
        raise RuntimeError(joern_stats["error"] or "joern failed")

    csv_root = Path(str(joern_stats["selected_csv_dir"]))
    prediction = predict_deepwukong(
        source_path=work_source,
        checkpoint_path=args.checkpoint,
        csv_root=csv_root,
        threshold=args.threshold,
        device_name=args.device,
    )
    nodes_count = count_tsv_rows(csv_root / "nodes.csv")
    edges_count = count_tsv_rows(csv_root / "edges.csv")
    probability = float(prediction["probability"])
    predicted_label = int(prediction["predicted_label"])
    confidence = float(prediction["confidence"])

    row = {
        "sample_id": host_sample_id(args.host_source_path),
        "input_file": args.host_source_path,
        "function_name": function_name(source_code),
        "joern_status": joern_stats["parse_status"],
        "num_nodes": nodes_count,
        "num_edges": edges_count,
        "predicted_label": predicted_label,
        "vulnerability_probability": probability,
        "threshold": args.threshold,
        "confidence": confidence,
        "lexical_score": None,
        "graph_score": probability,
        "fusion_status": "deepwukong_xfg_max",
        "unixcoder_score": None,
        "codet5_score": None,
        "graphcodebert_score": None,
        "final_score": probability,
    }
    branch = {
        "new_graph_prob": {
            "score": probability,
            "status": "ok",
            "model": str(args.checkpoint),
            "xfg_count": prediction["xfg_count"],
        },
        "old_graph_prob": {"score": None, "status": "skipped", "reason": "DeepWuKong single-branch baseline"},
        "lexical_prob": {"score": None, "status": "skipped", "reason": "DeepWuKong full mode does not use lexical branch"},
        "unixcoder_prob": {"score": None, "status": "skipped", "reason": "DeepWuKong full mode does not use transformer branch"},
        "graphcodebert_prob": {"score": None, "status": "skipped", "reason": "DeepWuKong full mode does not use transformer branch"},
        "codet5_prob": {"score": None, "status": "skipped", "reason": "DeepWuKong full mode does not use transformer branch"},
        "unixcoder_seed13_prob": {"score": None, "status": "skipped", "reason": "DeepWuKong full mode does not use transformer branch"},
        "unixcoder_seed42_prob": {"score": None, "status": "skipped", "reason": "DeepWuKong full mode does not use transformer branch"},
        "unixcoder_seed2025_prob": {"score": None, "status": "skipped", "reason": "DeepWuKong full mode does not use transformer branch"},
    }
    details = {
        "baseline": "deepwukong_xfg_baseline",
        "selection": {
            "model": "DeepWuKong GCN CWE119",
            "checkpoint": str(args.checkpoint),
            "threshold": args.threshold,
            "source_aggregation": "max_xfg_vulnerability_probability",
        },
        "joern_stats": {
            **joern_stats,
            "node_count": nodes_count,
            "edge_count": edges_count,
            "summary": {"node_count": nodes_count, "edge_count": edges_count},
        },
        "features": {
            "source": {
                "function_name": row["function_name"],
                "char_length": len(source_code),
                "line_count": len(source_code.splitlines()),
            },
            "graph": {
                "available": True,
                "node_count": nodes_count,
                "edge_count": edges_count,
            },
            "xfg": {
                "xfg_count": prediction["xfg_count"],
                "key_line_counts": prediction["key_line_counts"],
                "xfg_predictions": prediction["xfg_predictions"],
            },
        },
        "branch_results": branch,
        "component_scores": {"new_graph_prob": probability},
        "fusion": {
            "fusion_status": "deepwukong_xfg_max",
            "available_components": ["new_graph_prob"],
            "missing_components": [],
            "final_score": probability,
            "predicted_label": predicted_label,
            "confidence": confidence,
            "threshold": args.threshold,
        },
        "runtime_ms": (time.perf_counter() - started) * 1000.0,
        "limitations": [
            "DeepWuKong reports function/source-level vulnerability probability by taking the maximum vulnerable probability across generated XFG slices.",
            "The output is not line-level localization.",
            "If no sensitive XFG slices are generated, the source is reported as non-vulnerable with probability 0.0 and a warning.",
        ],
        "warnings": [prediction["warning"]] if prediction.get("warning") else [],
    }
    write_prediction_outputs(output_dir, row, details)
    print(json.dumps(row, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
