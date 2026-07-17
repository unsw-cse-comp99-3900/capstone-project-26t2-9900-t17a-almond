from __future__ import annotations

import argparse
import csv
import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Literal, Sequence

import networkx as nx


ActionName = Literal[
    "node_add",
    "node_delete",
    "node_attribute_modify",
    "edge_add",
    "edge_delete",
    "edge_reconnect",
]
StrategyName = Literal["random", "guided"]

ACTION_NAMES: tuple[ActionName, ...] = (
    "node_add",
    "node_delete",
    "node_attribute_modify",
    "edge_add",
    "edge_delete",
    "edge_reconnect",
)
STRATEGY_NAMES: tuple[StrategyName, ...] = ("random", "guided")
EDGE_KINDS = {"c", "d"}


@dataclass(frozen=True)
class GraphOperation:
    step: int
    action: str
    target_nodes: tuple[int, ...]
    removed_edges: tuple[tuple[int, int, str], ...] = ()
    added_edges: tuple[tuple[int, int, str], ...] = ()
    details: str = ""


@dataclass(frozen=True)
class GraphPerturbationResult:
    graph: nx.DiGraph
    action: str
    strategy: str
    requested_count: int
    applied_count: int
    operations: tuple[GraphOperation, ...]
    validation_errors: tuple[str, ...]
    notes: str

    @property
    def valid(self) -> bool:
        return not self.validation_errors


def flatten_key_lines(key_lines: Iterable[int] | dict[str, Iterable[int]] | None) -> set[int]:
    if key_lines is None:
        return set()
    if isinstance(key_lines, dict):
        return {int(line) for lines in key_lines.values() for line in lines}
    return {int(line) for line in key_lines}


def _edge_kind(attributes: dict[str, Any]) -> str:
    return str(attributes.get("c/d", "d"))


def validate_pdg(graph: nx.DiGraph, key_lines: Iterable[int] | None = None) -> tuple[str, ...]:
    errors: list[str] = []
    if not isinstance(graph, nx.DiGraph) or isinstance(graph, nx.MultiDiGraph):
        errors.append("graph must be a networkx.DiGraph")
        return tuple(errors)
    if graph.number_of_nodes() == 0:
        errors.append("graph has no nodes")
    for node, attributes in graph.nodes(data=True):
        if not isinstance(node, int):
            errors.append(f"node {node!r} is not an integer line/synthetic identifier")
        source_line = attributes.get("source_line")
        if source_line is not None and (not isinstance(source_line, int) or source_line <= 0):
            errors.append(f"node {node!r} has invalid source_line {source_line!r}")
    for source, target, attributes in graph.edges(data=True):
        kind = _edge_kind(attributes)
        if kind not in EDGE_KINDS:
            errors.append(f"edge {source!r}->{target!r} has invalid c/d value {kind!r}")
    missing_seeds = set(key_lines or ()) - set(graph.nodes)
    if missing_seeds:
        errors.append(f"key-line nodes were removed: {sorted(missing_seeds)}")
    return tuple(errors)


def _distance_to_seeds(graph: nx.DiGraph, key_lines: set[int]) -> dict[int, float]:
    sources = sorted(key_lines.intersection(graph.nodes))
    if not sources:
        return {int(node): math.inf for node in graph.nodes}
    distances = nx.multi_source_dijkstra_path_length(graph.to_undirected(), sources, weight=None)
    return {int(node): float(distance) for node, distance in distances.items()}


def _choose(
    candidates: Sequence[Any],
    strategy: StrategyName,
    rng: random.Random,
    guided_key: Any,
) -> Any | None:
    if not candidates:
        return None
    if strategy == "random":
        return rng.choice(list(candidates))
    return min(candidates, key=guided_key)


def _next_synthetic_node_id(graph: nx.DiGraph) -> int:
    candidate = min([-1, *(int(node) - 1 for node in graph.nodes)])
    while candidate in graph:
        candidate -= 1
    return candidate


def _node_key(graph: nx.DiGraph, distances: dict[int, float], node: int) -> tuple[Any, ...]:
    return (distances.get(node, math.inf), -graph.degree(node), node)


