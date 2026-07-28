from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
import tempfile
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_WORKSPACE_ROOT = Path("/workspace")
DEFAULT_REPO_ROOT = Path("/repo")
DEFAULT_BASELINE_SCRIPTS = Path("/baseline/scripts")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate cached DeepWuKong predictions for showcase code and PDG perturbations."
    )
    parser.add_argument("--catalog", required=True, type=Path, help="Showcase sample catalog JSON.")
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--strategy", choices=("random",), default="random")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--joern-timeout", type=int, default=600)
    parser.add_argument("--workspace-root", type=Path, default=DEFAULT_WORKSPACE_ROOT)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--baseline-scripts", type=Path, default=DEFAULT_BASELINE_SCRIPTS)
    parser.add_argument("--joern-bin", type=Path, default=None)
    parser.add_argument("--sensi-api", type=Path, default=None)
    parser.add_argument("--device", default="auto", help="Torch device, or 'auto'.")
    return parser.parse_args(argv)


def json_safe(value: Any) -> Any:
    """Convert model, graph, and dataclass values to strict JSON values."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return json_safe(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [json_safe(item) for item in value]
    item_method = getattr(value, "item", None)
    if callable(item_method):
        try:
            return json_safe(item_method())
        except (TypeError, ValueError, RuntimeError):
            pass
    return str(value)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(json_safe(payload), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(rendered, encoding="utf-8")
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_component(value: str, field: str) -> str:
    if not value or value in {".", ".."} or Path(value).name != value or "/" in value or "\\" in value:
        raise ValueError(f"{field} must be a non-empty path component: {value!r}")
    return value


def resolve_source(source_root: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute():
        raise ValueError(f"catalog source path must be relative: {relative_path!r}")
    root = source_root.resolve()
    source = (root / relative).resolve()
    try:
        source.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"catalog source path escapes source root: {relative_path!r}") from exc
    if not source.is_file():
        raise FileNotFoundError(f"source file not found: {source}")
    return source


def load_catalog(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("samples"), list):
        raise ValueError("catalog must be an object containing a samples array")

    raw_code_actions = payload.get("code_actions")
    if raw_code_actions is not None and not isinstance(raw_code_actions, list):
        raise ValueError("catalog code_actions must be an array")
    code_actions = (
        [safe_component(str(action), "catalog code action") for action in raw_code_actions]
        if raw_code_actions is not None
        else []
    )
    if len(set(code_actions)) != len(code_actions):
        raise ValueError("catalog code_actions contains duplicates")

    samples: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    inferred_actions: list[str] = []
    for index, raw_sample in enumerate(payload["samples"]):
        if not isinstance(raw_sample, dict):
            raise ValueError(f"samples[{index}] must be an object")
        missing = [name for name in ("key", "sample_id", "source_relpath", "variants") if name not in raw_sample]
        if missing:
            raise ValueError(f"samples[{index}] is missing: {', '.join(missing)}")
        key = safe_component(str(raw_sample["key"]), f"samples[{index}].key")
        if key in seen_keys:
            raise ValueError(f"duplicate sample key: {key!r}")
        seen_keys.add(key)
        if not isinstance(raw_sample["variants"], dict):
            raise ValueError(f"samples[{index}].variants must be an object")
        variants: dict[str, str] = {}
        for action, relative_path in raw_sample["variants"].items():
            action_name = safe_component(str(action), f"samples[{index}].variants action")
            if not isinstance(relative_path, str) or not relative_path:
                raise ValueError(f"samples[{index}].variants[{action_name!r}] must be a relative path string")
            variants[action_name] = relative_path
            if action_name not in inferred_actions:
                inferred_actions.append(action_name)

        raw_application_skipped = raw_sample.get("application_skipped", [])
        if not isinstance(raw_application_skipped, list):
            raise ValueError(f"samples[{index}].application_skipped must be an array")
        application_skipped: list[dict[str, str]] = []
        for skip_index, raw_skip in enumerate(raw_application_skipped):
            if not isinstance(raw_skip, dict):
                raise ValueError(f"samples[{index}].application_skipped[{skip_index}] must be an object")
            action_name = safe_component(
                str(raw_skip.get("action", "")),
                f"samples[{index}].application_skipped[{skip_index}].action",
            )
            application_skipped.append(
                {
                    "kind": str(raw_skip.get("kind", "code")),
                    "action": action_name,
                    "reason": str(raw_skip.get("reason", "code action was not applied")),
                }
            )
            if action_name not in inferred_actions:
                inferred_actions.append(action_name)

        samples.append(
            {
                "key": key,
                "sample_id": str(raw_sample["sample_id"]),
                "function_hint": str(raw_sample.get("function_hint", "")),
                "source_relpath": str(raw_sample["source_relpath"]),
                "variants": variants,
                "application_skipped": application_skipped,
            }
        )

    if not code_actions:
        code_actions = inferred_actions
    known_actions = set(code_actions)
    for sample in samples:
        unexpected = (set(sample["variants"]) | {item["action"] for item in sample["application_skipped"]}) - known_actions
        if unexpected:
            raise ValueError(f"sample {sample['key']!r} contains code actions absent from catalog: {sorted(unexpected)}")
    return samples, code_actions


def configure_import_paths(workspace_root: Path, repo_root: Path, baseline_scripts: Path) -> None:
    requested = [str(workspace_root.resolve()), str(repo_root.resolve()), str(baseline_scripts.resolve())]
    sys.path[:] = requested + [entry for entry in sys.path if entry not in requested]


def ensure_joern_csv(
    *,
    source_path: Path,
    cache_dir: Path,
    joern_bin: Path,
    timeout_seconds: int,
    run_joern: Any,
) -> Path:
    source_digest = sha256_file(source_path)
    nodes_path = cache_dir / "nodes.csv"
    edges_path = cache_dir / "edges.csv"
    digest_path = cache_dir / "source.sha256"
    if nodes_path.is_file() and edges_path.is_file() and digest_path.is_file():
        if digest_path.read_text(encoding="ascii", errors="ignore").strip() == source_digest:
            return cache_dir

    cache_dir.parent.mkdir(parents=True, exist_ok=True)
    stage_root = Path(tempfile.mkdtemp(prefix=f".{cache_dir.name}-joern-", dir=cache_dir.parent))
    try:
        staged_source_dir = stage_root / "source"
        staged_source_dir.mkdir(parents=True)
        staged_source = staged_source_dir / source_path.name
        shutil.copyfile(source_path, staged_source)
        joern_result = run_joern(
            joern_bin=joern_bin,
            source_path=staged_source,
            output_dir=stage_root / "output",
            timeout_seconds=timeout_seconds,
        )
        if joern_result.get("parse_status") != "success":
            raise RuntimeError(str(joern_result.get("error") or "Joern extraction failed"))
        selected = joern_result.get("selected_csv_dir")
        if not selected:
            raise RuntimeError("Joern extraction did not identify a CSV directory")
        selected_dir = Path(str(selected))
        staged_nodes = selected_dir / "nodes.csv"
        staged_edges = selected_dir / "edges.csv"
        if not staged_nodes.is_file() or not staged_edges.is_file():
            raise RuntimeError("Joern extraction did not produce both nodes.csv and edges.csv")

        cache_dir.mkdir(parents=True, exist_ok=True)
        nodes_tmp = cache_dir / ".nodes.csv.tmp"
        edges_tmp = cache_dir / ".edges.csv.tmp"
        digest_tmp = cache_dir / ".source.sha256.tmp"
        shutil.copyfile(staged_nodes, nodes_tmp)
        shutil.copyfile(staged_edges, edges_tmp)
        digest_tmp.write_text(source_digest + "\n", encoding="ascii")
        nodes_tmp.replace(nodes_path)
        edges_tmp.replace(edges_path)
        digest_tmp.replace(digest_path)
        return cache_dir
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)


def serialize_pdg(graph: Any) -> dict[str, list[dict[str, Any]]]:
    nodes: list[dict[str, Any]] = []
    for node_id, attributes in sorted(graph.nodes(data=True), key=lambda item: str(item[0])):
        node = {"id": json_safe(node_id)}
        if attributes.get("source_line") is not None:
            node["source_line"] = json_safe(attributes["source_line"])
        nodes.append(node)

    edge_kinds = {"c": "control", "d": "data"}
    edges: list[dict[str, Any]] = []
    for source, target, attributes in sorted(
        graph.edges(data=True), key=lambda item: (str(item[0]), str(item[1]), str(item[2].get("c/d", "")))
    ):
        raw_kind = str(attributes.get("c/d", "d"))
        if raw_kind not in edge_kinds:
            raise ValueError(f"PDG edge {source!r}->{target!r} has invalid c/d value {raw_kind!r}")
        edges.append(
            {
                "source": json_safe(source),
                "target": json_safe(target),
                "kind": edge_kinds[raw_kind],
            }
        )
    return {"nodes": nodes, "edges": edges}


class Predictor:
    """One persistent DeepWuKong model plus graph-building dependencies."""

    def __init__(self, checkpoint: Path, threshold: float, device_name: str, sensi_api: Path) -> None:
        import torch
        from src.data_generator import build_PDG, build_XFG
        from src.datas.graphs import XFG
        from src.models.vd import DeepWuKong
        from torch_geometric.data import Batch

        self.torch = torch
        self.Batch = Batch
        self.XFG = XFG
        self.build_PDG = build_PDG
        self.build_XFG = build_XFG
        self.sensi_api = sensi_api
        self.threshold = threshold
        selected_device = device_name if device_name != "auto" else ("cuda:0" if torch.cuda.is_available() else "cpu")
        self.device = torch.device(selected_device)
        self.model = DeepWuKong.load_from_checkpoint(
            checkpoint_path=str(checkpoint),
            weights_only=False,
        ).to(self.device)
        self.model.eval()
        self.config = self.model.hparams["config"]
        self.vocab = self.model.hparams["vocab"]

    def build_graph(self, csv_root: Path, source_path: Path) -> tuple[Any, dict[str, set[int]]]:
        pdg, key_line_map = self.build_PDG(str(csv_root), str(self.sensi_api), str(source_path))
        if pdg is None or key_line_map is None:
            raise RuntimeError("DeepWuKong could not build a PDG and sensitive-line map")
        return pdg, key_line_map

    def predict_graph(self, pdg: Any, key_line_map: dict[str, set[int]], add_symbols: Any) -> dict[str, Any]:
        xfg_dict = self.build_XFG(pdg, key_line_map) or {}
        data_list = []
        for graphs in xfg_dict.values():
            for graph in graphs:
                symbolized = add_symbols(graph, self.config.split_token)
                data_list.append(self.XFG(xfg=symbolized).to_torch(self.vocab, self.config.dataset.token.max_parts))

        if not data_list:
            return {"probability": 0.0, "label": 0, "xfg_count": 0}

        batch = self.Batch.from_data_list(data_list).to(self.device)
        with self.torch.no_grad():
            probabilities = self.torch.softmax(self.model(batch), dim=1).detach().cpu().tolist()
        vulnerable_probabilities = [float(values[1]) if len(values) > 1 else 0.0 for values in probabilities]
        probability = max(vulnerable_probabilities, default=0.0)
        return {
            "probability": probability,
            "label": int(probability >= self.threshold),
            "xfg_count": len(vulnerable_probabilities),
        }


def skipped_entry(kind: str, name: str, stage: str, exc: BaseException) -> dict[str, str]:
    return {
        "kind": kind,
        "name": name,
        "stage": stage,
        "error": f"{type(exc).__name__}: {exc}",
    }


def build_and_predict_variant(
    *,
    predictor: Predictor,
    add_symbols: Any,
    run_joern: Any,
    source_path: Path,
    cache_dir: Path,
    joern_bin: Path,
    joern_timeout: int,
) -> tuple[dict[str, Any], Any, dict[str, set[int]]]:
    csv_root = ensure_joern_csv(
        source_path=source_path,
        cache_dir=cache_dir,
        joern_bin=joern_bin,
        timeout_seconds=joern_timeout,
        run_joern=run_joern,
    )
    pdg, key_line_map = predictor.build_graph(csv_root, source_path)
    prediction = predictor.predict_graph(pdg, key_line_map, add_symbols)
    return {"prediction": prediction, "graph": serialize_pdg(pdg)}, pdg, key_line_map


def run(args: argparse.Namespace) -> dict[str, int]:
    workspace_root = args.workspace_root.resolve()
    repo_root = args.repo_root.resolve()
    baseline_scripts = args.baseline_scripts.resolve()
    configure_import_paths(workspace_root, repo_root, baseline_scripts)

    from robustness_experiments.graph.graph_perturbations import ACTION_NAMES, apply_graph_action
    from infer_single_source import add_symbols, function_name, run_joern

    source_root = args.source_root.resolve()
    output_dir = args.output_root.resolve()
    joern_bin = (args.joern_bin or (workspace_root / "joern" / "joern-parse")).resolve()
    sensi_api = (args.sensi_api or (workspace_root / "data" / "sensiAPI.txt")).resolve()
    samples, code_actions = load_catalog(args.catalog.resolve())
    output_dir.mkdir(parents=True, exist_ok=True)

    predictor = Predictor(args.checkpoint.resolve(), args.threshold, args.device, sensi_api)
    summary = {
        "samples_total": len(samples),
        "samples_completed": 0,
        "code_attempted": 0,
        "code_succeeded": 0,
        "graph_attempted": 0,
        "graph_succeeded": 0,
        "skipped": 0,
    }

    for sample in samples:
        key = sample["key"]
        result: dict[str, Any] = {
            "key": key,
            "sample_id": sample["sample_id"],
            "function_hint": sample["function_hint"],
            "source_relpath": sample["source_relpath"],
            "function_name": None,
            "original": None,
            "code_actions": {},
            "graph_actions": {},
            "skipped": [],
        }
        original_pdg = None
        original_key_line_map = None

        try:
            original_source = resolve_source(source_root, sample["source_relpath"])
            source_code = original_source.read_text(encoding="utf-8", errors="replace")
            result["function_name"] = sample["function_hint"] or function_name(source_code)
            original, original_pdg, original_key_line_map = build_and_predict_variant(
                predictor=predictor,
                add_symbols=add_symbols,
                run_joern=run_joern,
                source_path=original_source,
                cache_dir=output_dir / "joern" / key / "original",
                joern_bin=joern_bin,
                joern_timeout=args.joern_timeout,
            )
            result["original"] = original
        except Exception as exc:
            result["skipped"].append(skipped_entry("original", "original", "build_or_predict", exc))

        result["skipped"].extend(sample["application_skipped"])
        application_skipped_actions = {item["action"] for item in sample["application_skipped"]}
        for action in code_actions:
            summary["code_attempted"] += 1
            if action not in sample["variants"]:
                if action not in application_skipped_actions:
                    result["skipped"].append(
                        {
                            "kind": "code",
                            "action": action,
                            "reason": "catalog has neither a generated variant nor an application failure",
                        }
                    )
                continue
            try:
                variant_source = resolve_source(source_root, sample["variants"][action])
                variant, _, _ = build_and_predict_variant(
                    predictor=predictor,
                    add_symbols=add_symbols,
                    run_joern=run_joern,
                    source_path=variant_source,
                    cache_dir=output_dir / "joern" / key / action,
                    joern_bin=joern_bin,
                    joern_timeout=args.joern_timeout,
                )
                result["code_actions"][action] = variant
                summary["code_succeeded"] += 1
            except Exception as exc:
                result["skipped"].append(skipped_entry("code_action", action, "build_or_predict", exc))

        for action in ACTION_NAMES:
            summary["graph_attempted"] += 1
            try:
                if original_pdg is None or original_key_line_map is None:
                    raise RuntimeError("original PDG is unavailable")
                perturbation = apply_graph_action(
                    original_pdg,
                    action=action,
                    strategy=args.strategy,
                    count=args.count,
                    seed=args.seed,
                    key_lines=original_key_line_map,
                )
                if not perturbation.valid or perturbation.applied_count != args.count:
                    detail = perturbation.notes or "; ".join(perturbation.validation_errors)
                    raise RuntimeError(detail or "graph action was not applied")
                prediction = predictor.predict_graph(perturbation.graph, original_key_line_map, add_symbols)
                result["graph_actions"][action] = {
                    "strategy": args.strategy,
                    "seed": args.seed,
                    "notes": perturbation.notes,
                    "operations": list(perturbation.operations),
                    "prediction": prediction,
                    "graph": serialize_pdg(perturbation.graph),
                }
                summary["graph_succeeded"] += 1
            except Exception as exc:
                result["skipped"].append(skipped_entry("graph_action", str(action), "perturb_or_predict", exc))

        summary["skipped"] += len(result["skipped"])
        write_json(output_dir / "results" / f"{key}.json", result)
        summary["samples_completed"] += 1

    write_json(output_dir / "summary.json", summary)
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