def _edge_key(
    graph: nx.DiGraph,
    distances: dict[int, float],
    edge: tuple[int, int],
) -> tuple[Any, ...]:
    source, target = edge
    return (
        min(distances.get(source, math.inf), distances.get(target, math.inf)),
        -(graph.degree(source) + graph.degree(target)),
        source,
        target,
    )


def _apply_node_add(
    graph: nx.DiGraph,
    strategy: StrategyName,
    rng: random.Random,
    distances: dict[int, float],
    edge_kind: str,
    step: int,
) -> GraphOperation | None:
    anchors = [int(node) for node in graph.nodes]
    anchor = _choose(anchors, strategy, rng, lambda node: _node_key(graph, distances, node))
    if anchor is None:
        return None
    synthetic = _next_synthetic_node_id(graph)
    source_line = int(graph.nodes[anchor].get("source_line", anchor))
    graph.add_node(synthetic, synthetic=True, source_line=source_line)
    graph.add_edge(anchor, synthetic, **{"c/d": edge_kind})
    return GraphOperation(
        step=step,
        action="node_add",
        target_nodes=(anchor, synthetic),
        added_edges=((anchor, synthetic, edge_kind),),
        details=f"added synthetic node {synthetic} using source line {source_line}",
    )


def _apply_node_delete(
    graph: nx.DiGraph,
    strategy: StrategyName,
    rng: random.Random,
    distances: dict[int, float],
    protected_nodes: set[int],
    step: int,
) -> GraphOperation | None:
    candidates = [int(node) for node in graph.nodes if node not in protected_nodes]
    node = _choose(candidates, strategy, rng, lambda item: _node_key(graph, distances, item))
    if node is None:
        return None
    removed_edges = tuple(
        sorted(
            {
                (int(source), int(target), _edge_kind(attributes))
                for source, target, attributes in graph.edges(node, data=True)
            }
            | {
                (int(source), int(target), _edge_kind(attributes))
                for source, target, attributes in graph.in_edges(node, data=True)
            }
        )
    )
    graph.remove_node(node)
    return GraphOperation(
        step=step,
        action="node_delete",
        target_nodes=(node,),
        removed_edges=removed_edges,
        details=f"deleted non-key node {node} and its incident edges",
    )


def _apply_node_attribute_modify(
    graph: nx.DiGraph,
    strategy: StrategyName,
    rng: random.Random,
    distances: dict[int, float],
    protected_nodes: set[int],
    step: int,
) -> GraphOperation | None:
    pairs: list[tuple[int, int]] = []
    nodes = [int(node) for node in graph.nodes]
    for target in nodes:
        if target in protected_nodes:
            continue
        old_line = int(graph.nodes[target].get("source_line", target))
        for donor in nodes:
            donor_line = int(graph.nodes[donor].get("source_line", donor))
            if donor != target and donor_line != old_line and donor_line > 0:
                pairs.append((target, donor))
    pair = _choose(
        pairs,
        strategy,
        rng,
        lambda item: (*_node_key(graph, distances, item[0]), item[1]),
    )
    if pair is None:
        return None
    target, donor = pair
    old_line = int(graph.nodes[target].get("source_line", target))
    new_line = int(graph.nodes[donor].get("source_line", donor))
    graph.nodes[target]["source_line"] = new_line
    graph.nodes[target]["feature_modified"] = True
    return GraphOperation(
        step=step,
        action="node_attribute_modify",
        target_nodes=(target, donor),
        details=f"changed node {target} token source from line {old_line} to line {new_line}",
    )


def _apply_edge_add(
    graph: nx.DiGraph,
    strategy: StrategyName,
    rng: random.Random,
    distances: dict[int, float],
    edge_kind: str,
    step: int,
) -> GraphOperation | None:
    nodes = [int(node) for node in graph.nodes]
    candidates = [
        (source, target)
        for source in nodes
        for target in nodes
        if source != target and not graph.has_edge(source, target)
    ]
    edge = _choose(candidates, strategy, rng, lambda item: _edge_key(graph, distances, item))
    if edge is None:
        return None
    source, target = edge
    graph.add_edge(source, target, **{"c/d": edge_kind})
    return GraphOperation(
        step=step,
        action="edge_add",
        target_nodes=(source, target),
        added_edges=((source, target, edge_kind),),
        details=f"added {edge_kind} edge {source}->{target}",
    )


def _apply_edge_delete(
    graph: nx.DiGraph,
    strategy: StrategyName,
    rng: random.Random,
    distances: dict[int, float],
    step: int,
) -> GraphOperation | None:
    candidates = [(int(source), int(target)) for source, target in graph.edges]
    edge = _choose(candidates, strategy, rng, lambda item: _edge_key(graph, distances, item))
    if edge is None:
        return None
    source, target = edge
    edge_kind = _edge_kind(graph.edges[source, target])
    graph.remove_edge(source, target)
    return GraphOperation(
        step=step,
        action="edge_delete",
        target_nodes=(source, target),
        removed_edges=((source, target, edge_kind),),
        details=f"deleted {edge_kind} edge {source}->{target}",
    )


def _apply_edge_reconnect(
    graph: nx.DiGraph,
    strategy: StrategyName,
    rng: random.Random,
    distances: dict[int, float],
    step: int,
) -> GraphOperation | None:
    nodes = [int(node) for node in graph.nodes]
    candidates = [
        (int(source), int(target), replacement)
        for source, target in graph.edges
        for replacement in nodes
        if replacement not in {source, target} and not graph.has_edge(source, replacement)
    ]
    candidate = _choose(
        candidates,
        strategy,
        rng,
        lambda item: (*_edge_key(graph, distances, (item[0], item[1])), item[2]),
    )
    if candidate is None:
        return None
    source, old_target, new_target = candidate
    attributes = dict(graph.edges[source, old_target])
    edge_kind = _edge_kind(attributes)
    graph.remove_edge(source, old_target)
    graph.add_edge(source, new_target, **attributes)
    return GraphOperation(
        step=step,
        action="edge_reconnect",
        target_nodes=(source, old_target, new_target),
        removed_edges=((source, old_target, edge_kind),),
        added_edges=((source, new_target, edge_kind),),
        details=f"reconnected {edge_kind} edge {source}->{old_target} to {source}->{new_target}",
    )


def apply_graph_action(
    pdg: nx.DiGraph,
    action: ActionName,
    count: int = 1,
    strategy: StrategyName = "random",
    key_lines: Iterable[int] | dict[str, Iterable[int]] | None = None,
    seed: int = 0,
    edge_kind: str = "d",
) -> GraphPerturbationResult:
    if action not in ACTION_NAMES:
        raise ValueError(f"unknown graph action: {action}")
    if strategy not in STRATEGY_NAMES:
        raise ValueError(f"unknown selection strategy: {strategy}")
    if count < 1:
        raise ValueError("count must be at least 1")
    if edge_kind not in EDGE_KINDS:
        raise ValueError("edge_kind must be 'c' or 'd'")

    protected_nodes = flatten_key_lines(key_lines)
    if strategy == "guided" and not protected_nodes:
        raise ValueError("guided strategy requires at least one key line")

    graph = pdg.copy()
    original_errors = validate_pdg(graph, protected_nodes.intersection(graph.nodes))
    if original_errors:
        return GraphPerturbationResult(
            graph=graph,
            action=action,
            strategy=strategy,
            requested_count=count,
            applied_count=0,
            operations=(),
            validation_errors=original_errors,
            notes="input PDG failed validation",
        )

    rng = random.Random(seed)
    operations: list[GraphOperation] = []
    for step in range(1, count + 1):
        distances = _distance_to_seeds(graph, protected_nodes)
        if action == "node_add":
            operation = _apply_node_add(graph, strategy, rng, distances, edge_kind, step)
        elif action == "node_delete":
            operation = _apply_node_delete(graph, strategy, rng, distances, protected_nodes, step)
        elif action == "node_attribute_modify":
            operation = _apply_node_attribute_modify(graph, strategy, rng, distances, protected_nodes, step)
        elif action == "edge_add":
            operation = _apply_edge_add(graph, strategy, rng, distances, edge_kind, step)
        elif action == "edge_delete":
            operation = _apply_edge_delete(graph, strategy, rng, distances, step)
        else:
            operation = _apply_edge_reconnect(graph, strategy, rng, distances, step)
        if operation is None:
            break
        operations.append(operation)

    validation_errors = validate_pdg(graph, protected_nodes.intersection(pdg.nodes))
    if len(operations) == count:
        notes = f"applied {count} {action} operation(s)"
    elif operations:
        notes = f"applied {len(operations)} of {count} requested {action} operation(s)"
    else:
        notes = f"no valid target was available for {action}"
    return GraphPerturbationResult(
        graph=graph,
        action=action,
        strategy=strategy,
        requested_count=count,
        applied_count=len(operations),
        operations=tuple(operations),
        validation_errors=validation_errors,
        notes=notes,
    )


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _line_number(location: str) -> int | None:
    try:
        line = int(location.split(":", 1)[0])
    except (TypeError, ValueError):
        return None
    return line if line > 0 else None


def load_joern_pdg(csv_root: Path) -> nx.DiGraph:
    nodes_path = csv_root / "nodes.csv"
    edges_path = csv_root / "edges.csv"
    if not nodes_path.is_file() or not edges_path.is_file():
        raise FileNotFoundError(f"nodes.csv and edges.csv are required under {csv_root}")

    node_id_to_line: dict[str, int] = {}
    for node in _read_tsv(nodes_path):
        line = _line_number(node.get("location", ""))
        node_id = node.get("key", "").strip()
        if node_id and line is not None:
            node_id_to_line[node_id] = line

    typed_edges: dict[str, list[tuple[int, int, dict[str, str]]]] = {"c": [], "d": []}
    for edge in _read_tsv(edges_path):
        edge_type = edge.get("type", "").strip()
        kind = "c" if edge_type == "CONTROLS" else "d" if edge_type == "REACHES" else None
        source = node_id_to_line.get(edge.get("start", "").strip())
        target = node_id_to_line.get(edge.get("end", "").strip())
        if kind is not None and source is not None and target is not None:
            typed_edges[kind].append((source, target, {"c/d": kind}))

    graph = nx.DiGraph(csv_root=str(csv_root.resolve()))
    graph.add_edges_from(typed_edges["c"])
    graph.add_edges_from(typed_edges["d"])
    return graph


def graph_payload(result: GraphPerturbationResult) -> dict[str, Any]:
    graph = result.graph
    return {
        "action": result.action,
        "strategy": result.strategy,
        "requested_count": result.requested_count,
        "applied_count": result.applied_count,
        "valid": result.valid,
        "validation_errors": list(result.validation_errors),
        "notes": result.notes,
        "operations": [asdict(operation) for operation in result.operations],
        "graph": {
            "attributes": dict(graph.graph),
            "nodes": [
                {"id": int(node), **dict(attributes)}
                for node, attributes in sorted(graph.nodes(data=True), key=lambda item: int(item[0]))
            ],
            "edges": [
                {"source": int(source), "target": int(target), **dict(attributes)}
                for source, target, attributes in sorted(
                    graph.edges(data=True), key=lambda item: (int(item[0]), int(item[1]))
                )
            ],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply direct node/edge perturbations to a Joern-derived PDG.")
    parser.add_argument("--csv-root", required=True, type=Path, help="Directory containing Joern nodes.csv and edges.csv.")
    parser.add_argument("--action", required=True, choices=ACTION_NAMES)
    parser.add_argument("--strategy", choices=STRATEGY_NAMES, default="random")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--edge-kind", choices=sorted(EDGE_KINDS), default="d")
    parser.add_argument("--key-lines", nargs="*", type=int, default=[])
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pdg = load_joern_pdg(args.csv_root.resolve())
    result = apply_graph_action(
        pdg,
        action=args.action,
        count=args.count,
        strategy=args.strategy,
        key_lines=args.key_lines,
        seed=args.seed,
        edge_kind=args.edge_kind,
    )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(graph_payload(result), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Action: {result.action}")
    print(f"Strategy: {result.strategy}")
    print(f"Applied: {result.applied_count}/{result.requested_count}")
    print(f"Graph: {result.graph.number_of_nodes()} nodes, {result.graph.number_of_edges()} edges")
    print(f"Valid: {result.valid}")
    print(f"Output: {output}")
    return 0 if result.valid and result.applied_count > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
